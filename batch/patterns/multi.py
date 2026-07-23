"""피벗 시퀀스 기반 반전 패턴: 헤드앤숄더/역H&S, 3중바닥/트리플탑."""

import numpy as np
import pandas as pd

from batch import config
from batch.patterns.util import PatternHit, fit_line, price_pivots

HS_SHOULDER_TOL_PCT = 8.0    # 양 어깨 높이 차 허용 %
HS_HEAD_MIN_PCT = 3.0        # 머리가 어깨 평균보다 최소 이만큼 높아야(낮아야) 함
HS_MAX_SPAN = 140            # 첫 어깨→끝 어깨 최대 봉수
HS_BREAK_WINDOW = 40

TRI_TOL_PCT = 3.5            # 3중바닥/트리플탑: 세 극값 유사 허용 %
TRI_MIN_SPAN = 20
TRI_MAX_SPAN = 120
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


def detect_head_shoulders(ind: pd.DataFrame) -> list[PatternHit]:
    """H&S 탑(하락 반전) / 역H&S(상승 반전).

    탑: 피벗 고점 3개 (어깨-머리-어깨) + 사이 저점 2개로 넥라인.
    완성 = 종가가 넥라인(연장선) 아래로 이탈. 역H&S는 대칭.
    """
    n = len(ind)
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    closes = ind["close"].astype(float).to_numpy()
    ph, pl = price_pivots(ind)

    out: list[PatternHit] = []

    def scan(tops: bool):
        peaks = ph if tops else pl
        ext = highs if tops else lows
        used: set[int] = set()
        for i in range(len(peaks) - 2):
            s1, hd, s2 = peaks[i], peaks[i + 1], peaks[i + 2]
            if s2 - s1 > HS_MAX_SPAN:
                continue
            v1, vh, v2 = ext[s1], ext[hd], ext[s2]
            if v1 <= 0:
                continue
            sh_avg = (v1 + v2) / 2
            if abs(v2 - v1) / v1 * 100 > HS_SHOULDER_TOL_PCT:
                continue
            prominence = (vh - sh_avg) / sh_avg * 100 if tops else (sh_avg - vh) / sh_avg * 100
            if prominence < HS_HEAD_MIN_PCT:
                continue
            # 넥라인: 어깨-머리 사이 반대편 극값 2개
            opp = lows if tops else highs
            seg1 = slice(s1 + 1, hd)
            seg2 = slice(hd + 1, s2)
            if seg1.stop <= seg1.start or seg2.stop <= seg2.start:
                continue
            n1 = s1 + 1 + int(np.argmin(opp[seg1]) if tops else np.argmax(opp[seg1]))
            n2 = hd + 1 + int(np.argmin(opp[seg2]) if tops else np.argmax(opp[seg2]))
            neck = fit_line([n1, n2], [float(opp[n1]), float(opp[n2])])

            start = s2 + config.PAT_PIVOT_RIGHT
            if start >= n:
                continue
            deadline = min(s2 + HS_BREAK_WINDOW, n - 1)
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
                    (int(s1), float(v1)), (int(n1), float(opp[n1])),
                    (int(hd), float(vh)), (int(n2), float(opp[n2])),
                    (int(s2), float(v2)),
                ],
                confirmed_at=int(s2 + config.PAT_PIVOT_RIGHT),
            ))

    scan(tops=True)
    scan(tops=False)
    return out


def detect_triple(ind: pd.DataFrame) -> list[PatternHit]:
    """3중바닥(상승 반전) / 트리플탑(하락 반전) — 유사 극값 3개 + 넥라인 돌파."""
    n = len(ind)
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    closes = ind["close"].astype(float).to_numpy()
    ph, pl = price_pivots(ind)

    out: list[PatternHit] = []

    def scan(bottoms: bool):
        pivots = pl if bottoms else ph
        ext = lows if bottoms else highs
        opp = highs if bottoms else lows
        used: set[int] = set()
        for i in range(len(pivots) - 2):
            a, b, c = pivots[i], pivots[i + 1], pivots[i + 2]
            span = c - a
            if not (TRI_MIN_SPAN <= span <= TRI_MAX_SPAN):
                continue
            va, vb, vc = ext[a], ext[b], ext[c]
            if va <= 0:
                continue
            vmax, vmin = max(va, vb, vc), min(va, vb, vc)
            if (vmax - vmin) / va * 100 > TRI_TOL_PCT:
                continue
            mid = slice(a + 1, c)
            neck_i = a + 1 + int(np.argmax(opp[mid]) if bottoms else np.argmin(opp[mid]))
            neckline = float(opp[neck_i])
            base = (va + vb + vc) / 3
            depth = (neckline - base) / base * 100 if bottoms else (base - neckline) / neckline * 100
            if depth < TRI_MIN_DEPTH_PCT:
                continue

            start = c + config.PAT_PIVOT_RIGHT
            if start >= n:
                continue
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

            def _mid(lo, hi):
                seg = slice(lo + 1, hi)
                k = lo + 1 + int(np.argmax(opp[seg]) if bottoms else np.argmin(opp[seg]))
                return int(k), float(opp[k])

            m1 = _mid(a, b)
            m2 = _mid(b, c)
            out.append(PatternHit(
                kind="pat_triple_bottom" if bottoms else "pat_triple_top",
                completed_at=completed_at,
                forming=forming,
                neckline=neckline,
                points=[(int(a), float(va)), m1, (int(b), float(vb)), m2, (int(c), float(vc))],
                confirmed_at=int(c + config.PAT_PIVOT_RIGHT),
            ))

    scan(bottoms=True)
    scan(bottoms=False)
    return out
