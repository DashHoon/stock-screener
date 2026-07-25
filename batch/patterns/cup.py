"""컵앤핸들(Cup and Handle) 탐지.

판정 규칙 (오닐 정의를 일봉 규칙으로 번역):
1. 좌림(L)·우림(R): 피벗 고점 쌍, 간격 CUP_MIN_LEN~CUP_MAX_LEN, 높이 차 ≤ CUP_RIM_TOL_PCT
2. 컵 깊이: 림 평균 대비 CUP_MIN_DEPTH_PCT~CUP_MAX_DEPTH_PCT
3. U자형 검증 (V자 반등 배제):
   - 바닥 위치가 컵 구간의 가운데(CUP_BOTTOM_ZONE)
   - 바닥권(바닥에서 깊이의 25% 이내)에 머문 봉이 컵 길이의 CUP_FLAT_FRAC 이상
   - 컵 구간 종가의 2차 곡선(포물선) 적합 R² ≥ CUP_ROUND_R2 (위로 오목)
4. 핸들: 우림 이후 얕은 눌림 — 핸들 저점이 컵 깊이의 상위 절반(HANDLE_MAX_DEPTH_FRAC)
   유지. 컵 중단 아래로 내려가면 무효.
5. 완성: 우림 이후 HANDLE_MIN_LEN~HANDLE_MAX_LEN 봉 안에 종가가 우림 고가를 상향
   돌파한 날. 형성 중: 핸들 구간 진행 중(무효화 전, 대기 기한 내).

같은 우림을 공유하는 후보 중에는 림 높이 차가 가장 작은 것 하나만 남긴다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from batch import config
from batch.indicators.divergence import find_pivots


@dataclass
class CupPattern:
    kind: str            # pat_cup_handle
    i_left: int          # 좌림
    i_bottom: int        # 컵 바닥
    i_right: int         # 우림
    i_handle: int | None  # 핸들 저점 (핸들이 식별된 경우)
    neckline: float      # 돌파 기준선 (우림 고가)
    completed_at: int | None
    forming: bool
    points: list         # [(idx, price), ...]
    shape: int = 0       # 형태 신뢰도 (shape.grade_shapes가 채움)
    grade: str = "C"

    @property
    def confirmed_at(self) -> int:
        return self.i_right


def _round_ok(closes: np.ndarray) -> bool:
    """컵 구간 종가가 위로 오목한 2차 곡선에 그럴듯하게 맞는가."""
    n = len(closes)
    if n < 10:
        return False
    x = np.arange(n, dtype=float)
    y = closes / closes.mean()  # 스케일 정규화
    coef = np.polyfit(x, y, 2)
    if coef[0] <= 0:  # 위로 볼록(뒤집힌 U)은 컵이 아님
        return False
    fit = np.polyval(coef, x)
    ss_res = float(np.sum((y - fit) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot <= 0:
        return False
    return 1 - ss_res / ss_tot >= config.CUP_ROUND_R2


def detect_cup_handle(ind: pd.DataFrame) -> list[CupPattern]:
    n = len(ind)
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    closes = ind["close"].astype(float).to_numpy()

    pivot_highs, _ = find_pivots(
        pd.Series(highs), config.PAT_PIVOT_LEFT, config.PAT_PIVOT_RIGHT
    )
    pivot_highs = sorted(int(i) for i in pivot_highs)

    out: list[CupPattern] = []
    best_by_rim: dict[int, tuple[float, CupPattern]] = {}  # 우림별 최적 후보

    for ri, r in enumerate(pivot_highs):
        for l in reversed(pivot_highs[:ri]):
            span = r - l
            if span < config.CUP_MIN_LEN:
                continue
            if span > config.CUP_MAX_LEN:
                break
            rim_l, rim_r = highs[l], highs[r]
            if rim_l <= 0:
                continue
            rim_diff_pct = abs(rim_r - rim_l) / rim_l * 100
            if rim_diff_pct > config.CUP_RIM_TOL_PCT:
                continue

            seg_lows = lows[l : r + 1]
            ib = l + int(np.argmin(seg_lows))
            bottom = float(lows[ib])
            rim_avg = (rim_l + rim_r) / 2
            depth_pct = (rim_avg - bottom) / rim_avg * 100
            if not (config.CUP_MIN_DEPTH_PCT <= depth_pct <= config.CUP_MAX_DEPTH_PCT):
                continue

            pos = (ib - l) / span
            z0, z1 = config.CUP_BOTTOM_ZONE
            if not (z0 <= pos <= z1):
                continue

            depth_abs = rim_avg - bottom
            near_bottom = np.sum(seg_lows <= bottom + config.CUP_FLAT_ZONE * depth_abs)
            if near_bottom < max(4, config.CUP_FLAT_FRAC * span):
                continue

            if not _round_ok(closes[l : r + 1]):
                continue

            # 핸들·돌파 스캔 (우림 피벗 확정 이후)
            neckline = float(rim_r)
            invalid_level = bottom + depth_abs * config.HANDLE_MAX_DEPTH_FRAC
            deadline = min(r + config.HANDLE_MAX_LEN, n - 1)
            completed_at = None
            invalidated = False
            handle_low_idx = None
            handle_low = np.inf
            for j in range(r + 1, deadline + 1):
                if lows[j] < handle_low:
                    handle_low, handle_low_idx = float(lows[j]), j
                if closes[j] < invalid_level:
                    invalidated = True  # 핸들이 너무 깊음 → 컵 실패
                    break
                if j - r >= config.HANDLE_MIN_LEN and closes[j] > neckline:
                    completed_at = j
                    break

            forming = bool(
                completed_at is None and not invalidated and deadline == n - 1
                and r + 1 <= n - 1
            )
            if completed_at is None and not forming:
                continue

            points = [(int(l), float(rim_l)), (int(ib), bottom), (int(r), float(rim_r))]
            if handle_low_idx is not None and (completed_at is None or handle_low_idx < completed_at):
                points.append((int(handle_low_idx), handle_low))

            cand = CupPattern(
                kind="pat_cup_handle",
                i_left=int(l), i_bottom=int(ib), i_right=int(r),
                i_handle=int(handle_low_idx) if handle_low_idx is not None else None,
                neckline=neckline,
                completed_at=completed_at,
                forming=forming,
                points=points,
            )
            prev = best_by_rim.get(r)
            if prev is None or rim_diff_pct < prev[0]:
                best_by_rim[r] = (rim_diff_pct, cand)

    used_completion: set[int] = set()
    for _, cand in sorted(best_by_rim.values(), key=lambda t: t[1].i_right):
        if cand.completed_at is not None:
            if cand.completed_at in used_completion:
                continue
            used_completion.add(cand.completed_at)
        out.append(cand)
    return out
