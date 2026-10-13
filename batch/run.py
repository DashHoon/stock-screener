"""배치 파이프라인 진입점.

사용:
  python -m batch.run                  # 전체 (일자별 시세 동기화 → 계산 → JSON 산출)
  python -m batch.run --backfill       # 일자별 시세 동기화만
  python -m batch.run --rebuild-all    # 창 안의 일자별 시세를 전부 다시 받은 뒤 계산·산출
  python -m batch.run --no-collect     # 받아 둔 시세 그대로 계산·산출만
  python -m batch.run --limit 50      # 앞 50종목만 (개발용)

수집 소스: 공공데이터포털 일자별 전 종목 시세 하나 (batch/collector/daystore.py).
"""

import argparse
import json
import datetime as dt
import logging
import shutil
import time

from dotenv import load_dotenv

from batch import config
from batch.collector import backfill, daily, daystore, master
from batch.indicators.candles import detect_candles
from batch.indicators.core import compute_indicators
from batch.indicators.divergence import detect_divergences
from batch.indicators.flags import compute_flags
from batch.indicators.recent import compute_recent
from batch.output import writer
from batch.patterns import detect_all_patterns
from batch.sectors import ETC, sector_slug

log = logging.getLogger("batch")


# 지수·업종 지수는 종목 목록에 없지만 정상 산출물이다.
_KEEP_CHART_PREFIXES = ("KS11", "KQ11", "sector")


def drop_orphan_charts(codes: set[str]) -> int:
    """이번 회차에 쓰지 않은 차트 파일을 지운다.

    데이터가 모자라 건너뛴 종목(skipped_short)이나 상장폐지 종목의 차트가
    그대로 남아, 옛 규칙으로 만든 산출물이 계속 서빙됐다. 실측(2026-08-25):
    시스웍 한 종목의 2021년 차트가 남아 있어, 폐지한 A/B/C 등급과 최소 기간을
    못 지키는 패턴이 그 페이지에만 살아 있었다. 사이트도 이 디렉터리를 훑어
    종목 페이지를 만들기 때문에 5년 묵은 페이지가 검색에 노출된다.

    지우는 것은 배치가 매일 다시 만드는 산출물뿐이다 — 종목이 조건을 되찾으면
    다음 회차에 그대로 생긴다.
    """
    dropped = 0
    d = config.CHART_DIR
    if not d.exists():
        return dropped
    for f in d.glob("*.json"):
        code = f.stem
        if code in codes or code.startswith(_KEEP_CHART_PREFIXES):
            continue
        f.unlink()
        dropped += 1
        log.info("고아 차트 삭제: %s", f.relative_to(config.OUTPUT_DIR))
    return dropped


def drop_retired_outputs() -> int:
    """더 이상 배포하지 않는 대용량 산출물을 매 회차 정리한다.

    생성 코드만 끄면 data 브랜치 작업 디렉터리에 남은 옛 파일이 rsync로 다시
    배포된다. 2년 차트, 10년 아카이브, 사용자 정의 백테스트 데이터셋을 명시적으로
    지워 산출물 크기가 다시 늘지 않게 한다.
    """
    dropped = 0
    chart2y = config.OUTPUT_DIR / "chart2y"
    if chart2y.exists():
        dropped += sum(1 for p in chart2y.rglob("*") if p.is_file())
        shutil.rmtree(chart2y)
    if config.CHART_DIR.exists():
        for path in config.CHART_DIR.glob("*.arc.json"):
            path.unlink()
            dropped += 1
    dataset = config.OUTPUT_DIR / "bt" / "dataset.json"
    if dataset.exists():
        dataset.unlink()
        dropped += 1
    return dropped


def collect(force: bool = False) -> daystore.SyncResult:
    """일자별 시세를 창 전체에 걸쳐 맞추고 종목별 캐시를 다시 만든다.

    지난 거래일 중 하나라도 비면 배포하지 않는다. 그 상태로 내보내면 전 종목
    차트에 같은 날이 빠진다 — 앱에서 보이는 구멍이 신뢰를 가장 크게 깎는다.
    하루 늦은 데이터는 '전일 기준' 고지와 모순되지 않지만 구멍은 그렇지 않다.
    """
    if not daily.api_key():
        raise SystemExit("DATA_GO_KR_API_KEY 없음 — 수집할 수 없다")
    res = daystore.sync(force=force)
    if res.latest is None:
        raise SystemExit("받아 둔 일자별 시세가 없다")
    if not res.complete:
        # 앞쪽만 받고 멈춘 상태로 계산하면 기준일이 거꾸로 돌아간 데이터가 나간다
        raise SystemExit("공공 API 장애로 수집이 중간에 멈춤 — 다음 회차에 이어서 받는다")
    if res.gaps:
        raise SystemExit(f"거래일 {len(res.gaps)}일 미수집: {res.gaps[:10]} — 배포 중단")
    daystore.build_cache()
    return res


def compute_and_write(stocks) -> dict:
    """캐시의 전 종목을 계산해 JSON 산출. 통계 dict를 돌려준다."""
    entries: list[dict] = []
    skipped = failed = stale = 0
    latest_date = ""
    # 거래정지 판별: 마지막 데이터가 12일(달력) 이상 뒤처졌거나, 최근 봉이 연달아
    # 거래 없이 평평한 종목. 공공 API는 정지 기간에도 전일 종가로 된 봉을 매일
    # 주므로 날짜만으로는 안 잡힌다. 이런 종목은 평평한 봉 때문에 스퀴즈 같은
    # 시그널이 거짓으로 켜지므로 시그널을 비운다 (차트 페이지는 유지).
    stale_cutoff = (dt.date.today() - dt.timedelta(days=12)).isoformat()

    # 일봉만 만든다. 주봉·월봉은 앱이 쓰지 않으면서 파일의 58%를 차지했다.

    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < config.MIN_ROWS_FOR_INDICATORS:
            skipped += 1
            continue
        try:
            ind = compute_indicators(ohlcv)
            _flags, events = compute_flags(ind)  # events는 차트 마킹·최근 발생 계산에 재사용
            is_stale = (
                ohlcv["date"].iloc[-1] < stale_cutoff
                or bool((ohlcv["volume"].iloc[-config.HALT_ZERO_VOLUME_BARS:] == 0).all())
            )
            sig = {} if is_stale else compute_recent(ind, events)
            if is_stale:
                stale += 1

            # 차트 패턴 (일봉): 완성=돌파일 기준, 형성 중=오늘 상태.
            # 차트에는 최근 1년 창 안의 전체 이력을 싣는다 — 과거
            # 구간을 줌인해도 그 시절 패턴이 보이도록 (2026-07-26 사용자 결정).
            # 과밀은 최소 기간·형태 통과선·중복 병합으로 배치에서 걸러내고,
            # 남은 것은 종류별 칩으로 프론트에서 통제한다.
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
                    elif p.forming and not getattr(p, "pending_against", False):
                        # 실패 쪽으로 처음 이탈한 패턴은 차트에만 '이탈 대기'로 보인다
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

            # 배포 차트는 최근 1년 한 벌만 만든다.
            cdl = detect_candles(ind)
            tf = {
                "d": writer.timeframe_payload(
                    ind, events, config.CHART_DAILY_BARS,
                    patterns=chart_patterns, candles=cdl,
                )
            }
            def _s(v) -> str:
                t = str(v or "").strip()
                return "" if t in ("nan", "NaT", "None") else t

            profile = {
                k: v
                for k, v in {
                    "products": _s(getattr(row, "products", "")),
                    "industry": _s(getattr(row, "industry", "")),
                    "sector": _s(getattr(row, "sector", "")),
                    "market": _s(getattr(row, "market", "")),
                    "listed": _s(getattr(row, "listing_date", ""))[:10],
                    "ceo": _s(getattr(row, "ceo", "")),
                    "homepage": _s(getattr(row, "homepage", "")),
                    "region": _s(getattr(row, "region", "")),
                    "cap": int(getattr(row, "marcap", -1)),
                }.items()
                if v not in ("", -1)
            }
            writer.write_chart(row.code, row.name, tf, profile)
            writer.write_chart_mini(row.code, writer.mini_payload(ind, chart_patterns))
            latest_date = max(latest_date, ind["date"].iloc[-1])
        except Exception:
            log.exception("%s(%s) 계산 실패", row.name, row.code)
            failed += 1

    # 코스피/코스닥 지수: 초기 화면 카드 + 상세 차트(종목 차트 파이프라인 재사용)
    from batch.collector.indices import INDICES, fetch_index_ohlcv, summarize
    indices = []
    for sym, name in INDICES:
        try:
            iohlcv = fetch_index_ohlcv(sym)
            if iohlcv is not None and latest_date:
                # 종목 수집이 늦어진 날 지수만 하루 앞서 나가지 않게 같은 날짜로 맞춘다
                iohlcv = iohlcv[iohlcv["date"] <= latest_date].reset_index(drop=True)
            card = summarize(sym, name, iohlcv)
            if card:
                indices.append(card)
                if card["date"] < latest_date:
                    log.warning("지수 %s 마지막 봉 %s — 종목(%s)보다 뒤처짐",
                                sym, card["date"], latest_date)
            if iohlcv is None or len(iohlcv) < config.MIN_ROWS_FOR_INDICATORS:
                continue
            i_ind = compute_indicators(iohlcv)
            _f, i_events = compute_flags(i_ind)
            i_pats = detect_all_patterns(iohlcv)  # 지수도 창 내 전체 이력
            i_cdl = detect_candles(i_ind)
            writer.write_chart(
                sym,
                name,
                {
                    "d": writer.timeframe_payload(
                        i_ind, i_events, config.CHART_DAILY_BARS,
                        patterns=i_pats, candles=i_cdl,
                    )
                },
            )
        except Exception:
            log.exception("지수 %s 차트 생성 실패", sym)

    # 업종 지수 — 섹터별 시가총액 가중 지수를 만들어 종목과 같은 파이프라인에 태운다.
    # 업종맵은 '오늘 얼마나 올랐나'만 보여준다. 몇 달째 오르는 중인지, 지금이
    # 고점인지 바닥인지는 지수 시계열이 있어야 보인다.
    from batch.sector_index import build_index
    sec_written = 0
    try:
        members: dict[str, list] = {}
        for e in entries:
            cap, close = e.get("cap", -1), e.get("close") or 0
            if cap <= 0 or close <= 0:
                continue
            # 시가총액(억원) ÷ 현재가 = 주식수. 이 값을 과거 종가에 곱해 지수를 만든다
            members.setdefault(e.get("sec") or ETC, []).append(
                (e["code"], cap * 1e8 / close)
            )
        for sec, mem in members.items():
            if sec == ETC:
                continue  # '기타'는 성격이 안 묶여 지수에 의미가 없다
            rows = []
            for code, shares in mem:
                ohlcv = backfill.load_cached(code)
                if ohlcv is not None and len(ohlcv) >= config.MIN_ROWS_FOR_INDICATORS:
                    rows.append((code, shares, ohlcv))
            idx = build_index(rows)
            if idx is None:
                continue
            s_ind = compute_indicators(idx)
            s_pats = detect_all_patterns(idx)
            s_div = detect_divergences(
                s_ind["high"].astype(float), s_ind["low"].astype(float), s_ind["rsi"]
            )
            # 업종 지수는 한 벌만 만든다 — 목록에서 스치듯 보는 화면이고,
            # 구독 여부로 나눌 만큼 무겁지 않다.
            writer.write_sector_chart(
                sector_slug(sec),
                sec,
                {
                    "d": writer.timeframe_payload(
                        s_ind, s_div, config.CHART_DAILY_BARS, patterns=s_pats
                    )
                },
            )
            sec_written += 1
    except Exception:
        log.exception("업종 지수 생성 실패")

    # 최신 거래일 데이터가 없는(거래정지 등) 종목은 스크리너에서 제외하지 않고 그대로 둔다.
    writer.write_latest(latest_date, entries, indices)
    orphans = drop_orphan_charts({e["code"] for e in entries})
    retired = drop_retired_outputs()
    return {
        "date": latest_date,
        "written": len(entries),
        "skipped_short": skipped,
        # 이번에 안 쓴 옛 차트 파일. 0이 정상이고, 계속 잡히면 종목 마스터가
        # 흔들리고 있다는 뜻이다.
        "orphans_dropped": orphans,
        "retired_outputs_dropped": retired,
        "stale_no_sig": stale,
        "failed": failed,
        # 업종 수집이 조용히 실패하면 업종맵이 '기타' 한 칸으로 퇴화한다.
        # 매일 읽는 완료 로그 한 줄에 노출해 눈에 띄게 한다.
        "sector_etc_pct": round(float((stocks["sector"] == ETC).mean()) * 100, 1)
        if "sector" in stocks
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="일자별 시세 동기화만")
    parser.add_argument(
        "--rebuild-all", action="store_true",
        help="창 안의 일자별 시세를 전부 다시 받은 뒤 계산·산출",
    )
    parser.add_argument("--no-collect", action="store_true", help="수집 생략")
    parser.add_argument(
        "--collect-only", action="store_true",
        help="--backfill과 같다 (워크플로 워밍업 슬롯 호환)",
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
    log.info("대상 종목 %d개", len(stocks))

    if args.backfill or args.collect_only:
        collect()
        log.info("수집만 완료 (%.0f초)", time.time() - t0)
        return

    if not args.no_collect:
        collect(force=args.rebuild_all)

    stats = compute_and_write(stocks)
    log.info("완료: %s (%.0f초)", stats, time.time() - t0)

    # 산출이 비면 조용히 성공 처리하지 않고 실패시킨다 (CI에서 빨간불로 보이게)
    if stats["written"] == 0:
        raise SystemExit("산출 0종목 — 데이터 수집이 정상인지 확인 필요")


if __name__ == "__main__":
    main()
