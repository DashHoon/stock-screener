"""패턴 검출 통계 스냅샷 — 파라미터 변경 전/후 비교와 SHAPE_CUTS 재측정용.

사용: .venv/bin/python scripts/pattern_stats.py --out /tmp/stats.json [--step 8] [--limit 0]

전 종목 캐시를 step 간격으로 샘플링해 detect_all_patterns를 돌리고 종류별
건수·기간(span)·형태점수 분포를 JSON으로 저장한다. shape_p35/p70이 곧
shape.SHAPE_CUTS의 (B컷, A컷) 재측정값이다 — 탐지 로직을 바꾸면 같은 step으로
다시 재서 SHAPE_CUTS를 갱신할 것 (2026-07-28 스윙 이식 때 step=8, 323종목 사용).
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch import config  # noqa: E402
from batch.collector import backfill  # noqa: E402
from batch.patterns import detect_all_patterns  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--step", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    files = sorted(config.OHLCV_CACHE_DIR.glob("*.parquet"))
    codes = [f.stem for f in files][:: args.step]
    if args.limit:
        codes = codes[: args.limit]

    per_kind: dict[str, dict] = {}
    per_stock_total: list[int] = []
    t0 = time.time()
    n_done = 0
    for code in codes:
        ohlcv = backfill.load_cached(code)
        if ohlcv is None or len(ohlcv) < config.MIN_ROWS_FOR_INDICATORS:
            continue
        try:
            pats = detect_all_patterns(ohlcv)
        except Exception as e:  # noqa: BLE001
            print(f"{code} FAIL {e}", file=sys.stderr)
            continue
        n_done += 1
        per_stock_total.append(len(pats))
        for p in pats:
            d = per_kind.setdefault(
                p.kind, {"n": 0, "n_completed": 0, "n_forming": 0,
                         "spans": [], "shapes": []},
            )
            d["n"] += 1
            if p.completed_at is not None:
                d["n_completed"] += 1
            if p.forming:
                d["n_forming"] += 1
            if p.points:
                d["spans"].append(int(p.points[-1][0]) - int(p.points[0][0]))
            d["shapes"].append(int(p.shape))

    def q(xs, pct):
        if not xs:
            return None
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(len(xs) * pct))]

    summary = {}
    for k, d in sorted(per_kind.items()):
        summary[k] = {
            "n": d["n"], "completed": d["n_completed"], "forming": d["n_forming"],
            "span_p10": q(d["spans"], 0.10), "span_med": q(d["spans"], 0.50),
            "span_p90": q(d["spans"], 0.90),
            "shape_med": q(d["shapes"], 0.50),
            "shape_p35": q(d["shapes"], 0.35), "shape_p70": q(d["shapes"], 0.70),
        }
    out = {
        "stocks": n_done,
        "total_patterns": sum(per_stock_total),
        "per_stock_mean": round(statistics.mean(per_stock_total), 2) if per_stock_total else 0,
        "elapsed_sec": round(time.time() - t0, 1),
        "kinds": summary,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
