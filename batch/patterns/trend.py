"""Fixed, causally registered swing boundaries for triangles and wedges.

Candidates use 20–200 inclusive daily bars. Once recognized, a boundary is
never refitted to rescue a broken structure. Replay keeps terminated candidates
internally so later overlapping windows cannot resurrect them.
"""

import numpy as np
import pandas as pd

from batch import config
from batch.patterns.shape import SHAPE_CUTS, SHAPE_MIN, score_shape
from batch.patterns.swing import Swing, SwingCtx, build_ctx, fit_swing_trendline
from batch.patterns.util import Line, PatternHit, slope_pct

FLAT_EPS = 0.10
TREND_EPS = 0.12
RISE_EPS = 0.08
CONVERGE_RATIO = 0.75
CONVERGE_RATIO_LOOSE = 0.85
DIVERGE_RATIO = 1.35
BWEDGE_DIVERGE_RATIO = 1.50
BWEDGE_SLOPE_K = 0.60
BWEDGE_TRAVEL_MAX_PCT = 35.0
BWEDGE_WIDTH_MAX_PCT = 35.0
BREAK_WINDOW = 25
BREAK_WINDOW_LOOSE = 40
FAVORED = ("pat_tri_asc", "pat_tri_sym")
WINDOW_SIZES = (5, 6, 7, 8, 9, 10, 12)
SPAN_LIMITS = {"minor": (20, 120), "major": (40, 200)}  # inclusive bar counts
CHAIN_OVERLAP = 0.50


def _tolerance(ctx: SwingCtx) -> np.ndarray:
    # Yesterday's volatility: today's spike cannot enlarge its own tolerance.
    return ctx.line_atr


def _touches(line: Line, swings: list[Swing], atr: np.ndarray) -> list[int]:
    result = []
    for s in swings:
        if abs(s.price - line.at(s.idx)) <= config.SWING_TOUCH_ATR * atr[s.idx]:
            if not result or s.idx - result[-1] >= config.PATTERN_TOUCH_GAP:
                result.append(s.idx)
    return result


def _scan_structure(ctx, upper, lower, start, end, recognized, break_up, wait):
    """Replay fixed lines, retaining termination even when no hit is published."""
    n = len(ctx.closes)
    atr = _tolerance(ctx)
    deadline = min(recognized + wait, start + config.PATTERN_MAX_BARS - 1)
    if recognized > deadline:
        return "expired", deadline, None, "max_age"
    run_up = run_down = 0
    pending = False
    # New confirmed swings must keep supporting these same boundaries.
    confirmations = {}
    for swing in ctx.minor:
        if swing.idx > end and swing.confirmed_at is not None:
            confirmations.setdefault(swing.confirmed_at, []).append(swing)
    misses = {True: 0, False: 0}
    for j in range(end + 1, min(deadline, n - 1) + 1):
        u, l, a = upper.at(j), lower.at(j), atr[j]
        if u <= l:
            return "expired", j, None, "apex_cross"
        up_wick = ctx.highs[j] > u + config.PATTERN_WICK_VIOL_ATR * a
        dn_wick = ctx.lows[j] < l - config.PATTERN_WICK_VIOL_ATR * a
        if up_wick and dn_wick:
            return "invalidated", j, None, "both_boundaries"
        du, dd = (ctx.closes[j] - u) / a, (l - ctx.closes[j]) / a
        run_up = run_up + 1 if du > config.PATTERN_BREAK_ATR else 0
        run_down = run_down + 1 if dd > config.PATTERN_BREAK_ATR else 0
        direction = (True if du > config.PATTERN_STRONG_BREAK_ATR or run_up >= 2
                     else False if dd > config.PATTERN_STRONG_BREAK_ATR or run_down >= 2
                     else None)
        if direction is not None:
            if j < recognized:
                return "invalidated", j, None, "break_before_recognition"
            if break_up is None or direction == break_up:
                return "completed", j, direction, None
            return "invalidated", j, None, "opposite_break"
        pending = run_up > 0 or run_down > 0
        # A moderate first close outside is pending; a large rejected wick is damage.
        if (up_wick and not run_up) or (dn_wick and not run_down):
            return "invalidated", j, None, "extreme_violation"
        for swing in confirmations.get(j, []):
            line = upper if swing.is_high else lower
            touches = abs(swing.price - line.at(swing.idx)) <= config.SWING_TOUCH_ATR * atr[swing.idx]
            misses[swing.is_high] = 0 if touches else misses[swing.is_high] + 1
            if misses[swing.is_high] >= 2:
                return "invalidated", j, None, "lost_support"
    if n - 1 > deadline:
        return "expired", deadline + 1, None, "max_age"
    return ("pending" if pending else "forming"), n - 1, None, None


def _eval_window(win: list[Swing], ctx: SwingCtx, n: int,
                 span_lim: tuple[int, int]) -> dict | None:
    # The initial ZigZag seed has no preceding reversal; it is not a proven touch.
    if win[0].idx == 0 or any(s.confirmed_at is None for s in win):
        return None
    hs = [s for s in win if s.is_high]
    ls = [s for s in win if not s.is_high]
    if len(hs) < 2 or len(ls) < 2:
        return None
    # Keep every anchor inside the declared structure; never hide early violations
    # by trimming while continuing to count the discarded points as support.
    x_first, x_last = win[0].idx, win[-1].idx
    span_w = x_last - x_first
    if not max(config.PATTERN_MIN_BARS, span_lim[0]) <= span_w + 1 <= min(config.PATTERN_MAX_BARS, span_lim[1]):
        return None
    recognized = max(int(s.confirmed_at) for s in win)
    if recognized >= n or recognized - x_first + 1 > config.PATTERN_MAX_BARS:
        return None
    atr = _tolerance(ctx)
    up_fit = fit_swing_trendline([s.idx for s in hs], [s.price for s in hs], atr, True)
    lo_fit = fit_swing_trendline([s.idx for s in ls], [s.price for s in ls], atr, False)
    if up_fit is None or lo_fit is None:
        return None
    upper, lower = up_fit[0], lo_fit[0]
    closes = ctx.closes
    ref = float(closes[x_last])
    if not np.isfinite(ref) or ref <= 0:
        return None
    su, sl = slope_pct(upper, ref), slope_pct(lower, ref)
    # A nearly flat daily slope must also be flat across the complete structure.
    flat_limit = min(0.02 * ref, 1.5 * float(np.median(atr[x_first:x_last + 1])))
    if abs(su) <= FLAT_EPS and abs(upper.slope * span_w) <= flat_limit:
        upper = Line(0.0, max(s.price for s in hs), upper.r2)
    if abs(sl) <= FLAT_EPS and abs(lower.slope * span_w) <= flat_limit:
        lower = Line(0.0, min(s.price for s in ls), lower.r2)
    su, sl = slope_pct(upper, ref), slope_pct(lower, ref)
    w_start = upper.at(x_first) - lower.at(x_first)
    w_end = upper.at(x_last) - lower.at(x_last)
    if w_start <= 0 or w_end <= 0:
        return None
    converging = w_end <= w_start * CONVERGE_RATIO
    converging_loose = w_end <= w_start * CONVERGE_RATIO_LOOSE
    diverging = w_end >= w_start * DIVERGE_RATIO
    bw_diverging = w_end >= w_start * BWEDGE_DIVERGE_RATIO
    bw_angled = min(abs(su), abs(sl)) <= max(abs(su), abs(sl)) * BWEDGE_SLOPE_K
    kind = None
    break_up: bool | None = None  # True=위 돌파가 완성, False=아래 이탈, None=양방향(수렴)
    if upper.slope == 0 and sl >= RISE_EPS and converging_loose:
        kind, break_up = "pat_tri_asc", True
    elif lower.slope == 0 and su <= -TREND_EPS and converging_loose:
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

    # 추세 잠식 게이트 (모듈 상수 BWEDGE_TRAVEL_MAX_PCT 주석 참고)
    if kind in ("pat_bwedge_rise", "pat_bwedge_fall"):
        mid_travel = abs(
            (upper.at(x_last) + lower.at(x_last))
            - (upper.at(x_first) + lower.at(x_first))
        ) / 2
        if mid_travel / ref * 100 > BWEDGE_TRAVEL_MAX_PCT:
            return None
        if w_end / ref * 100 > BWEDGE_WIDTH_MAX_PCT:
            return None

    if kind not in FAVORED and (len(hs) < 3 or len(ls) < 3):
        return None
    # Revalidate final horizontal/diagonal lines, not the discarded original fit.
    touch_u, touch_l = _touches(upper, hs, atr), _touches(lower, ls, atr)
    if min(len(touch_u), len(touch_l)) < 2 or len(touch_u) + len(touch_l) < 5:
        return None
    for touches in (touch_u, touch_l):
        if touches[-1] - touches[0] < 0.50 * span_w:
            return None
        if touches[0] > x_first + 0.40 * span_w or touches[-1] < x_last - 0.40 * span_w:
            return None
    grid = np.arange(x_first, x_last + 1)
    hi_line, lo_line = upper.slope * grid + upper.intercept, lower.slope * grid + lower.intercept
    a = atr[grid]
    seg = closes[grid]
    if not np.isfinite(ctx.highs[grid]).all() or not np.isfinite(ctx.lows[grid]).all() or not np.isfinite(seg).all():
        return None
    if ((hi_line <= lo_line) | (ctx.highs[grid] > hi_line + config.PATTERN_WICK_VIOL_ATR * a)
            | (ctx.lows[grid] < lo_line - config.PATTERN_WICK_VIOL_ATR * a)).any():
        return None
    inside = ((seg >= lo_line - config.PATTERN_CLOSE_TOL_ATR * a)
              & (seg <= hi_line + config.PATTERN_CLOSE_TOL_ATR * a)).mean()
    if inside < config.PATTERN_CONTAIN_MIN:
        return None
    for outside in (seg > hi_line + config.PATTERN_BREAK_ATR * a,
                    seg < lo_line - config.PATTERN_BREAK_ATR * a):
        if (outside[:-1] & outside[1:]).any():
            return None
    # Admission is based only on evidence known at recognition, never eventual success.
    points = [(x_first, upper.at(x_first)), (x_last, upper.at(x_last))]
    points2 = [(x_first, lower.at(x_first)), (x_last, lower.at(x_last))]
    neckline = upper.at(x_last) if break_up in (True, None) else lower.at(x_last)
    shape = score_shape(closes, points, neckline, points2, kind, (x_first, x_last))
    if shape < SHAPE_CUTS.get(kind, SHAPE_MIN):
        return None
    residual = float(np.mean([abs(s.price - (upper if s.is_high else lower).at(s.idx)) / atr[s.idx] for s in win]))
    quality = len(touch_u) + len(touch_l) + inside - residual
    status, terminal, direction, reason = _scan_structure(
        ctx, upper, lower, x_first, x_last, recognized, break_up,
        BREAK_WINDOW_LOOSE if kind in FAVORED else BREAK_WINDOW)
    if terminal < recognized:
        return None  # Never admitted: cannot act as a tombstone for a valid structure.
    completed = terminal if status == "completed" else None
    out_kind = kind + ("_up" if direction else "_down") if kind == "pat_tri_sym" and completed is not None else kind
    return dict(kind=kind, out_kind=out_kind, completed_at=completed,
                forming=status == "forming", status=status, terminal=terminal, reason=reason,
                neckline=float((upper if direction is True or (direction is None and break_up in (True, None)) else lower).at(terminal)),
                points=[(x_first, float(upper.at(x_first))), (terminal, float(upper.at(terminal)))],
                points2=[(x_first, float(lower.at(x_first))), (terminal, float(lower.at(terminal)))],
                confirmed_at=recognized, touches=len(touch_u) + len(touch_l),
                span=(x_first, x_last), anchors=frozenset(s.idx for s in win),
                touch_points=[(i, float(upper.at(i))) for i in touch_u] + [(i, float(lower.at(i))) for i in touch_l],
                quality=quality, shape=shape)


def _register_candidates(cands: list[dict]) -> list[dict]:
    """Deterministic causal admission, including tombstones for broken structures."""
    order = sorted(cands, key=lambda c: (c["confirmed_at"], -c["quality"], c["span"], c["kind"]))
    registered = []
    for c in order:
        s1, e1 = c["span"]
        duplicate = False
        for previous in reversed(registered):
            if previous["kind"] != c["kind"]:
                continue
            s2, structure_end = previous["span"]
            # Existing fixed boundaries remain active beyond their last anchor.
            # Only their life up to this admission date may influence selection.
            e2 = max(structure_end, min(previous["terminal"], c["confirmed_at"]))
            if e2 < s1:
                continue
            overlap = min(e1, e2) - max(s1, s2) + 1
            shared = len(c["anchors"] & previous["anchors"])
            if (shared >= 2 and overlap / min(e1 - s1 + 1, e2 - s2 + 1) >= CHAIN_OVERLAP):
                duplicate = True
                break
        if not duplicate:
            registered.append(c)
    return registered


def detect_trendline_patterns(ind: pd.DataFrame, ctx: SwingCtx | None = None) -> list[PatternHit]:
    if ctx is None:
        ctx = build_ctx(ind)
    cands = []
    for scale, span_lim in SPAN_LIMITS.items():
        swings = ctx.swings(scale)
        for e, swing in enumerate(swings):
            if swing.confirmed_at is None:
                continue
            for m in WINDOW_SIZES:
                if e + 1 < m:
                    continue
                candidate = _eval_window(swings[e - m + 1:e + 1], ctx, len(ind), span_lim)
                if candidate is not None:
                    cands.append(candidate)
    return [PatternHit(
        kind=c["out_kind"], completed_at=c["completed_at"], forming=c["forming"],
        neckline=c["neckline"], points=c["points"], points2=c["points2"],
        confirmed_at=c["confirmed_at"], score_span=c["span"], structure_span=c["span"],
        touch_points=c["touch_points"], quality=c["quality"], shape=c["shape"], shape_locked=True,
    ) for c in _register_candidates(cands) if c["status"] in ("forming", "completed")]
