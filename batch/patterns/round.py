"""라운드 바텀(접시형 바닥, 상승 반전) / 라운드 탑(하락 반전).

컵앤핸들과 같은 곡선 검증을 쓰되 핸들 없이 좌측 림 레벨 회복(돌파)으로 완성한다.
컵보다 길고 완만한 구간을 본다.
"""

import numpy as np
import pandas as pd

from batch import config
from batch.patterns.cup import _round_ok
from batch.patterns.util import PatternHit, price_pivots

RB_MIN_LEN = 60
RB_MAX_LEN = 240
RB_RIM_TOL_PCT = 8.0        # 우측 회복 지점이 좌측 림 대비 이 이내로 근접
RB_MIN_DEPTH_PCT = 15.0
RB_MAX_DEPTH_PCT = 30.0     # 40%+ 깊이는 라운드바텀이 아니라 급락 후 반등 — 실측 -6.01%p, 승률 27%
RB_BOTTOM_ZONE = (0.30, 0.70)   # 바닥이 가운데 — 치우치면 U자가 아니다
RB_FLAT_FRAC = 0.25          # 바닥권(깊이 하위 20%) 체류 비율 — 컵보다 넓고 완만해야
RB_FLAT_ZONE = 0.20
RB_BREAK_WINDOW = 60


def detect_round(ind: pd.DataFrame) -> list[PatternHit]:
    n = len(ind)
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    closes = ind["close"].astype(float).to_numpy()
    ph, pl = price_pivots(ind)

    out: list[PatternHit] = []

    def scan(bottom: bool):
        rims = ph if bottom else pl
        ext = lows if bottom else highs      # 바닥/천장 극값
        rim_ext = highs if bottom else lows  # 림 기준
        used: set[int] = set()
        for l in rims:
            rim_l = rim_ext[l]
            if rim_l <= 0:
                continue
            # 우측 회복 지점: l 이후 rim 레벨 재접근 (RB_MIN_LEN~RB_MAX_LEN)
            lo_j = l + RB_MIN_LEN
            hi_j = min(l + RB_MAX_LEN, n - 1)
            if lo_j >= n:
                continue
            for r in range(lo_j, hi_j + 1):
                near = (rim_l - rim_ext[r]) / rim_l * 100 if bottom else (rim_ext[r] - rim_l) / rim_l * 100
                if not (-RB_RIM_TOL_PCT <= near <= RB_RIM_TOL_PCT):
                    continue
                span = r - l
                seg = slice(l, r + 1)
                ib = l + int(np.argmin(ext[seg]) if bottom else np.argmax(ext[seg]))
                extreme = float(ext[ib])
                depth = (rim_l - extreme) / rim_l * 100 if bottom else (extreme - rim_l) / rim_l * 100
                if not (RB_MIN_DEPTH_PCT <= depth <= RB_MAX_DEPTH_PCT):
                    continue
                pos = (ib - l) / span
                if not (RB_BOTTOM_ZONE[0] <= pos <= RB_BOTTOM_ZONE[1]):
                    continue
                depth_abs = abs(rim_l - extreme)
                if bottom:
                    near_ext = np.sum(ext[seg] <= extreme + RB_FLAT_ZONE * depth_abs)
                else:
                    near_ext = np.sum(ext[seg] >= extreme - RB_FLAT_ZONE * depth_abs)
                if near_ext < max(6, RB_FLAT_FRAC * span):
                    continue
                seg_closes = closes[seg].copy()
                if not bottom:
                    seg_closes = 2 * seg_closes.max() - seg_closes  # ∩ → ∪ 반전
                if not _round_ok(seg_closes):
                    continue

                # 완성: r 이후 림 레벨 돌파
                deadline = min(r + RB_BREAK_WINDOW, n - 1)
                completed_at = None
                invalidated = False
                mid_level = extreme + depth_abs * 0.5 if bottom else extreme - depth_abs * 0.5
                for j in range(r, deadline + 1):
                    c = closes[j]
                    if bottom and c > rim_l:
                        completed_at = j
                        break
                    if not bottom and c < rim_l:
                        completed_at = j
                        break
                    if (bottom and c < mid_level) or (not bottom and c > mid_level):
                        invalidated = True
                        break
                forming = bool(completed_at is None and not invalidated and deadline == n - 1)
                if completed_at is None and not forming:
                    continue
                if completed_at is not None and completed_at in used:
                    break
                if completed_at is not None:
                    used.add(completed_at)
                out.append(PatternHit(
                    kind="pat_round_bottom" if bottom else "pat_round_top",
                    completed_at=completed_at,
                    forming=forming,
                    neckline=float(rim_l),
                    points=[(int(l), float(rim_l)), (int(ib), extreme),
                            (int(r), float(rim_ext[r]))],
                    confirmed_at=int(r),
                ))
                break  # 이 좌림에서는 첫 유효 회복만
    scan(bottom=True)
    scan(bottom=False)
    return out
