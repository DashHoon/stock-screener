"""다이아몬드 탑 (고점권에서 변동폭 확대 → 수렴 → 하향 이탈, 하락 반전).

2026-07-28 스윙 기반 이식: head 후보를 고정 lookback 피벗(price_pivots)이 아니라
ATR 적응형 ZigZag 스윙 고점(minor ∪ major 합집합)에서 뽑는다. 잔파동 고점이
head로 잡혀 생기던 오탐이 줄어든다. 4분할 폭 검증·이탈 스캔 로직은 기존 유지.

근사 규칙:
1. 스윙 고점(head) 중심으로 전후 구간 [head-half, head+half]를 본다
2. 구간을 4등분해 고저 폭이 [확대 → 최대 → 수렴] 순서: 가운데 폭이 양끝 폭보다 큼
3. 중심 고점이 구간 최고이고, 시작·끝 종가가 서로 ±DIA_END_TOL_PCT% 이내
   (마름모 좌우 꼭짓점)
4. 완성: 구간 끝(b) 이후 구간 저가(수렴부 지지) 하향 이탈 — b가 이미
   head+half라서 b부터 스캔해도 미래 참조가 없다 (구조가 b 시점에 확정됨)
"""

import numpy as np
import pandas as pd

from batch.patterns.swing import build_ctx
from batch.patterns.util import PatternHit

DIA_HALF_MIN = 20    # 중심 고점 기준 좌우 최소 봉수
DIA_HALF_MAX = 40
DIA_WIDEN_RATIO = 1.8   # 가운데 폭이 양끝 폭의 최소 배수 (마름모 명확성)
DIA_END_TOL_PCT = 6.0   # 좌우 꼭짓점 종가 유사성
DIA_BREAK_WINDOW = 25


def _diamond_frame(swings, a: int, head: int, b: int, head_price: float):
    """마름모의 스윙 골격과 테두리. 아니면 None.

    왼쪽은 확산(머리보다 낮은 고점, 낮아지는 저점), 오른쪽은 수렴(머리보다 낮은
    고점, 높아지는 저점)이어야 한다. 폭 4분할 비교만 하면 급등 후 급락(역V)
    하나로도 '가운데가 넓다'가 성립한다 — 곧게 오르내린 구간에는 낮아지는/
    높아지는 저점 쌍이 없다.

    반환: (윗선 [(idx, price)...], 아랫선 [...]) — 바깥 고점·머리·바깥 고점,
    바깥 저점·최저점·바깥 저점을 잇는 마름모 테두리.
    """
    # 구조는 b 시점에 확정된다 — 그때까지 확정된 스윙만 쓴다 (미래 참조 방지)
    known = [s for s in swings if s.confirmed_at is not None and s.confirmed_at <= b]
    left = [s for s in known if a <= s.idx < head]
    right = [s for s in known if head < s.idx <= b]
    ll = [s for s in left if not s.is_high]
    rl = [s for s in right if not s.is_high]
    lh = [s for s in left if s.is_high and s.price < head_price]
    rh = [s for s in right if s.is_high and s.price < head_price]
    if not (lh and len(ll) >= 2 and ll[-1].price < ll[0].price):
        return None
    if not (rh and len(rl) >= 2 and rl[-1].price > rl[0].price):
        return None
    low = min(ll[-1], rl[0], key=lambda s: s.price)
    upper = [(lh[0].idx, lh[0].price), (head, head_price), (rh[-1].idx, rh[-1].price)]
    lower = [(ll[0].idx, ll[0].price), (low.idx, low.price), (rl[-1].idx, rl[-1].price)]
    return upper, lower


def detect_diamond(ind: pd.DataFrame, ctx=None) -> list[PatternHit]:
    if ctx is None:
        ctx = build_ctx(ind)
    n = len(ind)
    closes = ind["close"].astype(float).to_numpy()
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    # A head must have actually been confirmed by the end of its structure.
    confirmed = {}
    for swing in ctx.minor + ctx.major:
        if swing.is_high and swing.confirmed_at is not None:
            confirmed[swing.idx] = min(confirmed.get(swing.idx, swing.confirmed_at), swing.confirmed_at)
    ph = sorted(confirmed)

    out: list[PatternHit] = []
    used: set[int] = set()

    for head in ph:
        for half in range(DIA_HALF_MIN, DIA_HALF_MAX + 1, 5):
            a, b = head - half, head + half
            if a < 0 or b >= n or confirmed[head] > b:
                continue
            if highs[head] < np.max(highs[a : b + 1]) * 0.999:
                continue  # 중심이 구간 최고가 아니면 다이아몬드 탑 아님
            q = half // 2
            def width(s, e):
                return float(np.max(highs[s:e]) - np.min(lows[s:e]))
            w1 = width(a, a + q)
            w2 = width(head - q, head + q)
            w4 = width(b - q, b)
            if w1 <= 0 or w4 <= 0:
                continue
            if not (w2 >= w1 * DIA_WIDEN_RATIO and w2 >= w4 * DIA_WIDEN_RATIO):
                continue
            if abs(closes[b] - closes[a]) / closes[a] * 100 > DIA_END_TOL_PCT:
                continue
            frame = _diamond_frame(ctx.minor, a, head, b, float(highs[head]))
            if frame is None:
                continue

            support = float(np.min(lows[b - q : b + 1]))
            deadline = min(b + DIA_BREAK_WINDOW, n - 1)
            completed_at = None
            invalidated = False
            for j in range(b, deadline + 1):
                if closes[j] < support:
                    completed_at = j
                    break
                if closes[j] > highs[head]:  # 신고가 돌파 → 무효
                    invalidated = True
                    break
            forming = bool(completed_at is None and not invalidated and deadline == n - 1)
            if completed_at is None and not forming:
                continue
            if completed_at is not None:
                if completed_at in used:
                    break
                used.add(completed_at)
            out.append(PatternHit(
                kind="pat_diamond",
                completed_at=completed_at,
                forming=forming,
                neckline=support,
                points=frame[0],    # 마름모 윗테두리
                points2=frame[1],   # 마름모 아랫테두리
                confirmed_at=int(b),
                structure_span=(int(a), int(b)),
            ))
            break  # 이 head에서는 한 사이즈만
    return out
