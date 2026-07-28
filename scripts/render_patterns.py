"""패턴 검출 결과를 캔들차트 + 구성선 PNG로 렌더링 — 눈 검증(튜닝 사이클)용.

사용: .venv/bin/python scripts/render_patterns.py <출력디렉터리> <코드,코드...> [종류접두사,...] [최근N봉]
예:   .venv/bin/python scripts/render_patterns.py /tmp "005930,000660" "pat_tri,pat_wedge" 380

PATTERN_PLAN.md의 원칙("구성 라인을 마킹해 눈으로 검증하며 파라미터 튜닝")을
로컬에서 빠르게 도는 도구. matplotlib 필요.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch.collector import backfill  # noqa: E402
from batch.patterns import detect_all_patterns  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
CODES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["005930"]
KINDS = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else None
LAST = int(sys.argv[4]) if len(sys.argv) > 4 else 500


def render(code: str) -> None:
    df = backfill.load_cached(code)
    if df is None:
        print(code, "no cache")
        return
    pats = detect_all_patterns(df)
    n = len(df)
    lo = max(0, n - LAST)
    sel = [
        p for p in pats
        if (KINDS is None or any(p.kind.startswith(k) for k in KINDS))
        and p.points[-1][0] >= lo
    ]
    if not sel:
        print(code, "no patterns in window")
        return

    o = df["open"].astype(float).to_numpy()
    h = df["high"].astype(float).to_numpy()
    l = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()

    fig, ax = plt.subplots(figsize=(20, 9))
    xs = range(lo, n)
    ax.vlines(xs, l[lo:], h[lo:], color="#999", lw=0.5)
    up = c[lo:] >= o[lo:]
    for cond, col in ((up, "#c33"), (~up, "#36c")):
        ax.vlines([x for x, u in zip(xs, cond) if u],
                  [min(a, b) for a, b, u in zip(o[lo:], c[lo:], cond) if u],
                  [max(a, b) for a, b, u in zip(o[lo:], c[lo:], cond) if u],
                  color=col, lw=2.2)

    colors = plt.cm.tab10.colors
    for i, p in enumerate(sel):
        col = colors[i % 10]
        ax.plot([pt[0] for pt in p.points], [pt[1] for pt in p.points], color=col, lw=1.8,
                label=f"{p.kind} [{p.grade}{p.shape}] "
                      f"{'done@' + str(p.completed_at) if p.completed_at is not None else 'forming'}")
        p2 = getattr(p, "points2", None)
        if p2:
            ax.plot([pt[0] for pt in p2], [pt[1] for pt in p2], color=col, lw=1.8, ls="--")
        if p.completed_at is not None:
            ax.axvline(p.completed_at, color=col, lw=0.6, ls=":", alpha=0.6)
    ax.legend(loc="upper left", fontsize=7)
    ax.set_title(f"{code} last {n - lo} bars — {len(sel)} patterns "
                 f"({'all kinds' if KINDS is None else ','.join(KINDS)})")
    ax.set_xlim(lo, n)
    seg_lo, seg_hi = l[lo:].min(), h[lo:].max()
    pad = (seg_hi - seg_lo) * 0.03
    ax.set_ylim(seg_lo - pad, seg_hi + pad)
    fig.tight_layout()
    out = OUT / f"pat_{code}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(code, len(sel), "->", out)


for code_ in CODES:
    render(code_)
