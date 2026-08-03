"""미래 참조 감사 — 이벤트가 발생일까지의 데이터만으로 판정되는지 검증한다.

백테스트 28전략의 수익률은 "이벤트 발생일 종가에 진입"을 전제로 한다. 그런데
탐지기가 발생일 이후의 봉을 보고 판정했다면, 그 시점에는 알 수 없었던 신호로
매매한 셈이 되어 성과가 통째로 거짓이 된다. 코드를 읽어서는 확신할 수 없으므로
실제로 과거 시점을 재현해 대조한다.

방법 (point-in-time replay):
  1. 전체 데이터로 이벤트를 뽑고, 인덱스 T 이하만 남긴다
  2. 데이터를 T까지 잘라 지표부터 다시 계산해 이벤트를 뽑는다
  3. 1에는 있는데 2에 없으면 → 그 이벤트는 T 이후 봉을 봐야 나온다 = 미래 참조

지표 계산부터 다시 하는 이유: 지표 자체에 미래 참조가 있으면(예: bfill, 중심
이동평균) 잘린 데이터에서 값이 달라져 이벤트도 달라진다. 이벤트만 다시 뽑으면
그 층을 놓친다.

실행: python -m batch.tests.audit_lookahead [--stocks N] [--cuts N]
"""

import argparse
import collections
import random

import pandas as pd

from batch import config
from batch.backtest.events import build_events
from batch.collector import backfill
from batch.indicators.core import compute_indicators


def events_at(ohlcv: pd.DataFrame, upto: int | None = None) -> dict[str, set[int]]:
    """(잘라낸) OHLCV로 지표부터 다시 계산해 이벤트를 뽑는다."""
    df = ohlcv if upto is None else ohlcv.iloc[: upto + 1]
    ind = compute_indicators(df)
    return {k: set(v) for k, v in build_events(ind).items()}


def audit_entry(code: str, ohlcv: pd.DataFrame, events: list[tuple[str, int]]) -> dict:
    """진입 시점 재현 — 백테스트 유효성을 가르는 검사.

    이벤트 발생일 그 자리에서 데이터를 끊고 다시 판정한다. 여기서 안 나오면
    실전에서 그날 볼 수 없었던 신호로 매매한 것이 되어 성과가 거짓이 된다.
    """
    bad: collections.Counter = collections.Counter()
    for kind, i in events:
        past = events_at(ohlcv, i)
        if i not in past.get(kind, set()):
            bad[kind] += 1
    return {"code": code, "checked": len(events), "bad": bad}


def audit_stability(code: str, ohlcv: pd.DataFrame, cuts: list[int]) -> dict:
    """이후 시점 재현 — 표시 안정성 검사.

    이미 발생한 이벤트가 며칠 뒤에도 그대로 보이는가. 여기서 어긋나는 건
    진입 시점에는 보였다가 나중에 사라지거나 다시 나타나는 경우다.
    백테스트를 무효화하지는 않지만, 사용자 눈에는 신호가 오락가락하는 것으로
    보이므로 신뢰도 문제다.
    """
    full = events_at(ohlcv)
    missing: collections.Counter = collections.Counter()
    extra: collections.Counter = collections.Counter()
    checked = 0
    for t in cuts:
        past = events_at(ohlcv, t)
        for kind, idxs in full.items():
            want = {i for i in idxs if i <= t}
            got = {i for i in past.get(kind, set()) if i <= t}
            checked += len(want)
            missing[kind] += len(want - got)
            extra[kind] += len(got - want)
    return {"code": code, "checked": checked, "missing": missing, "extra": extra}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stocks", type=int, default=20, help="검사할 종목 수")
    ap.add_argument("--events", type=int, default=25, help="종목당 진입 시점 재현 수")
    ap.add_argument("--cuts", type=int, default=0, help="종목당 안정성 재현 시점 수 (0=생략)")
    ap.add_argument("--seed", type=int, default=20260803)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    codes = sorted(p.stem for p in config.OHLCV_CACHE_DIR.glob("*.parquet"))
    if not codes:
        raise SystemExit("OHLCV 캐시가 없습니다. 배치를 먼저 돌리세요.")
    picked = rng.sample(codes, min(args.stocks, len(codes)))

    entry_bad: collections.Counter = collections.Counter()
    entry_checked = 0
    st_missing: collections.Counter = collections.Counter()
    st_extra: collections.Counter = collections.Counter()
    st_checked = 0
    skipped = 0

    for n, code in enumerate(picked, 1):
        ohlcv = backfill.load_cached(code)
        if ohlcv is None or len(ohlcv) < 400:
            skipped += 1
            continue
        lo, hi = 250, len(ohlcv) - 2  # 지표 워밍업 이후 ~ 마지막 직전

        # (A) 진입 시점 재현 — 발생일 그 자리에서 끊어 본다
        pool = [
            (kind, i)
            for kind, idxs in events_at(ohlcv).items()
            for i in idxs
            if lo <= i < hi
        ]
        picked_ev = rng.sample(pool, min(args.events, len(pool))) if pool else []
        r = audit_entry(code, ohlcv, picked_ev)
        entry_checked += r["checked"]
        entry_bad.update(r["bad"])
        if r["bad"]:
            print(f"  [{n}/{len(picked)}] {code} 진입 시점 미재현: {dict(r['bad'])}")

        # (B) 안정성 재현 — 며칠 뒤에도 그대로 보이는가
        if args.cuts:
            cuts = sorted(rng.sample(range(lo, hi), min(args.cuts, hi - lo)))
            s = audit_stability(code, ohlcv, cuts)
            st_checked += s["checked"]
            st_missing.update(s["missing"])
            st_extra.update(s["extra"])

    print()
    print(f"검사한 종목 {len(picked) - skipped}개 (데이터 부족 {skipped}개 제외)")
    print()
    print("■ (A) 진입 시점 재현 — 백테스트 유효성")
    print(f"   재현한 이벤트 {entry_checked:,}건")
    if entry_bad:
        print("   ✗ 발생일 데이터만으로는 나오지 않는 이벤트 (= 미래 참조)")
        for k, v in entry_bad.most_common():
            print(f"     {k:<24} {v:>6}건")
    else:
        print("   ✓ 전부 발생일까지의 데이터로 재현됨 — 미래 참조 없음")

    if args.cuts:
        print()
        print("■ (B) 표시 안정성 — 며칠 뒤에도 같은 신호가 보이는가")
        print(f"   대조한 이벤트 {st_checked:,}건")
        print(f"   사라졌다 (나중에 다시 나타남): {sum(st_missing.values()):,}건")
        print(f"   그때는 있었는데 지금은 없음:   {sum(st_extra.values()):,}건")
        print("   (진입 시점 판정이 아니라 표시 흔들림. 사용자 신뢰도 문제)")
        for k, v in (st_missing + st_extra).most_common(8):
            print(f"     {k:<24} {v:>6}건")


if __name__ == "__main__":
    main()
