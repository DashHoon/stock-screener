"""패턴 '형태 신뢰도' 점수.

패턴 탐지의 본질은 수익 예측이 아니라 **모양 인식**이다. 우리가 "쌍바닥"이라고
표시했을 때 그것이 실제로 교과서적인 쌍바닥 모양인가 — 그 확신도를 점수화한다.
(수익률·백테스트는 사용자가 보고 판단할 영역이므로 여기에 섞지 않는다.)

세 가지 기하학적 관점으로 채점한다:

1. 꺾은선 적합도 (fit, 45점)
   차트에 그리는 꺾은선(points)을 실제 종가가 얼마나 충실히 따라갔는가.
   같은 "쌍바닥"이라도 가격이 꺾은선 주변에서 깔끔하게 움직였으면 뚜렷한 W이고,
   제멋대로 튀었으면 억지로 끼워 맞춘 모양이다.

2. 대칭성 (symmetry, 30점)
   같은 역할을 하는 극점들(쌍바닥의 두 바닥, 헤드앤숄더의 양 어깨 등)의
   가격이 서로 얼마나 비슷한가. 교과서 패턴일수록 수평에 가깝다.

3. 돌출도 (prominence, 25점)
   넥라인 대비 패턴의 진폭이 충분한가. 진폭이 미미하면 잡음에 가깝다.

등급: A(뚜렷) ≥ 70, B(보통) ≥ 50, C(모호) 미만.
"""

import numpy as np
import pandas as pd

SHAPE_A = 70   # 기준선이 없는 패턴의 기본 컷
SHAPE_B = 50

# 종류별 등급 기준선 (B컷, A컷). 계열마다 점수 스케일이 달라 절대값으로 비교하면
# 쐐기는 늘 A, 플래그는 늘 C가 된다. 그래서 "같은 패턴 종류 안에서 얼마나 뚜렷한가"로
# 정규화한다 — 323종목 34,035건 표본의 35/70 백분위
# (2026-07-28, 확대 쐐기 2종 추가 후 재측정. 신규 2종이 1,161건이고 나머지 증가분은
#  그 사이 캐시에 쌓인 봉 때문이다. 기존 종류의 백분위는 한 종류도 빠짐없이 이전과
#  동일하게 나와 값을 그대로 두었고, 신규 2종과 누락돼 있던 pat_tri_sym만 추가했다.)
# pat_tri_sym은 '형성 중' 전용 kind다 — 완성되면 out_kind가 _up/_down으로 갈린다.
# 표에 없어 기본 컷(50,70)으로 떨어지는 바람에 형성 중 삼각수렴이 96.6% A등급이었다.
# 표본이 29건으로 작아 백분위가 흔들릴 수 있으므로 다음 재측정 때 확인할 것.
SHAPE_CUTS = {
    "pat_broadening": (76, 87),
    "pat_bwedge_fall": (79, 90),   # 2026-07-28 추세 잠식 게이트 추가 후 재측정
    "pat_bwedge_rise": (74, 85),
    "pat_cup_handle": (52, 64),
    "pat_diamond": (34, 55),
    "pat_double_bottom": (67, 77),
    "pat_double_top": (65, 76),
    "pat_flag_bear": (52, 67),
    "pat_flag_bull": (54, 73),
    "pat_hs_inv": (60, 69),
    "pat_hs_top": (57, 68),
    "pat_round_bottom": (62, 71),
    "pat_round_top": (68, 77),
    "pat_tri_asc": (56, 68),
    "pat_tri_desc": (74, 86),
    "pat_tri_sym": (75, 88),          # 형성 중 전용 (완성 시 _up/_down으로 분리)
    "pat_tri_sym_down": (70, 82),
    "pat_tri_sym_up": (74, 86),
    "pat_triple_bottom": (71, 78),
    "pat_triple_top": (70, 77),
    "pat_wedge_fall": (77, 88),
    "pat_wedge_rise": (73, 84),
}

# 같은 역할의 극점이 반복되어 '수평 대칭'을 따질 수 있는 패턴들.
# (쌍바닥의 두 바닥, H&S의 양 어깨, 컵·라운드의 좌우 림 …)
# 다이아몬드는 꺾은선의 점들이 서로 역할이 달라 대칭성을 적용하지 않는다.
# (플래그는 고점선·저점선 채널이라 아래 채널 채점 경로를 탄다)
SYMMETRIC_KINDS = frozenset({
    "pat_double_bottom", "pat_double_top",
    "pat_triple_bottom", "pat_triple_top",
    "pat_hs_top", "pat_hs_inv",
    "pat_round_bottom", "pat_round_top",
    "pat_cup_handle",
})


def _fit_score(closes: np.ndarray, points: list) -> float:
    """실제 종가가 꺾은선을 따라간 정도 (0~1). 편차를 패턴 진폭으로 정규화."""
    if len(points) < 2:
        return 0.0
    xs = [int(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    i0, i1 = xs[0], xs[-1]
    if i1 <= i0 or i1 >= len(closes):
        return 0.0
    grid = np.arange(i0, i1 + 1)
    ideal = np.interp(grid, xs, ys)          # 꺾은선을 봉 단위로 펼침
    actual = closes[i0 : i1 + 1]
    amp = max(ys) - min(ys)                  # 패턴 진폭 = 허용 편차의 기준
    if amp <= 0:
        return 0.0
    # 평균 절대편차가 진폭의 25%를 넘으면 0점, 5% 이하면 만점
    dev = float(np.mean(np.abs(actual - ideal))) / amp
    return float(np.clip((0.25 - dev) / 0.20, 0.0, 1.0))


def _symmetry_score(points: list) -> float | None:
    """같은 역할 극점들의 가격 유사도 (0~1). 극점이 부족하면 None(해당 없음)."""
    if len(points) < 3:
        return None
    ys = [float(p[1]) for p in points]
    # 꺾은선은 극점이 번갈아 나타난다 — 한 칸씩 건너뛴 것끼리 같은 역할
    a, b = ys[0::2], ys[1::2]
    groups = [g for g in (a, b) if len(g) >= 2]
    if not groups:
        return None
    scores = []
    for g in groups:
        base = float(np.mean(np.abs(g)))
        if base <= 0:
            continue
        spread = (max(g) - min(g)) / base      # 같은 역할끼리의 상대 편차
        # 3% 이내면 만점, 12% 넘으면 0점
        scores.append(float(np.clip((0.12 - spread) / 0.09, 0.0, 1.0)))
    return float(np.mean(scores)) if scores else None


def _prominence_score(points: list, neckline: float) -> float:
    """넥라인 대비 패턴 진폭 (0~1). 진폭 3% 이상 만점, 1% 이하 0점."""
    if neckline <= 0 or not points:
        return 0.0
    ys = [float(p[1]) for p in points]
    amp = (max(ys) - min(ys)) / neckline
    return float(np.clip((amp - 0.01) / 0.02, 0.0, 1.0))


def _channel_score(
    closes: np.ndarray, upper: list, lower: list,
    span: tuple | None = None,
) -> tuple[float, float]:
    """채널형(삼각형·쐐기·플래그) 전용 — (수렴도 안착률, 접촉 균형).

    이 계열은 가격이 두 추세선 사이를 지그재그하는 것이 정상이므로, 단일 꺾은선
    적합도로 재면 부당하게 낮게 나온다. 대신 '채널 안에 얼마나 머물렀는가'와
    '위·아래 선에 고르게 닿았는가'로 형태의 뚜렷함을 본다.
    """
    if len(upper) < 2 or len(lower) < 2:
        return 0.0, 0.0
    ux = [int(p[0]) for p in upper]
    uy = [float(p[1]) for p in upper]
    lx = [int(p[0]) for p in lower]
    ly = [float(p[1]) for p in lower]
    i0 = max(ux[0], lx[0])
    i1 = min(ux[-1], lx[-1])
    if span is not None:
        # 추세선 계열은 선을 돌파 지점까지 연장해 그린다 — 채점은 구조 구간만.
        # 돌파 대기 드리프트가 섞이면 같은 형태라도 대기가 길수록 점수가 깎인다.
        i0, i1 = max(i0, int(span[0])), min(i1, int(span[1]))
    if i1 <= i0 or i1 >= len(closes):
        return 0.0, 0.0
    grid = np.arange(i0, i1 + 1)
    hi = np.interp(grid, ux, uy)
    lo = np.interp(grid, lx, ly)
    band = hi - lo
    ok = band > 0
    if ok.sum() < 5:
        return 0.0, 0.0
    actual = closes[i0 : i1 + 1]
    # 채널 폭의 10% 여유까지 '안'으로 인정
    tol = band * 0.10
    inside = ((actual >= lo - tol) & (actual <= hi + tol) & ok).sum() / ok.sum()

    # 위·아래 선에 고르게 닿았는가 (한쪽만 닿으면 채널이라 보기 어렵다)
    pos = np.where(ok, (actual - lo) / np.where(band == 0, 1, band), 0.5)
    near_hi = float((pos[ok] > 0.75).mean())
    near_lo = float((pos[ok] < 0.25).mean())
    balance = 1.0 - abs(near_hi - near_lo) / max(near_hi + near_lo, 1e-6)
    if near_hi + near_lo < 0.10:      # 어느 선에도 거의 안 닿음
        balance = 0.0
    return float(inside), float(np.clip(balance, 0.0, 1.0))


def score_shape(
    closes: np.ndarray, points: list, neckline: float,
    points2: list | None = None, kind: str = "",
    span: tuple | None = None,
) -> int:
    """형태 신뢰도 0~100. 계열별로 채점 기준이 다르다.

    채널형(points2 보유): 채널 안착률 + 위아래 접촉 균형 (span = 구조 구간 한정)
    대칭형(SYMMETRIC_KINDS): 꺾은선 적합도 + 좌우 대칭 + 돌출도
    그 외(플래그·다이아몬드 등): 꺾은선 적합도 + 돌출도
    """
    pro = _prominence_score(points, neckline)
    if points2:
        inside, balance = _channel_score(closes, points, points2, span)
        return int(round(inside * 55 + balance * 30 + pro * 15))
    fit = _fit_score(closes, points)
    sym = _symmetry_score(points) if kind in SYMMETRIC_KINDS else None
    if sym is None:
        return int(round(fit * 75 + pro * 25))
    return int(round(fit * 45 + sym * 30 + pro * 25))


def grade_shapes(ohlcv: pd.DataFrame, pats: list) -> list:
    """각 패턴에 shape(점수)·grade(A/B/C)를 채운다. 제자리 수정 후 반환."""
    if not pats:
        return pats
    closes = ohlcv["close"].astype(float).to_numpy()
    for p in pats:
        s = score_shape(
            closes, p.points, float(p.neckline),
            getattr(p, "points2", None), p.kind,
            getattr(p, "score_span", None),
        )
        p.shape = s
        b_cut, a_cut = SHAPE_CUTS.get(p.kind, (SHAPE_B, SHAPE_A))
        p.grade = "A" if s >= a_cut else ("B" if s >= b_cut else "C")
    return pats
