"""추세선 계열 패턴: 삼각형 3종, 쐐기 2종, 브로드닝.

피벗 고점열·저점열에 각각 직선을 적합해 기울기 조합으로 분류한다.
- 상승삼각형: 위 수평 + 아래 상승 → 위 돌파 시 완성 (상승)
- 하락삼각형: 아래 수평 + 위 하락 → 아래 이탈 시 완성 (하락)
- 삼각수렴: 위 하락 + 아래 상승 → 돌파 방향에 따라 up/down
- 상승쐐기: 둘 다 상승하며 수렴 → 아래 이탈 시 완성 (하락)
- 하락쐐기: 둘 다 하락하며 수렴 → 위 돌파 시 완성 (상승)
- 브로드닝: 위 상승 + 아래 하락(확대) → 아래 이탈 시 완성 (하락)

기울기 판정: 봉당 % (FLAT_EPS 이내 = 수평). 수렴형은 폭이 25% 이상 줄어야 함.
"""

import pandas as pd

from batch import config
from batch.patterns.util import (
    PatternHit, fit_envelope_line, fit_line, price_pivots, slope_pct,
)

FLAT_EPS = 0.08    # 봉당 % — 이하면 수평 취급
TREND_EPS = 0.12   # 봉당 % — 이상이어야 추세로 취급
MAX_STRUCT_SPAN = 100
MIN_STRUCT_SPAN = 20
MIN_R2 = 0.45
CONVERGE_RATIO = 0.75   # 끝 폭 ≤ 시작 폭 × 이 값 (수렴형)
DIVERGE_RATIO = 1.35    # 끝 폭 ≥ 시작 폭 × 이 값 (브로드닝)
BREAK_WINDOW = 25


def detect_trendline_patterns(ind: pd.DataFrame) -> list[PatternHit]:
    n = len(ind)
    closes = ind["close"].astype(float).to_numpy()
    highs = ind["high"].astype(float).to_numpy()
    lows = ind["low"].astype(float).to_numpy()
    ph, pl = price_pivots(ind)

    out: list[PatternHit] = []
    used: set[tuple[str, int]] = set()

    # 앵커: 각 피벗(고/저 합집합)마다 직전 구조를 평가
    anchors = sorted(set(ph) | set(pl))
    for anchor in anchors:
        lo = anchor - MAX_STRUCT_SPAN
        hs = [i for i in ph if lo <= i <= anchor][-4:]
        ls = [i for i in pl if lo <= i <= anchor][-4:]
        if len(hs) < 3 or len(ls) < 3:
            continue
        start = min(hs[0], ls[0])
        span = anchor - start
        if span < MIN_STRUCT_SPAN:
            continue
        # 저항선은 고점 위, 지지선은 저점 아래에 놓이도록 극점에 붙인다
        upper = fit_envelope_line(hs, [highs[i] for i in hs], upper=True)
        lower = fit_envelope_line(ls, [lows[i] for i in ls], upper=False)
        if upper.r2 < MIN_R2 or lower.r2 < MIN_R2:
            continue
        ref = float(closes[anchor])
        su, sl = slope_pct(upper, ref), slope_pct(lower, ref)
        w_start = upper.at(start) - lower.at(start)
        w_end = upper.at(anchor) - lower.at(anchor)
        if w_start <= 0:
            continue
        converging = w_end <= w_start * CONVERGE_RATIO
        diverging = w_end >= w_start * DIVERGE_RATIO

        kind = None
        break_up: bool | None = None  # True=위 돌파가 완성, False=아래 이탈, None=양방향(수렴)
        if abs(su) <= FLAT_EPS and sl >= TREND_EPS:
            kind, break_up = "pat_tri_asc", True
        elif abs(sl) <= FLAT_EPS and su <= -TREND_EPS:
            kind, break_up = "pat_tri_desc", False
        elif su <= -TREND_EPS and sl >= TREND_EPS and converging:
            kind, break_up = "pat_tri_sym", None
        elif su >= TREND_EPS and sl >= TREND_EPS and converging and sl > su:
            kind, break_up = "pat_wedge_rise", False
        elif su <= -TREND_EPS and sl <= -TREND_EPS and converging and su < sl:
            kind, break_up = "pat_wedge_fall", True
        elif su >= TREND_EPS and sl <= -TREND_EPS and diverging:
            kind, break_up = "pat_broadening", False
        if kind is None:
            continue

        # 돌파 스캔 (앵커 피벗 확정 이후)
        scan_from = anchor + config.PAT_PIVOT_RIGHT
        if scan_from >= n:
            continue
        deadline = min(anchor + BREAK_WINDOW, n - 1)
        completed_at = None
        completed_kind = kind
        for j in range(scan_from, deadline + 1):
            c = closes[j]
            up_lvl, dn_lvl = upper.at(j), lower.at(j)
            if up_lvl <= dn_lvl:  # 추세선 교차(apex) 이후는 무효
                break
            if break_up in (True, None) and c > up_lvl:
                completed_at = j
                completed_kind = kind + ("_up" if break_up is None else "")
                break
            if break_up in (False, None) and c < dn_lvl:
                completed_at = j
                completed_kind = kind + ("_down" if break_up is None else "")
                break
        forming = bool(completed_at is None and deadline == n - 1)
        if completed_at is None and not forming:
            continue
        key = (completed_kind, completed_at if completed_at is not None else -1)
        if completed_at is not None:
            if key in used:
                continue
            used.add(key)

        # 적합한 추세선을 '직선 + 돌파 지점까지 연장'해서 그린다.
        # 실제 고점들을 지그재그로 이으면 꺾인 선이라 어디를 돌파했는지 안 보인다.
        # 돌파 판정도 이 직선(upper.at/lower.at)으로 하므로 화면과 판정이 일치한다.
        # 직선이 모든 고점을 정확히 지나지는 않지만 추세를 대표하면 충분하다.
        x0 = int(start)
        x1 = int(completed_at if completed_at is not None else min(deadline, n - 1))
        if x1 <= x0:
            continue
        pts_u = [(x0, float(upper.at(x0))), (x1, float(upper.at(x1)))]
        pts_l = [(x0, float(lower.at(x0))), (x1, float(lower.at(x1)))]
        neck_ref = completed_at if completed_at is not None else anchor
        neckline = upper.at(neck_ref) if (break_up in (True, None)) else lower.at(neck_ref)
        out.append(PatternHit(
            kind=completed_kind if completed_at is not None else kind,
            completed_at=completed_at,
            forming=forming,
            neckline=float(neckline),
            points=pts_u,     # 위 추세선
            points2=pts_l,    # 아래 추세선
            confirmed_at=int(anchor),
        ))
    return out
