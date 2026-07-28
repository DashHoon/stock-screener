"""추세선 계열 패턴: 삼각형 3종, 쐐기 2종, 브로드닝 — ATR 적응형 스윙(ZigZag) 기반.

고정 lookback 피벗 대신 스윙 구조(swing.py)를 읽는다 (2026-07-28 이식).
- 구조 후보: 확정 스윙 e에서 끝나는 연속 스윙 윈도우(마지막 m개, m=5~8).
  잔파동은 스윙 층에서 걸러지므로 엉뚱한 고점·저점이 선에 연결되지 않는다.
- 추세선: fit_swing_trendline — 앵커 2점 + 터치 수 최대화 (회귀·R² 게이트 폐기,
  품질은 터치 수로 판정).
- 미래 참조 없음: 돌파 스캔은 마지막 구조 스윙의 confirmed_at부터 시작.
- 스케일: minor(단기)·major(장기) 둘 다 탐지 — 겹침은 dedupe_patterns가 정리.

분류 (기울기 = 봉당 %, FLAT_EPS 이내 = 수평):
- 상승삼각형: 위 수평 + 아래 상승 → 위 돌파 시 완성 (상승)
- 하락삼각형: 아래 수평 + 위 하락 → 아래 이탈 시 완성 (하락)
- 삼각수렴: 위 하락 + 아래 상승 → 돌파 방향에 따라 up/down
- 상승쐐기: 둘 다 상승하며 수렴 → 아래 이탈 시 완성 (하락)
- 하락쐐기: 둘 다 하락하며 수렴 → 위 돌파 시 완성 (상승)
- 상승 확대 쐐기: 둘 다 상승하며 확대 → 아래 이탈 시 완성 (하락)
- 하락 확대 쐐기: 둘 다 하락하며 확대 → 위 돌파 시 완성 (상승)
- 브로드닝: 위 상승 + 아래 하락(확대) → 아래 이탈 시 완성 (하락)
"""

import numpy as np
import pandas as pd

from batch.patterns.swing import Swing, SwingCtx, build_ctx, fit_swing_trendline
from batch.patterns.util import Line, PatternHit, slope_pct

FLAT_EPS = 0.10    # 봉당 % — 이하면 수평 취급
TREND_EPS = 0.12   # 봉당 % — 이상이어야 추세로 취급
CONVERGE_RATIO = 0.75   # 끝 폭 ≤ 시작 폭 × 이 값 (수렴형)
DIVERGE_RATIO = 1.35    # 끝 폭 ≥ 시작 폭 × 이 값 (브로드닝)
# 확대 쐐기(둘 다 같은 방향 기울기 + 벌어짐)는 대칭 메가폰(브로드닝)과 기하가
# 달라 확대 임계를 공유하지 않는다. 메가폰은 위·아래가 서로 반대로 벌어져
# 폭이 급격히 커지지만, 확대 쐐기는 같은 방향으로 기울어 벌어짐이 완만해
# 후보가 훨씬 많이 나온다 → 별도(더 엄격한) 상수로 방출량을 따로 조인다.
BWEDGE_DIVERGE_RATIO = 1.50   # 확대 쐐기: 끝 폭 ≥ 시작 폭 × 이 값
# 확대비만으로는 평행 채널이 통과한다: 창이 길면 기울기가 거의 같아도(su≈sl)
# 누적 폭 차이가 임계를 넘기 때문. '완만한 쪽 |기울기| ≤ 가파른 쪽 × K'를
# 함께 요구해 두 선이 실제로 벌어지는 각을 이루는 경우만 남긴다.
BWEDGE_SLOPE_K = 0.60
BREAK_WINDOW = 25       # 구조 확정(confirmed_at) 후 돌파 대기 봉 수

# 연속 스윙 윈도우 크기. 같은 e에서 여러 m이 같은 종류로 분류되면 터치 최다 1개만.
WINDOW_SIZES = (5, 6, 7, 8)
# 스팬 백스톱: 첫 스윙 idx ~ 마지막 스윙 idx (봉). 스케일별.
SPAN_LIMITS = {"minor": (20, 120), "major": (40, 250)}
# 품질 게이트 — R² 대신 추세선 터치 수
MIN_TOUCH_FAVORED = 4   # 재현율 우선 종류: 위+아래 합계
MIN_TOUCH_STRICT = 5    # 그 외 종류: 합계 ≥ 5, 그리고 양쪽 각 ≥ 2
# 앵커 2점은 정의상 터치라 2+2 윈도우에서 터치 게이트가 자동 통과된다.
# 그래서 '가격이 실제로 두 선 사이에 머물렀는가'를 별도 게이트로 요구한다
# (안착률 — 종가가 채널 밖으로 자주 나가는 창은 선을 억지로 끼워 맞춘 것).
MIN_CONTAIN = 0.80      # 윈도우 구간 종가의 채널 안착 비율 하한
CONTAIN_TOL = 0.10      # 채널 폭 대비 안/밖 판정 여유
# 같은 구조가 스윙이 하나 늘 때마다 다른 완성봉으로 재방출되는 연쇄를 막는다:
# 기본 종류가 같고 구조 구간이 이 비율 이상 겹치면 동일 구조로 보고 대표 1개만.
CHAIN_OVERLAP = 0.50
# 구조 범위 트리밍: 창은 후보 풀일 뿐, 패턴의 실제 범위는 '두 선이 모두
# 받쳐지기 시작하는 지점'부터다. 창 앞에 구조와 무관한 진입 레그가 섞이면
# (a) 선이 창 앞부분에서 가격 위를 붕 떠 지나가는 가짜 수렴이 통과되고
# (b) 수렴 폭(w_start)이 뻥튀기된다. 그래서 각 선의 '근접'(SUPPORT_TOL_ATR×ATR
# 이내) 극점 중 첫 지점의 늦은 쪽을 구조 시작으로 삼아 스팬·수렴·안착률을
# 다시 계산한다. 근접은 터치(0.5 ATR)보다 느슨하게 — 지지 여부 검사이지
# 터치 카운트가 아니다.
SUPPORT_TOL_ATR = 1.0
# 각 선의 마지막 근접 극점은 구조 뒤쪽 이 비율 안에 있어야 (끝까지 받치는 선)
LINE_SUPPORT_END = 0.40

# ── 신뢰 종류(상승삼각형·삼각수렴) 재현율 우선 완화 ──────────────────────
# 사용자가 가장 신뢰하는 패턴은 '살짝 틀려도 되니 놓치지 않는 것'이 우선이다
# (2026-07-26 결정). 느슨해진 후보의 품질은 형태 등급(A/B/C)이 구분해 준다.
FAVORED = ("pat_tri_asc", "pat_tri_sym")
RISE_EPS = 0.08             # 신뢰 종류의 추세 기울기 하한 (기본 0.12보다 완화)
CONVERGE_RATIO_LOOSE = 0.85 # 삼각수렴: 완만한 수렴도 허용
BREAK_WINDOW_LOOSE = 40     # 신뢰 종류는 돌파 대기 기간도 길게


def _eval_window(
    win: list[Swing], ctx: SwingCtx, n: int, span_lim: tuple[int, int],
) -> dict | None:
    """연속 스윙 윈도우 하나를 평가해 후보(dict)를 반환. 탈락이면 None.

    분류·게이트·돌파 스캔까지 끝내고, 완성 또는 형성 중인 것만 후보가 된다.
    """
    hs = [s for s in win if s.is_high]
    ls = [s for s in win if not s.is_high]
    # 신뢰 종류는 한쪽 2개면 시도 (2+3이면 손으로 긋는 삼각형엔 충분).
    # 엄격 종류의 3+3 요건은 분류 후에 거른다.
    if len(hs) < 2 or len(ls) < 2:
        return None
    x_last = win[-1].idx
    if win[-1].idx - win[0].idx > span_lim[1]:
        return None  # 트리밍해도 상한 초과인 창은 조기 탈락

    closes = ctx.closes
    upper, t_u = fit_swing_trendline(
        [s.idx for s in hs], [s.price for s in hs], ctx.atr, upper=True)
    lower, t_l = fit_swing_trendline(
        [s.idx for s in ls], [s.price for s in ls], ctx.atr, upper=False)

    # 구조 범위 트리밍 (모듈 상수 SUPPORT_TOL_ATR 주석 참고)
    def _near_xs(line: Line, swings_: list[Swing]) -> list[int]:
        atr = ctx.atr
        return [
            s.idx for s in swings_
            if abs(s.price - line.at(s.idx))
            <= float(atr[min(s.idx, len(atr) - 1)]) * SUPPORT_TOL_ATR
        ]

    near_u, near_l = _near_xs(upper, hs), _near_xs(lower, ls)
    if not near_u or not near_l:
        return None
    x_first = max(near_u[0], near_l[0])  # 구조 시작 = 두 선이 모두 받쳐지는 지점
    span_w = x_last - x_first
    if not (span_lim[0] <= span_w <= span_lim[1]):
        return None
    # 두 선 모두 구조 끝까지 받쳐야 한다
    if near_u[-1] < x_last - LINE_SUPPORT_END * span_w:
        return None
    if near_l[-1] < x_last - LINE_SUPPORT_END * span_w:
        return None

    ref = float(closes[x_last])
    su, sl = slope_pct(upper, ref), slope_pct(lower, ref)
    # 수렴/확산 폭은 트리밍된 구조 시작~마지막 스윙에서 계산
    w_start = upper.at(x_first) - lower.at(x_first)
    w_end = upper.at(x_last) - lower.at(x_last)
    if w_start <= 0:
        return None
    converging = w_end <= w_start * CONVERGE_RATIO
    converging_loose = w_end <= w_start * CONVERGE_RATIO_LOOSE
    diverging = w_end >= w_start * DIVERGE_RATIO
    # 확대 쐐기: 폭 w(x)=upper-lower, dw/dx = su - sl 이므로 부호와 무관하게
    # '확대 ⟺ su > sl'. 수렴 쐐기(sl > su)와 상호 배타적이다.
    bw_diverging = w_end >= w_start * BWEDGE_DIVERGE_RATIO
    bw_angled = min(abs(su), abs(sl)) <= max(abs(su), abs(sl)) * BWEDGE_SLOPE_K

    kind = None
    break_up: bool | None = None  # True=위 돌파가 완성, False=아래 이탈, None=양방향(수렴)
    if abs(su) <= FLAT_EPS and sl >= RISE_EPS:
        kind, break_up = "pat_tri_asc", True
    elif abs(sl) <= FLAT_EPS and su <= -TREND_EPS:
        kind, break_up = "pat_tri_desc", False
    elif su <= -RISE_EPS and sl >= RISE_EPS and converging_loose:
        kind, break_up = "pat_tri_sym", None
    elif su >= TREND_EPS and sl >= TREND_EPS and converging and sl > su:
        kind, break_up = "pat_wedge_rise", False
    elif su <= -TREND_EPS and sl <= -TREND_EPS and converging and su < sl:
        kind, break_up = "pat_wedge_fall", True
    elif (su >= TREND_EPS and sl >= TREND_EPS and bw_diverging
          and su > sl and bw_angled):
        # 상승 확대 쐐기: 둘 다 상승, 위가 더 가파름 → 하단(상승 지지선) 이탈
        kind, break_up = "pat_bwedge_rise", False
    elif (su <= -TREND_EPS and sl <= -TREND_EPS and bw_diverging
          and su > sl and bw_angled):
        # 하락 확대 쐐기: 둘 다 하락, 아래가 더 가파름 → 상단(하락 저항선) 돌파
        kind, break_up = "pat_bwedge_fall", True
    elif su >= TREND_EPS and sl <= -TREND_EPS and diverging:
        kind, break_up = "pat_broadening", False
    if kind is None:
        return None

    # 품질 게이트: 터치 수 (R² 게이트 대체)
    favored = kind in FAVORED
    touches = t_u + t_l
    if favored:
        if touches < MIN_TOUCH_FAVORED:
            return None
    else:
        if len(hs) < 3 or len(ls) < 3:
            return None
        if touches < MIN_TOUCH_STRICT or t_u < 2 or t_l < 2:
            return None

    # 안착률 게이트: 윈도우 구간 종가가 두 선 사이에 실제로 머물렀는가.
    # 앵커 2점 터치는 공짜라서, 이것이 재현율 우선 종류의 실질 품질 게이트다.
    grid = np.arange(x_first, x_last + 1)
    hi_line = upper.slope * grid + upper.intercept
    lo_line = lower.slope * grid + lower.intercept
    band = hi_line - lo_line
    if (band <= 0).any():
        return None  # 윈도우 안에서 선이 교차 — 구조로 볼 수 없다
    seg = closes[x_first : x_last + 1]
    tol = band * CONTAIN_TOL
    inside = ((seg >= lo_line - tol) & (seg <= hi_line + tol)).mean()
    if inside < MIN_CONTAIN:
        return None

    # 수평으로 분류된 선은 '완전한 수평선'으로 강제한다.
    # FLAT_EPS 이내의 잔기울기를 그대로 그리면 상승삼각형의 상단이 살짝
    # 틀어져 보인다. 정의대로 — 상승삼각형 상단은 스윙 고점들의 최고가,
    # 하락삼각형 하단은 스윙 저점들의 최저가에 놓인 수평 저항/지지선.
    if kind == "pat_tri_asc":
        upper = Line(0.0, max(s.price for s in hs), upper.r2)
    elif kind == "pat_tri_desc":
        lower = Line(0.0, min(s.price for s in ls), lower.r2)

    # 돌파 스캔 — 마지막 구조 스윙의 확정 봉부터 (미래 참조 없음)
    scan_from = int(win[-1].confirmed_at)
    deadline = min(scan_from + (BREAK_WINDOW_LOOSE if favored else BREAK_WINDOW), n - 1)
    completed_at = None
    completed_kind = kind
    invalidated = False
    for j in range(scan_from, deadline + 1):
        up_lvl, dn_lvl = upper.at(j), lower.at(j)
        if up_lvl <= dn_lvl:  # 추세선 교차(apex) 이후는 무효
            invalidated = True
            break
        c = closes[j]
        if break_up in (True, None) and c > up_lvl:
            completed_at = j
            completed_kind = kind + ("_up" if break_up is None else "")
            break
        if break_up in (False, None) and c < dn_lvl:
            completed_at = j
            completed_kind = kind + ("_down" if break_up is None else "")
            break
    # 형성 중 = 구조 확정 + 돌파 전 + 무효화 전 + 대기 기한이 차트 끝까지 남음
    forming = completed_at is None and not invalidated and deadline == n - 1
    if completed_at is None and not forming:
        return None

    # 적합한 추세선을 '직선 + 돌파 지점까지 연장'해서 그린다.
    # 실제 고점들을 지그재그로 이으면 꺾인 선이라 어디를 돌파했는지 안 보인다.
    # 돌파 판정도 이 직선(upper.at/lower.at)으로 하므로 화면과 판정이 일치한다.
    x0 = int(x_first)
    x1 = int(completed_at if completed_at is not None else deadline)
    if x1 <= x0:
        return None
    neck_ref = completed_at if completed_at is not None else x_last
    neckline = upper.at(neck_ref) if (break_up in (True, None)) else lower.at(neck_ref)
    return {
        "kind": kind,
        "out_kind": completed_kind if completed_at is not None else kind,
        "completed_at": completed_at,
        "forming": forming,
        "neckline": float(neckline),
        "points": [(x0, float(upper.at(x0))), (x1, float(upper.at(x1)))],
        "points2": [(x0, float(lower.at(x0))), (x1, float(lower.at(x1)))],
        "confirmed_at": scan_from,
        "touches": touches,
        "span": (int(x_first), int(x_last)),  # 구조 구간 — 채점·연쇄 억제 공용
    }


def detect_trendline_patterns(ind: pd.DataFrame, ctx: SwingCtx | None = None) -> list[PatternHit]:
    if ctx is None:
        ctx = build_ctx(ind)
    n = len(ind)

    # 1) 두 스케일의 모든 윈도우 후보를 하나의 풀로 모은다
    cands: list[dict] = []
    for scale, span_lim in SPAN_LIMITS.items():
        swings = ctx.swings(scale)
        # (스윙 위치 e, 분류 종류) → 대표 후보 하나.
        # 우선순위는 '완성 > 형성 중' 다음 터치 수 — 창 크기(m)만 다른 두 후보가
        # 터치 동점이면 먼저 평가된 쪽이 남는데, 하필 형성 중이 완성을 밀어내면
        # 그날 떠야 할 돌파 시그널이 통째로 사라진다 (리뷰 실측 2/227건).
        def _rank(c: dict) -> tuple:
            return (c["completed_at"] is not None, c["touches"])

        best: dict[tuple[int, str], dict] = {}
        for e in range(len(swings)):
            if swings[e].confirmed_at is None:
                continue  # 잠정 극점은 구조 확정에 쓰지 않는다
            for m in WINDOW_SIZES:
                if e - m + 1 < 0:
                    continue
                cand = _eval_window(swings[e - m + 1: e + 1], ctx, n, span_lim)
                if cand is None:
                    continue
                key = (e, cand["kind"])
                if key not in best or _rank(cand) > _rank(best[key]):
                    best[key] = cand
        cands.extend(best.values())

    # 2) 연쇄 억제: 같은 수렴 구조는 스윙이 하나 늘 때마다 (혹은 다른 스케일에서)
    #    조금 다른 창·완성봉으로 계속 다시 잡힌다. 완성봉이 달라 used-set이
    #    못 거르는 중복이므로 여기서 정리한다. 대표 선정은 제품 관례
    #    (dedupe_patterns)와 동일 — 가장 길게 그려진 것 → 터치 많은 것.
    #    단, 그룹은 '최종 출력 kind + 완성 여부'로 나눈다: 삼각수렴의 위/아래
    #    돌파는 서로 다른 시그널이고, 이미 돌파한 완성이 더 긴 '형성 중' 확장
    #    창에 가려지면 가장 가치 있는 최근 돌파가 사라진다 (리뷰 실측 결함).
    order = sorted(
        cands,
        key=lambda c: (
            -(c["span"][1] - c["span"][0]),
            -c["touches"],
            c["completed_at"] if c["completed_at"] is not None else 1 << 30,
        ),
    )
    kept: list[dict] = []
    used: set[tuple[str, int]] = set()  # 같은 완성봉·같은 종류 중복 제거 (2차 방어)
    for c in order:
        s1, e1 = c["span"]
        group = (c["out_kind"], c["completed_at"] is not None)
        dup = False
        for k in kept:
            if (k["out_kind"], k["completed_at"] is not None) != group:
                continue
            s2, e2 = k["span"]
            overlap = min(e1, e2) - max(s1, s2)
            shorter = min(e1 - s1, e2 - s2)
            if overlap > 0 and shorter > 0 and overlap / shorter >= CHAIN_OVERLAP:
                dup = True
                break
        if dup:
            continue
        if c["completed_at"] is not None:
            dedup_key = (c["out_kind"], c["completed_at"])
            if dedup_key in used:
                continue
            used.add(dedup_key)
        kept.append(c)

    kept.sort(key=lambda c: (c["span"][0], c["span"][1]))
    return [
        PatternHit(
            kind=c["out_kind"],
            completed_at=c["completed_at"],
            forming=c["forming"],
            neckline=c["neckline"],
            points=c["points"],      # 위 추세선
            points2=c["points2"],    # 아래 추세선
            confirmed_at=c["confirmed_at"],
            score_span=c["span"],    # 채점은 구조 구간만 (돌파 대기 드리프트 제외)
        )
        for c in kept
    ]
