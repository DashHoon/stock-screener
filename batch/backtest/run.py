"""백테스트 실행: 전 종목 × 전략 → stats/backtest.json

사용:
  python -m batch.backtest.run            # 전 종목 (약 2~3분)
  python -m batch.backtest.run --limit 50 # 개발용

주 1회(토요일 전체 재백필 후) 재계산하면 충분하다.
"""

import argparse
import datetime as dt
import json
import logging
import statistics
import time

from batch import config
from batch.backtest.engine import (
    HORIZONS,
    aggregate,
    find_entries,
    measure,
    merge_samples,
)
from batch.backtest.events import build_events
from batch.backtest.strategies import STRATEGIES
from batch.collector import backfill, master
from batch.indicators.core import compute_indicators

log = logging.getLogger("backtest")

STATS_DIR = config.OUTPUT_DIR / "stats"


def run(limit: int = 0) -> dict:
    stocks = master.load_or_fetch_master(refresh=False)
    if limit:
        stocks = stocks.head(limit)

    strat_samples = {s["id"]: {h: [] for h in HORIZONS} for s in STRATEGIES}
    strat_stocks = {s["id"]: 0 for s in STRATEGIES}  # 신호가 나온 종목 수
    baseline: dict[int, list[float]] = {h: [] for h in HORIZONS}
    first_date, last_date = "9999-12-31", ""
    universe = 0

    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < config.MIN_ROWS_FOR_INDICATORS:
            continue
        universe += 1
        ind = compute_indicators(ohlcv)
        events = build_events(ind)
        first_date = min(first_date, ind["date"].iloc[0])
        last_date = max(last_date, ind["date"].iloc[-1])

        # 시장 기준선: 이 종목의 모든 봉에서 H일 후 수익률 (표본 다운샘플: 10봉마다)
        close = ind["close"].astype(float).to_numpy()
        n = len(close)
        for i in range(0, n - max(HORIZONS), 10):
            if close[i] <= 0:
                continue
            for h in HORIZONS:
                baseline[h].append((close[i + h] / close[i] - 1) * 100)

        for s in STRATEGIES:
            entries = find_entries(ind, events, s)
            if entries:
                strat_stocks[s["id"]] += 1
                merge_samples(strat_samples[s["id"]], measure(ind, entries))

    payload = {
        "generated": dt.date.today().isoformat(),
        "period": {"from": first_date, "to": last_date},
        "universe": universe,
        "horizons": HORIZONS,
        "baseline": {
            str(h): {
                "n": len(v),
                "win": round(sum(1 for r in v if r > 0) / len(v) * 100, 1),
                "mean": round(statistics.fmean(v), 2),
                "median": round(statistics.median(v), 2),
            }
            for h, v in baseline.items()
            if v
        },
        "strategies": [
            {
                "id": s["id"],
                "name": s["name"],
                "desc": s["desc"],
                "stocks": strat_stocks[s["id"]],
                "results": aggregate(strat_samples[s["id"]]),
            }
            for s in STRATEGIES
        ],
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    t0 = time.time()
    payload = run(args.limit)
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    (STATS_DIR / "backtest.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    log.info(
        "백테스트 완료: %d종목, 전략 %d개 (%.0f초)",
        payload["universe"], len(payload["strategies"]), time.time() - t0,
    )


if __name__ == "__main__":
    main()
