"""다이아몬드 탑 (고점권에서 변동폭 확대 → 수렴 → 하향 이탈, 하락 반전).

근사 규칙:
1. 주요 고점(윈도 내 최고가 피벗) 중심으로 전후 구간을 본다
2. 구간을 4등분해 고저 폭이 [확대 → 최대 → 수렴] 순서: q2·q3 폭이 q1·q4보다 큼
3. 중심 고점이 구간 최고이고, 시작·끝 종가가 서로 ±10% 이내 (마름모 좌우 꼭짓점)
4. 완성: 구간 끝 이후 구간 저가(수렴부 지지) 하향 이탈
"""

import numpy as np
import pandas as pd

from batch.patterns.util import PatternHit, price_pivots

DIA_HALF_MIN = 20    # 중심 고점 기준 좌우 최소 봉수
DIA_HALF_MAX = 40
DIA_WIDEN_RATIO = 1.8   # 가운데 폭이 양끝 폭의 최소 배수 (마름모 명확성)
DIA_END_TOL_PCT = 6.0   # 좌우 꼭짓점 종가 유사성
DIA_BREAK_WINDOW = 25


def detect_diamond(ind: pd.DataFrame) -> list[PatternHit]:
    n = len(ind)
    closes = ind["close"].astype(float).to_numpy()
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    ph, _ = price_pivots(ind)

    out: list[PatternHit] = []
    used: set[int] = set()

    for head in ph:
        for half in (DIA_HALF_MIN, 30, DIA_HALF_MAX):
            a, b = head - half, head + half
            if a < 0 or b >= n:
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

            support = float(np.min(lows[b - q : b + 1]))
            deadline = min(b + DIA_BREAK_WINDOW, n - 1)
            completed_at = None
            for j in range(b, deadline + 1):
                if closes[j] < support:
                    completed_at = j
                    break
                if closes[j] > highs[head]:  # 신고가 돌파 → 무효
                    break
            forming = bool(completed_at is None and deadline == n - 1)
            if completed_at is None and not forming:
                continue
            if completed_at is not None:
                if completed_at in used:
                    break
                used.add(completed_at)
            mid_low = a + int(np.argmin(lows[a : b + 1]))
            pts = sorted(
                [(int(a), float(closes[a])), (int(head), float(highs[head])),
                 (int(mid_low), float(lows[mid_low])), (int(b), float(closes[b]))],
                key=lambda t: t[0],
            )
            out.append(PatternHit(
                kind="pat_diamond",
                completed_at=completed_at,
                forming=forming,
                neckline=support,
                points=pts,
                confirmed_at=int(b),
            ))
            break  # 이 head에서는 한 사이즈만
    return out
