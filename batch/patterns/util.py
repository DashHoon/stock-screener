"""패턴 탐지 공통 유틸 — 피벗 추출, 추세선 적합, 공통 결과 타입."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from batch import config
from batch.indicators.divergence import find_pivots


@dataclass
class PatternHit:
    """모든 패턴 탐지기의 공통 결과 타입.

    kind: pat_* 시그널 키 (완성). 형성 중이면 kind + "_form"으로 sig에 기록된다.
    neckline: 돌파 기준 가격 (차트에 점선으로 표시)
    points: [(idx, price), ...] 차트 꺾은선 좌표
    """
    kind: str
    completed_at: int | None
    forming: bool
    neckline: float
    points: list = field(default_factory=list)   # 시간 오름차순 꺾은선
    points2: list = field(default_factory=list)  # 보조선 (추세선 계열의 아래선 등)
    confirmed_at: int = 0
    shape: int = 0          # 형태 신뢰도 0~100 (shape.grade_shapes가 채움)
    grade: str = "C"        # A(뚜렷)/B(보통)/C(모호)


def price_pivots(ind: pd.DataFrame) -> tuple[list[int], list[int]]:
    """(피벗 고점 인덱스, 피벗 저점 인덱스) — 고가/저가 기준, 표준 패턴 피벗."""
    highs, _ = find_pivots(
        pd.Series(ind["high"].astype(float).to_numpy()),
        config.PAT_PIVOT_LEFT, config.PAT_PIVOT_RIGHT,
    )
    _, lows = find_pivots(
        pd.Series(ind["low"].astype(float).to_numpy()),
        config.PAT_PIVOT_LEFT, config.PAT_PIVOT_RIGHT,
    )
    return sorted(int(i) for i in highs), sorted(int(i) for i in lows)


@dataclass
class Line:
    slope: float      # 가격/봉
    intercept: float  # x=0 기준
    r2: float

    def at(self, x: float) -> float:
        return self.slope * x + self.intercept


def fit_line(xs: list[int], ys: list[float]) -> Line:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if len(x) < 2:
        return Line(0.0, float(y[0]) if len(y) else 0.0, 0.0)
    slope, intercept = np.polyfit(x, y, 1)
    fit = slope * x + intercept
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 if ss_tot <= 0 else 1 - float(np.sum((y - fit) ** 2)) / ss_tot
    return Line(float(slope), float(intercept), r2)


def fit_envelope_line(xs: list[int], ys: list[float], upper: bool) -> Line:
    """추세선 적합 — 기울기는 회귀로 잡고, 선은 극점에 붙인다.

    최소제곱선은 점들의 '한가운데'를 지나므로 고점 절반이 선 위로 삐져나온다.
    사람이 긋는 저항선은 고점들을 스치듯 지나가므로, 회귀 기울기는 그대로 두고
    절편만 밀어 올려(내려) 가장 튀어나온 점에 닿게 한다.

    upper=True면 모든 점이 선 아래(저항선), False면 모두 위(지지선)에 놓인다.
    """
    line = fit_line(xs, ys)
    if len(xs) < 2:
        return line
    resid = [y - line.at(x) for x, y in zip(xs, ys)]
    shift = max(resid) if upper else min(resid)
    return Line(line.slope, line.intercept + shift, line.r2)


def slope_pct(line: Line, ref_price: float) -> float:
    """기울기를 '봉당 %'로 정규화 (가격 규모 무관 비교용)."""
    if ref_price <= 0:
        return 0.0
    return line.slope / ref_price * 100
