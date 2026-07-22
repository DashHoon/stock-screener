"""쌍바닥(Double Bottom) / 더블탑(Double Top) 탐지.

판정 규칙 (쌍바닥 기준, 더블탑은 대칭):
1. 가격 저가(low)에서 피벗 저점을 찾는다 (좌우 PAT_PIVOT_LEFT/RIGHT)
2. 연속한 피벗 저점 쌍 (L1, L2):
   - 간격 PAT_MIN_GAP ~ PAT_MAX_GAP 봉
   - 두 바닥 가격 차이 ≤ PAT_TOL_PCT %
3. 사이 최고 고가(P) = 넥라인. 넥라인이 바닥 평균보다 PAT_MIN_DEPTH_PCT % 이상 높아야 함
4. 완성: L2 피벗 확정일(L2+PAT_PIVOT_RIGHT) 이후 PAT_BREAKOUT_WINDOW 봉 안에
   종가가 넥라인을 돌파(쌍바닥=상향, 더블탑=하향)한 첫날 = completed_at
5. 형성 중: L2는 확정됐지만 아직 돌파 전이고, 무효화(쌍바닥: 종가가 바닥 밑으로
   이탈)되지 않았으며 대기 기한이 남아 있는 상태

무효화되면 이벤트 없음. 같은 바닥을 공유하는 중복은 첫 완성만 남긴다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from batch import config
from batch.indicators.divergence import find_pivots


@dataclass
class DoublePattern:
    kind: str            # pat_double_bottom | pat_double_top
    i1: int              # 첫 바닥(꼭대기) 인덱스
    ip: int              # 사이 반등 고점(눌림 저점) 인덱스 — 넥라인 기준점
    i2: int              # 두 번째 바닥(꼭대기) 인덱스
    neckline: float
    confirmed_at: int    # i2 피벗 확정일 (i2 + PAT_PIVOT_RIGHT)
    completed_at: int | None  # 넥라인 돌파일 (None = 미완성)
    forming: bool        # 오늘 기준 '형성 중' 상태인가


def _detect_one_side(
    ind: pd.DataFrame, *, bottom: bool,
    left: int, right: int, tol_pct: float,
    min_gap: int, max_gap: int, min_depth_pct: float, breakout_window: int,
) -> list[DoublePattern]:
    n = len(ind)
    lows = ind["low"].astype(float).to_numpy()
    highs = ind["high"].astype(float).to_numpy()
    closes = ind["close"].astype(float).to_numpy()

    ext = lows if bottom else highs          # 바닥/꼭대기 판정용 극값 시리즈
    series = pd.Series(ext)
    highs_p, lows_p = find_pivots(series, left, right)
    pivots = sorted(lows_p if bottom else highs_p)

    out: list[DoublePattern] = []
    used_completion: set[int] = set()

    for a, b in zip(pivots[:-1], pivots[1:]):
        gap = b - a
        if not (min_gap <= gap <= max_gap):
            continue
        pa, pb = ext[a], ext[b]
        if pa <= 0 or abs(pb - pa) / pa * 100 > tol_pct:
            continue

        mid = slice(a + 1, b)
        if bottom:
            ip = a + 1 + int(np.argmax(highs[mid]))
            neckline = float(highs[ip])
            depth = (neckline - (pa + pb) / 2) / ((pa + pb) / 2) * 100
        else:
            ip = a + 1 + int(np.argmin(lows[mid]))
            neckline = float(lows[ip])
            depth = ((pa + pb) / 2 - neckline) / neckline * 100
        if depth < min_depth_pct:
            continue

        confirmed_at = b + right
        if confirmed_at >= n:
            continue

        completed_at = None
        invalidated = False
        deadline = min(confirmed_at + breakout_window, n - 1)
        floor = min(pa, pb) if bottom else max(pa, pb)
        for j in range(confirmed_at, deadline + 1):
            c = closes[j]
            if bottom:
                if c > neckline:
                    completed_at = j
                    break
                if c < floor * (1 - tol_pct / 100):
                    invalidated = True
                    break
            else:
                if c < neckline:
                    completed_at = j
                    break
                if c > floor * (1 + tol_pct / 100):
                    invalidated = True
                    break

        forming = bool(
            completed_at is None
            and not invalidated
            and deadline == n - 1  # 대기 기한이 아직 남아 있음 (차트 끝까지 미돌파)
        )
        if completed_at is None and not forming:
            continue
        if completed_at is not None:
            if completed_at in used_completion:
                continue  # 같은 돌파를 공유하는 중복 패턴 제거
            used_completion.add(completed_at)

        out.append(
            DoublePattern(
                kind="pat_double_bottom" if bottom else "pat_double_top",
                i1=int(a), ip=int(ip), i2=int(b),
                neckline=neckline,
                confirmed_at=int(confirmed_at),
                completed_at=completed_at,
                forming=forming,
            )
        )
    return out


def detect_double_patterns(ind: pd.DataFrame) -> list[DoublePattern]:
    """쌍바닥 + 더블탑 전체 탐지 (시간순)."""
    kw = dict(
        left=config.PAT_PIVOT_LEFT, right=config.PAT_PIVOT_RIGHT,
        tol_pct=config.PAT_TOL_PCT,
        min_gap=config.PAT_MIN_GAP, max_gap=config.PAT_MAX_GAP,
        min_depth_pct=config.PAT_MIN_DEPTH_PCT,
        breakout_window=config.PAT_BREAKOUT_WINDOW,
    )
    result = _detect_one_side(ind, bottom=True, **kw) + _detect_one_side(
        ind, bottom=False, **kw
    )
    result.sort(key=lambda p: p.completed_at if p.completed_at is not None else p.confirmed_at)
    return result
