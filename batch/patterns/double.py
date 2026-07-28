"""쌍바닥(Double Bottom) / 더블탑(Double Top) 탐지 — ATR 적응형 스윙 기반.

판정 규칙 (쌍바닥 기준, 더블탑은 대칭):
1. ZigZag 스윙 목록(minor·major 두 스케일)에서 **연속 스윙 3개** 저-고-저를 찾는다.
   잔파동은 애초에 스윙이 아니므로 엉뚱한 바닥 연결이 원천 차단된다.
2. 두 바닥 간격은 스케일별 [min, max]봉(DB_GAP), 가격 차이 ≤ PAT_TOL_PCT %
3. 넥라인 = 두 바닥 사이 실제 최고 고가 (가운데 스윙 가격이 아님 — 아웃사이드
   바의 반대편 극값은 스윙에 안 실려 스윙 고점이 실제 최고가보다 낮을 수 있다).
   넥라인이 바닥 평균보다 PAT_MIN_DEPTH_PCT % 이상 높아야 함
4. 완성: 두 번째 바닥 스윙의 확정봉(confirmed_at)부터 PAT_BREAKOUT_WINDOW 봉 안에
   종가가 넥라인을 돌파(쌍바닥=상향, 더블탑=하향)한 첫날 = completed_at.
   확정봉 이후만 스캔하므로 미래 참조가 없다.
5. 형성 중: 두 번째 바닥은 확정됐지만 아직 돌파 전이고, 무효화(쌍바닥: 종가가
   바닥 밑으로 이탈)되지 않았으며 대기 기한이 남아 있는 상태

무효화되면 이벤트 없음. 같은 돌파봉을 공유하는 중복(스케일 간 포함)은 첫 완성만
남긴다. 스케일 간 형성 중 중복은 dedupe_patterns가 정리한다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from batch import config
from batch.patterns.swing import SwingCtx, build_ctx

# 두 바닥(꼭대기) 사이 간격 [min, max]봉 — 스케일별. 기존 PAT_MIN_GAP/MAX_GAP
# (10/60)을 대체한다. minor 하한 10은 이식 전과 동일 — 스윙 임계를 넘는 진짜
# 반등이라도 5봉짜리 초미니 W는 일봉 스크리너에선 잡음이다. 상한은 스케일
# 성격에 맞게 넓혔다 (기존 60봉 상한은 큰 구조를 원천 차단했음).
DB_GAP = {"minor": (10, 90), "major": (20, 250)}


@dataclass
class DoublePattern:
    kind: str            # pat_double_bottom | pat_double_top
    i1: int              # 첫 바닥(꼭대기) 스윙 인덱스
    ip: int              # 사이 반등 고점(눌림 저점) 스윙 인덱스 — 넥라인 기준점
    i2: int              # 두 번째 바닥(꼭대기) 스윙 인덱스
    neckline: float
    confirmed_at: int    # i2 스윙 확정봉 (반전 임계를 넘어선 봉)
    completed_at: int | None  # 넥라인 돌파일 (None = 미완성)
    forming: bool        # 오늘 기준 '형성 중' 상태인가
    points: list         # [(idx, price), ...] 차트 마킹용 꺾은선 좌표
    shape: int = 0       # 형태 신뢰도 (shape.grade_shapes가 채움)
    grade: str = "C"


def _detect_one_side(ctx: SwingCtx, *, bottom: bool) -> list[DoublePattern]:
    n = len(ctx.closes)
    closes = ctx.closes
    tol_pct = config.PAT_TOL_PCT

    out: list[DoublePattern] = []
    used_completion: set[int] = set()  # 같은 돌파봉 공유 중복 제거 (스케일 간 공유)
    want = (False, True, False) if bottom else (True, False, True)

    for scale in ("minor", "major"):
        min_gap, max_gap = DB_GAP[scale]
        swings = ctx.swings(scale)
        for k in range(len(swings) - 2):
            s1, sp, s2 = swings[k], swings[k + 1], swings[k + 2]
            if (s1.is_high, sp.is_high, s2.is_high) != want:
                continue
            if s2.confirmed_at is None:
                continue  # 잠정 스윙 — 구조 미확정 (미래 참조 방지)

            gap = s2.idx - s1.idx
            if not (min_gap <= gap <= max_gap):
                continue
            pa, pb = s1.price, s2.price
            if pa <= 0 or abs(pb - pa) / pa * 100 > tol_pct:
                continue

            # 넥라인은 스윙 가격이 아니라 실제 배열 극값으로 잰다. 아웃사이드 바
            # (반전 확정봉)의 반대편 극값은 스윙 구조에 안 실리므로, 가운데 스윙
            # 가격이 두 바닥 사이 실제 최고가보다 낮을 수 있다 (실측 2.7%) —
            # 그대로 쓰면 돌파 기준이 낮아져 조기 완성 판정이 된다.
            mid = slice(s1.idx + 1, s2.idx)
            if bottom:
                ip_idx = s1.idx + 1 + int(np.argmax(ctx.highs[mid]))
                neckline = float(ctx.highs[ip_idx])
            else:
                ip_idx = s1.idx + 1 + int(np.argmin(ctx.lows[mid]))
                neckline = float(ctx.lows[ip_idx])
            base = (pa + pb) / 2
            if bottom:
                depth = (neckline - base) / base * 100
            else:
                depth = (base - neckline) / neckline * 100
            if depth < config.PAT_MIN_DEPTH_PCT:
                continue

            confirmed_at = int(s2.confirmed_at)
            completed_at = None
            invalidated = False
            deadline = min(confirmed_at + config.PAT_BREAKOUT_WINDOW, n - 1)
            floor = min(pa, pb) if bottom else max(pa, pb)
            for j in range(confirmed_at, deadline + 1):
                c = closes[j]
                if bottom:
                    if c > neckline:
                        completed_at = int(j)
                        break
                    if c < floor * (1 - tol_pct / 100):
                        invalidated = True
                        break
                else:
                    if c < neckline:
                        completed_at = int(j)
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
                    i1=int(s1.idx), ip=int(ip_idx), i2=int(s2.idx),
                    neckline=neckline,
                    confirmed_at=confirmed_at,
                    completed_at=completed_at,
                    forming=forming,
                    points=[
                        (int(s1.idx), float(pa)),
                        (int(ip_idx), neckline),
                        (int(s2.idx), float(pb)),
                    ],
                )
            )
    return out


def detect_double_patterns(ind: pd.DataFrame, ctx: SwingCtx | None = None) -> list[DoublePattern]:
    """쌍바닥 + 더블탑 전체 탐지 (시간순)."""
    if ctx is None:
        ctx = build_ctx(ind)
    result = _detect_one_side(ctx, bottom=True) + _detect_one_side(ctx, bottom=False)
    result.sort(key=lambda p: p.completed_at if p.completed_at is not None else p.confirmed_at)
    return result
