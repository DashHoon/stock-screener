"""패턴 품질 필터 실험 — 돌파일 조건(거래량·추세)이 성과를 개선하는지 측정.

사용: .venv/bin/python scripts/experiment_quality.py [--limit N]

전 종목을 한 번만 순회하며 (지표+이벤트 1회 계산) 모든 전략 변형을 평가한다.
결과는 20/60일 평균 수익률·승률을 기준(무필터·시장)과 비교해 표로 출력.
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch.backtest.engine import HORIZONS, find_entries, measure, merge_samples  # noqa: E402
from batch.backtest.events import build_events  # noqa: E402
from batch.collector import backfill, master  # noqa: E402
from batch.indicators.core import compute_indicators  # noqa: E402

# 실험 대상 패턴 (대표 상승형 5종)
PATTERNS = [
    "pat_double_bottom",
    "pat_hs_inv",
    "pat_wedge_fall",
    "pat_flag_bull",
    "pat_cup_handle",
]

# 필터 변형
VARIANTS = {
    "무필터": [],
    "거래량1.5x": [["vol_ratio20", ">=", 1.5]],
    "거래량2.5x": [["vol_ratio20", ">=", 2.5]],
    "추세위(MA120)": [["ma120_gap", ">=", 0]],
    "추세아래": [["ma120_gap", "<", 0]],
    "거래량1.5x+추세위": [["vol_ratio20", ">=", 1.5], ["ma120_gap", ">=", 0]],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    stocks = master.load_or_fetch_master(refresh=False)
    if args.limit:
        stocks = stocks.head(args.limit)

    strategies = []
    for pat in PATTERNS:
        for vname, conds in VARIANTS.items():
            strategies.append({
                "id": f"{pat}|{vname}",
                "trigger": pat,
                "when": conds,
                "confirm": None,
            })

    samples = {s["id"]: {h: [] for h in HORIZONS} for s in strategies}
    baseline = {h: [] for h in HORIZONS}
    t0 = time.time()
    done = 0
    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < 60:
            continue
        ind = compute_indicators(ohlcv)
        events = build_events(ind)
        closes = ind["close"].astype(float).to_numpy()
        n = len(closes)
        for i in range(0, n - max(HORIZONS), 10):
            if closes[i] <= 0:
                continue
            for h in HORIZONS:
                baseline[h].append((closes[i + h] / closes[i] - 1) * 100)
        for s in strategies:
            entries = find_entries(ind, events, s)
            if entries:
                merge_samples(samples[s["id"]], measure(ind, entries))
        done += 1
        if done % 500 == 0:
            print(f"... {done}종목 ({time.time()-t0:.0f}초)", flush=True)

    def stat(rets):
        if not rets:
            return None
        wins = sum(1 for r in rets if r > 0)
        return len(rets), wins / len(rets) * 100, statistics.fmean(rets)

    print(f"\n종목 {done}개, {time.time()-t0:.0f}초")
    for h in (20, 60):
        b = stat(baseline[h])
        print(f"\n=== {h}일 보유 (시장 기준: 승률 {b[1]:.1f}% 평균 {b[2]:+.2f}%) ===")
        print(f"{'패턴':20s} {'필터':16s} {'표본':>7s} {'승률':>7s} {'평균':>8s} {'시장대비':>8s}")
        for pat in PATTERNS:
            for vname in VARIANTS:
                r = stat(samples[f"{pat}|{vname}"][h])
                if r is None:
                    print(f"{pat:20s} {vname:16s} {'0':>7s}")
                    continue
                cnt, win, mean = r
                print(f"{pat:20s} {vname:16s} {cnt:7,d} {win:6.1f}% {mean:+7.2f}% {mean-b[2]:+7.2f}%p")


if __name__ == "__main__":
    main()
