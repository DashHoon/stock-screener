"""배치 파이프라인 진입점.

사용:
  python -m batch.run                  # 전체 (수집 갱신 → 계산 → JSON 산출)
  python -m batch.run --backfill       # 백필만 (최초 1회 또는 캐시 재구축)
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
from batch.indicators.core import compute_indicators
from batch.indicators.flags import compute_flags
from batch.output import writer

log = logging.getLogger("batch")


def collect(codes: list[str]) -> None:
    """일별 수집. 공공 API 우선, 실패/키 없음이면 fdr 증분 갱신."""
    if daily.api_key():
        # 어제부터 거슬러 올라가며 가장 최근 거래일 데이터를 찾는다 (최대 5일)
        for back in range(1, 6):
            bas_dt = (dt.date.today() - dt.timedelta(days=back)).strftime("%Y%m%d")
            day = daily.fetch_day(bas_dt)
            if not day.empty:
                daily.merge_into_cache(day)
                return
        log.warning("공공 API 최근 5일 데이터 없음 — fdr 폴백")
    else:
        log.info("DATA_GO_KR_API_KEY 없음 — FinanceDataReader 증분 갱신")
    backfill.update_all(codes)


def compute_and_write(stocks) -> dict:
    """캐시의 전 종목을 계산해 JSON 산출. 통계 dict를 돌려준다."""
    entries: list[dict] = []
    skipped = failed = 0
    latest_date = ""

    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < config.MIN_ROWS_FOR_INDICATORS:
            skipped += 1
            continue
        try:
            ind = compute_indicators(ohlcv)
            flags, events = compute_flags(ind)
            entries.append(writer.stock_entry(row.code, row.name, ind, flags))
            writer.write_chart(row.code, row.name, ind, events)
            latest_date = max(latest_date, ind["date"].iloc[-1])
        except Exception:
            log.exception("%s(%s) 계산 실패", row.name, row.code)
            failed += 1

    # 최신 거래일 데이터가 없는(거래정지 등) 종목은 스크리너에서 제외하지 않고 그대로 둔다.
    writer.write_latest(latest_date, entries)
    return {
        "date": latest_date,
        "written": len(entries),
        "skipped_short": skipped,
        "failed": failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="백필만 수행")
    parser.add_argument("--no-collect", action="store_true", help="수집 생략")
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

    if not args.no_collect:
        collect(codes)

    stats = compute_and_write(stocks)
    log.info("완료: %s (%.0f초)", stats, time.time() - t0)


if __name__ == "__main__":
    main()
