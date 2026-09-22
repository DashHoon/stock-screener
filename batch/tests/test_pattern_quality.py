"""Period boundaries, frozen lines and causal event regression tests."""
import numpy as np
import pytest

from batch.patterns import dedupe_patterns, detect_all_patterns
from batch.patterns.swing import SwingCtx
from batch.patterns.trend import _register_candidates, _scan_structure
from batch.patterns.util import Line, PatternHit, within_pattern_limits
from batch.tests.test_patterns_more import _df, _leg


@pytest.mark.parametrize("bars,valid", [(19, False), (20, True), (200, True), (201, False)])
def test_inclusive_structure_limits(bars, valid):
    hit = PatternHit("pat_tri_asc", bars - 1, False, 100,
                     points=[(0, 100), (bars - 1, 100)], structure_span=(0, bars - 1))
    assert within_pattern_limits(hit, bars) is valid


def test_extension_cannot_fill_short_structure_or_extend_lifetime():
    hit = PatternHit("pat_tri_asc", None, True, 100,
                     points=[(0, 100), (35, 100)], structure_span=(0, 11))
    assert not within_pattern_limits(hit, 36)
    hit.structure_span = (0, 30)
    assert within_pattern_limits(hit, 200)
    assert not within_pattern_limits(hit, 201)
    hit.completed_at = 199
    assert within_pattern_limits(hit, 240)  # Preserve an already completed event.


def _scan(tail, *, highs=None, lows=None, break_up=True):
    values = np.array([95.] * 20 + tail)
    ctx = SwingCtx(values + .1, values - .1, values,
                   np.ones(len(values)), [], [])
    if highs is not None:
        ctx.highs[20:] = highs
    if lows is not None:
        ctx.lows[20:] = lows
    return _scan_structure(ctx, Line(0, 100, 1), Line(0, 90, 1),
                           0, 19, 20, break_up, 40)


def test_opposite_break_terminates_before_later_rally():
    status, at, _, reason = _scan([89.4, 89.3, 101, 103])
    assert (status, at, reason) == ("invalidated", 21, "opposite_break")


def test_breakout_requires_confirmation_and_keeps_confirmation_date():
    assert _scan([100.6])[0] == "pending"
    assert _scan([100.6, 99.9])[0] == "forming"
    assert _scan([100.6, 100.7])[:3] == ("completed", 21, True)
    assert _scan([101.6])[:3] == ("completed", 20, True)
    assert _scan([89.4, 89.3], break_up=None)[:3] == ("completed", 21, False)


def test_wick_noise_and_large_rejected_wick_are_different():
    assert _scan([99.8], highs=[100.8])[0] == "forming"
    assert _scan([99.8], highs=[101.2])[3] == "extreme_violation"
    assert _scan([102], highs=[103], lows=[88])[3] == "both_boundaries"


def test_broken_structure_is_not_replaced_by_better_later_fit():
    old = dict(confirmed_at=30, quality=5, span=(0, 29),
               anchors=frozenset([0, 7, 14, 22, 29]), kind="pat_tri_asc",
               status="invalidated", terminal=35)
    refit = dict(old, confirmed_at=45, quality=9, span=(7, 44),
                 anchors=frozenset([7, 14, 22, 29, 44]), status="completed", terminal=46)
    fresh = dict(refit, confirmed_at=70, span=(40, 69),
                 anchors=frozenset([40, 47, 54, 62, 69]))
    assert _register_candidates([refit, fresh, old]) == [old, fresh]


def test_dedup_prefers_quality_and_preserves_earlier_events():
    short = PatternHit("pat_tri_asc", None, True, 100,
                       points=[(20, 100), (59, 100)], shape=90)
    long = PatternHit("pat_tri_asc", None, True, 100,
                      points=[(0, 100), (99, 100)], shape=60)
    assert dedupe_patterns([long, short]) == [short]
    short.completed_at, long.completed_at = 60, 100
    long.shape = 99
    assert dedupe_patterns([long, short]) == [short]


def test_completed_triangle_is_identical_at_confirmation_and_later():
    seq = [90.] * 3
    for b in (88, 91, 94, 97):
        seq += _leg(seq[-1], 100, 5) + _leg(100, b, 5)
    seq += _leg(seq[-1], 104, 4) + [104.] * 10
    df = _df(seq)
    full = [p for p in detect_all_patterns(df) if p.kind == "pat_tri_asc" and p.completed_at is not None]
    assert full
    for p in full:
        prefix = [q for q in detect_all_patterns(df.iloc[:p.completed_at + 1])
                  if q.kind == p.kind and q.completed_at == p.completed_at]
        assert len(prefix) == 1
        assert (prefix[0].points, prefix[0].points2, prefix[0].shape) == (p.points, p.points2, p.shape)
        assert 20 <= p.structure_span[1] - p.structure_span[0] + 1 <= 200
