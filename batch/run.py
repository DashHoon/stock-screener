"""배치 파이프라인 진입점.

사용:
  python -m batch.run                  # 전체 (수집 갱신 → 계산 → JSON 산출)
  python -m batch.run --backfill       # 백필만 (최초 1회)
  python -m batch.run --rebuild-all    # 전 종목 캐시 전체 재수집 후 계산·산출 (주 1회 수정주가 보정)
  python -m batch.run --no-collect     # 캐시 그대로 계산·산출만
  python -m batch.run --limit 50      # 앞 50종목만 (개발용)

수집 소스:
  1) DATA_GO_KR_API_KEY가 있으면 공공 API 하루치 수집 → 캐시 병합
  2) 없거나 미갱신이면 FinanceDataReader 증분 갱신 폴백
"""

import argparse
import datetime as dt
import logging
import time

from dotenv import load_dotenv

from batch import config
from batch.collector import backfill, daily, master
from batch.indicators.candles import detect_candles
from batch.indicators.core import compute_indicators
from batch.indicators.divergence import detect_divergences
from batch.indicators.flags import compute_flags
from batch.indicators.recent import compute_recent
from batch.indicators.resample import resample_ohlcv
from batch.output import writer
from batch.patterns import detect_all_patterns

log = logging.getLogger("batch")


def repair_gaps(codes: list[str], target_date: str) -> None:
    """캐시가 없거나 target_date보다 뒤처진 종목을 fdr로 백필한다.

    첫 실행(빈 캐시) 부트스트랩과, 수집 실패로 생긴 공백 보정을 겸한다.
    공공 API는 하루치만 주므로 과거 구간은 여기서 채워야 한다.
    """
    stale = []
    for code in codes:
        cached = backfill.load_cached(code)
        if cached is None or len(cached) == 0 or cached["date"].iloc[-1] < target_date:
            stale.append(code)
    if stale:
        log.info("캐시 없음/공백 %d종목 → fdr 백필", len(stale))
        backfill.update_all(stale)


def market_latest_date() -> str | None:
    """실제 최신 거래일(코스피 지수 기준). 공공 API가 늦을 때 기준일로 쓴다.

    공공 API는 하루 지연에 더해 갱신이 늦어 전일치가 아직 안 올라올 때가 있다.
    그 경우에도 지수(fdr)는 최신 거래일을 갖고 있으므로, 이를 기준으로 삼아
    뒤처진 종목을 fdr로 채운다. 조회 실패 시 None(공공 API 기준 그대로).
    """
    try:
        import FinanceDataReader as fdr

        from batch.collector.backfill import latest_complete_date

        start = (dt.date.today() - dt.timedelta(days=10)).isoformat()
        df = fdr.DataReader("KS11", start)
        if df is None or df.empty:
            return None
        complete = latest_complete_date()  # 장중이면 어제, 마감 후면 오늘까지
        dates = [d for d in (str(x)[:10] for x in df.index) if d <= complete]
        return dates[-1] if dates else None
    except Exception:
        log.exception("시장 최신 거래일 조회 실패")
        return None


def collect(codes: list[str]) -> None:
    """일별 수집. 공공 API 우선, 실패/키 없음이면 fdr 증분 갱신.

    공공 API가 최신 거래일을 아직 안 올렸으면(지수보다 뒤처지면) 그 차이만큼
    fdr 증분으로 보완한다 — repair_gaps 기준일을 지수 최신일까지 끌어올린다.
    """
    if daily.api_key():
        # 어제부터 거슬러 올라가며 가장 최근 거래일 데이터를 찾는다 (최대 5일)
        for back in range(1, 6):
            bas_dt = (dt.date.today() - dt.timedelta(days=back)).strftime("%Y%m%d")
            day = daily.fetch_day(bas_dt)
            if not day.empty:
                daily.merge_into_cache(day)
                # 공공 API가 지수보다 뒤처지면 지수 최신일까지 fdr로 채운다
                target = max(day["date"].max(), market_latest_date() or "")
                repair_gaps(codes, target)
                return
        log.warning("공공 API 최근 5일 데이터 없음 — fdr 폴백")
    else:
        log.info("DATA_GO_KR_API_KEY 없음 — FinanceDataReader 증분 갱신")
    backfill.update_all(codes)


def compute_and_write(stocks) -> dict:
    """캐시의 전 종목을 계산해 JSON 산출. 통계 dict를 돌려준다."""
    entries: list[dict] = []
    skipped = failed = stale = 0
    latest_date = ""
    # 거래정지 판별 기준: 마지막 데이터가 오늘로부터 12일(달력) 이상 뒤처진 종목.
    # 이런 종목의 시그널 경과일은 자기 마지막 봉 기준이라 '최근 발생'처럼 보이는
    # 착시가 생기므로 시그널을 비운다 (차트 페이지는 유지).
    stale_cutoff = (dt.date.today() - dt.timedelta(days=12)).isoformat()

    tf_specs = [  # (키, 리샘플 주기, 담을 봉 수)
        ("d", None, config.CHART_DAILY_BARS),
        ("w", "w", config.CHART_WEEKLY_BARS),
        ("m", "m", config.CHART_MONTHLY_BARS),
    ]

    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < config.MIN_ROWS_FOR_INDICATORS:
            skipped += 1
            continue
        try:
            ind = compute_indicators(ohlcv)
            _flags, events = compute_flags(ind)  # events는 차트 마킹·최근 발생 계산에 재사용
            is_stale = ohlcv["date"].iloc[-1] < stale_cutoff  # 거래정지 등
            sig = {} if is_stale else compute_recent(ind, events)
            if is_stale:
                stale += 1

            # 차트 패턴 (일봉): 완성=돌파일 기준, 형성 중=오늘 상태.
            # 차트에는 창(CHART_DAILY_BARS≈2년) 안의 전체 이력을 싣는다 — 과거
            # 구간을 줌인해도 그 시절 패턴이 보이도록 (2026-07-26 사용자 결정).
            # 과밀은 중복 병합·C등급 기본 숨김·종류별 칩으로 프론트에서 통제한다.
            # (창 밖에서 시작한 패턴은 writer가 좌표를 만들 수 없어 자동 제외)
            patterns = detect_all_patterns(ohlcv)
            n_bars = len(ind)
            chart_patterns = patterns
            if not is_stale:
                for p in patterns:
                    if p.completed_at is not None:
                        ago = n_bars - 1 - p.completed_at
                        if ago <= config.RECENT_MAX_BARS:
                            sig[p.kind] = min(sig.get(p.kind, ago), ago)
                    elif p.forming:
                        sig[p.kind + "_form"] = 0

            entries.append(
                writer.stock_entry(
                    row.code, row.name, ind, sig,
                    marcap=int(getattr(row, "marcap", -1)),
                    market=str(getattr(row, "market", "")),
                    industry=str(getattr(row, "industry", "") or ""),
                    sector=str(getattr(row, "sector", "") or ""),
                )
            )

            tf: dict[str, dict] = {}
            for key, freq, bars in tf_specs:
                if freq is None:
                    tf_ind, tf_events = ind, events
                else:
                    resampled = resample_ohlcv(ohlcv, freq)
                    if len(resampled) < 30:  # 지표 워밍업(RSI14+BB20)에 못 미치면 생략
                        continue
                    tf_ind = compute_indicators(resampled)
                    tf_events = detect_divergences(
                        tf_ind["high"].astype(float),
                        tf_ind["low"].astype(float),
                        tf_ind["rsi"],
                    )
                tf[key] = writer.timeframe_payload(
                    tf_ind, tf_events, bars,
                    patterns=chart_patterns if key == "d" else None,
                    candles=detect_candles(ind) if key == "d" else None,
                )
            writer.write_chart(row.code, row.name, tf)
            latest_date = max(latest_date, ind["date"].iloc[-1])
        except Exception:
            log.exception("%s(%s) 계산 실패", row.name, row.code)
            failed += 1

    # 코스피/코스닥 지수: 초기 화면 카드 + 상세 차트(종목 차트 파이프라인 재사용)
    from batch.collector.indices import INDICES, fetch_index_ohlcv, fetch_indices
    try:
        indices = fetch_indices()
    except Exception:
        log.exception("지수 수집 실패")
        indices = []
    for sym, name in INDICES:
        try:
            iohlcv = fetch_index_ohlcv(sym)
            if iohlcv is None or len(iohlcv) < config.MIN_ROWS_FOR_INDICATORS:
                continue
            i_ind = compute_indicators(iohlcv)
            _f, i_events = compute_flags(i_ind)
            i_pats = detect_all_patterns(iohlcv)  # 지수도 창 내 전체 이력
            i_tf: dict[str, dict] = {}
            for key, freq, bars in tf_specs:
                if freq is None:
                    ti, te, tp = i_ind, i_events, i_pats
                else:
                    rs = resample_ohlcv(iohlcv, freq)
                    if len(rs) < 30:
                        continue
                    ti = compute_indicators(rs)
                    te = detect_divergences(ti["high"].astype(float), ti["low"].astype(float), ti["rsi"])
                    tp = None
                i_tf[key] = writer.timeframe_payload(
                    ti, te, bars,
                    patterns=tp if freq is None else None,
                    candles=detect_candles(i_ind) if freq is None else None,
                )
            writer.write_chart(sym, name, i_tf)
        except Exception:
            log.exception("지수 %s 차트 생성 실패", sym)

    # 최신 거래일 데이터가 없는(거래정지 등) 종목은 스크리너에서 제외하지 않고 그대로 둔다.
    writer.write_latest(latest_date, entries, indices)
    return {
        "date": latest_date,
        "written": len(entries),
        "skipped_short": skipped,
        "stale_no_sig": stale,
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="백필만 수행")
    parser.add_argument(
        "--rebuild-all", action="store_true",
        help="전 종목 캐시를 새로 받아 교체 (수정주가 보정) 후 계산·산출",
    )
    parser.add_argument("--no-collect", action="store_true", help="수집 생략")
    parser.add_argument(
        "--collect-only", action="store_true",
        help="시세 수집만 하고 계산·산출은 생략 (저녁 워밍업 슬롯용)",
    )
    parser.add_argument("--limit", type=int, default=0, help="앞 N종목만 (개발용)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    load_dotenv()
    t0 = time.time()

    stocks = master.load_or_fetch_master()
    if args.limit:
        stocks = stocks.head(args.limit)
    codes = stocks["code"].tolist()
    log.info("대상 종목 %d개", len(codes))

    if args.backfill:
        backfill.update_all(codes)
        log.info("백필 완료 (%.0f초)", time.time() - t0)
        return

    if args.collect_only:
        collect(codes)
        log.info("수집만 완료 (%.0f초)", time.time() - t0)
        return

    if args.rebuild_all:
        backfill.update_all(codes, rebuild=True)
    elif not args.no_collect:
        collect(codes)

    stats = compute_and_write(stocks)
    log.info("완료: %s (%.0f초)", stats, time.time() - t0)

    # 산출이 비면 조용히 성공 처리하지 않고 실패시킨다 (CI에서 빨간불로 보이게)
    if stats["written"] == 0:
        raise SystemExit("산출 0종목 — 데이터 수집이 정상인지 확인 필요")


if __name__ == "__main__":
    main()
