"""스윙 시퀀스 기반 반전 패턴: 헤드앤숄더/역H&S, 3중바닥/트리플탑.

ATR 적응형 ZigZag 스윙(minor·major 두 스케일)의 **연속 5개 창**으로 판정한다:
- H&S 탑: 고-저-고-저-고 = 어깨·넥·머리·넥·어깨 (역H&S는 대칭)
- 3중바닥: 저-고-저-고-저 = 극값 3 + 중간 반등 2 (트리플탑은 대칭)

구조 확정 = 마지막 극점 스윙의 confirmed_at (반전 임계를 넘어선 봉).
돌파(completed_at) 스캔은 반드시 그 봉부터 시작하므로 미래 참조가 없다.
H&S와 트리플탑은 같은 5-스윙을 두고 경합할 수 있다 — kind가 달라 공존한다
(현행 동작 유지).
"""

import numpy as np
import pandas as pd

from batch.patterns.swing import SwingCtx, build_ctx
from batch.patterns.util import PatternHit, fit_line


def _true_extreme(arr: np.ndarray, lo: int, hi: int, is_max: bool) -> tuple[int, float]:
    """(lo, hi) 열린 구간의 실제 극값 (idx, price). 아웃사이드 바의 반대편 극값이
    스윙 구조에 안 실리는 공백을 메운다 — 넥라인은 실제 배열 극값으로 잰다."""
    seg = slice(lo + 1, hi)
    k = lo + 1 + int(np.argmax(arr[seg]) if is_max else np.argmin(arr[seg]))
    return int(k), float(arr[k])

HS_SHOULDER_TOL_PCT = 8.0    # 양 어깨 높이 차 허용 %
HS_HEAD_MIN_PCT = 3.0        # 머리가 어깨 평균보다 최소 이만큼 높아야(낮아야) 함
HS_MAX_SPAN = 140            # 첫 어깨→끝 어깨 최대 봉수 (minor)
HS_MAX_SPAN_MAJOR = 300      # (major)
HS_BREAK_WINDOW = 40

TRI_TOL_PCT = 3.5            # 3중바닥/트리플탑: 세 극값 유사 허용 %
TRI_SPAN = {"minor": (20, 120), "major": (40, 300)}  # 첫 극값→끝 극값 봉수 범위
TRI_MIN_DEPTH_PCT = 5.0
TRI_BREAK_WINDOW = 40


def _scan_break(closes, start, deadline, level_fn, upward, invalid_fn=None):
    """start~deadline에서 돌파/무효를 스캔. (completed_at, invalidated)"""
    for j in range(start, deadline + 1):
        c = closes[j]
        lvl = level_fn(j)
        if upward and c > lvl:
            return j, False
        if not upward and c < lvl:
            return j, False
        if invalid_fn is not None and invalid_fn(j, c):
            return None, True
    return None, False


def detect_head_shoulders(ind: pd.DataFrame, ctx: SwingCtx | None = None) -> list[PatternHit]:
    """H&S 탑(하락 반전) / 역H&S(상승 반전).

    탑: 연속 스윙 5개 고-저-고-저-고 (어깨-넥-머리-넥-어깨). 넥라인은 두 중간
    스윙을 잇는 직선. 완성 = 종가가 넥라인(연장선) 아래로 이탈. 역H&S는 대칭.
    """
    if ctx is None:
        ctx = build_ctx(ind)
    n = len(ctx.closes)
    closes = ctx.closes

    out: list[PatternHit] = []

    def scan(tops: bool):
        want = (tops, not tops, tops, not tops, tops)  # is_high 시퀀스
        used: set[int] = set()  # 같은 돌파봉 공유 중복 제거 (스케일 간 공유)
        for scale in ("minor", "major"):
            max_span = HS_MAX_SPAN if scale == "minor" else HS_MAX_SPAN_MAJOR
            swings = ctx.swings(scale)
            for i in range(len(swings) - 4):
                s1, m1, hd, m2, s2 = swings[i:i + 5]
                if tuple(s.is_high for s in (s1, m1, hd, m2, s2)) != want:
                    continue
                if s2.confirmed_at is None:
                    continue  # 잠정 스윙 — 구조 미확정 (미래 참조 방지)
                if s2.idx - s1.idx > max_span:
                    continue
                v1, vh, v2 = s1.price, hd.price, s2.price
                if v1 <= 0:
                    continue
                sh_avg = (v1 + v2) / 2
                if abs(v2 - v1) / v1 * 100 > HS_SHOULDER_TOL_PCT:
                    continue
                prominence = (
                    (vh - sh_avg) / sh_avg * 100 if tops else (sh_avg - vh) / sh_avg * 100
                )
                if prominence < HS_HEAD_MIN_PCT:
                    continue
                # 넥라인: 어깨-머리 사이 반대편 실제 극값 2개를 잇는 직선
                opp = ctx.lows if tops else ctx.highs
                n1_idx, n1_val = _true_extreme(opp, s1.idx, hd.idx, is_max=not tops)
                n2_idx, n2_val = _true_extreme(opp, hd.idx, s2.idx, is_max=not tops)
                neck = fit_line([n1_idx, n2_idx], [n1_val, n2_val])

                start = int(s2.confirmed_at)
                deadline = min(start + HS_BREAK_WINDOW, n - 1)
                completed_at, invalidated = _scan_break(
                    closes, start, deadline,
                    level_fn=neck.at, upward=not tops,
                    invalid_fn=(lambda j, c: c > vh) if tops else (lambda j, c: c < vh),
                )
                forming = bool(completed_at is None and not invalidated and deadline == n - 1)
                if completed_at is None and not forming:
                    continue
                if completed_at is not None:
                    if completed_at in used:
                        continue
                    used.add(completed_at)
                neckline_val = neck.at(completed_at if completed_at is not None else n - 1)
                out.append(PatternHit(
                    kind="pat_hs_top" if tops else "pat_hs_inv",
                    completed_at=completed_at,
                    forming=forming,
                    neckline=float(neckline_val),
                    points=[
                        (int(s1.idx), float(v1)), (n1_idx, n1_val),
                        (int(hd.idx), float(vh)), (n2_idx, n2_val),
                        (int(s2.idx), float(v2)),
                    ],
                    confirmed_at=start,
                ))

    scan(tops=True)
    scan(tops=False)
    return out


def detect_triple(ind: pd.DataFrame, ctx: SwingCtx | None = None) -> list[PatternHit]:
    """3중바닥(상승 반전) / 트리플탑(하락 반전).

    연속 스윙 5개 저-고-저-고-저(3중바닥)에서 유사 극값 3개 + 넥라인 돌파.
    넥라인 = 두 중간 스윙 중 높은(트리플탑은 낮은) 쪽 가격.
    """
    if ctx is None:
        ctx = build_ctx(ind)
    n = len(ctx.closes)
    closes = ctx.closes

    out: list[PatternHit] = []

    def scan(bottoms: bool):
        want = (not bottoms, bottoms, not bottoms, bottoms, not bottoms)  # is_high 시퀀스
        used: set[int] = set()  # 같은 돌파봉 공유 중복 제거 (스케일 간 공유)
        for scale in ("minor", "major"):
            min_span, max_span = TRI_SPAN[scale]
            swings = ctx.swings(scale)
            for i in range(len(swings) - 4):
                sa, m1, sb, m2, sc = swings[i:i + 5]
                if tuple(s.is_high for s in (sa, m1, sb, m2, sc)) != want:
                    continue
                if sc.confirmed_at is None:
                    continue  # 잠정 스윙 — 구조 미확정 (미래 참조 방지)
                span = sc.idx - sa.idx
                if not (min_span <= span <= max_span):
                    continue
                va, vb, vc = sa.price, sb.price, sc.price
                if va <= 0:
                    continue
                vmax, vmin = max(va, vb, vc), min(va, vb, vc)
                if (vmax - vmin) / va * 100 > TRI_TOL_PCT:
                    continue
                # 넥라인: 첫~끝 극값 사이 반대편 실제 극값 (스윙 가격이 아니라
                # 배열 극값 — 아웃사이드 바 공백 방어, _true_extreme 주석 참고)
                opp_arr = ctx.highs if bottoms else ctx.lows
                nk_i1, nk_v1 = _true_extreme(opp_arr, sa.idx, sb.idx, is_max=bottoms)
                nk_i2, nk_v2 = _true_extreme(opp_arr, sb.idx, sc.idx, is_max=bottoms)
                neckline = float(max(nk_v1, nk_v2) if bottoms else min(nk_v1, nk_v2))
                base = (va + vb + vc) / 3
                depth = (
                    (neckline - base) / base * 100 if bottoms
                    else (base - neckline) / neckline * 100
                )
                if depth < TRI_MIN_DEPTH_PCT:
                    continue

                start = int(sc.confirmed_at)
                deadline = min(start + TRI_BREAK_WINDOW, n - 1)
                floor = vmin if bottoms else vmax
                completed_at, invalidated = _scan_break(
                    closes, start, deadline,
                    level_fn=lambda j: neckline, upward=bottoms,
                    invalid_fn=(
                        (lambda j, cl: cl < floor * 0.97) if bottoms
                        else (lambda j, cl: cl > floor * 1.03)
                    ),
                )
                forming = bool(completed_at is None and not invalidated and deadline == n - 1)
                if completed_at is None and not forming:
                    continue
                if completed_at is not None:
                    if completed_at in used:
                        continue
                    used.add(completed_at)

                out.append(PatternHit(
                    kind="pat_triple_bottom" if bottoms else "pat_triple_top",
                    completed_at=completed_at,
                    forming=forming,
                    neckline=neckline,
                    points=[
                        (int(sa.idx), float(va)), (nk_i1, nk_v1),
                        (int(sb.idx), float(vb)), (nk_i2, nk_v2),
                        (int(sc.idx), float(vc)),
                    ],
                    confirmed_at=start,
                ))

    scan(bottoms=True)
    scan(bottoms=False)
    return out
