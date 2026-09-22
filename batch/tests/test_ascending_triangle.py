"""Ascending triangle watchlist, confirmation and failure regression cases."""
from batch.patterns import detect_all_patterns
from batch.tests.test_patterns_more import _df, _leg


def triangle(bottoms=(88, 92), steps=8):
    seq = [90.] * 3
    for bottom in bottoms:
        seq += _leg(seq[-1], 100, steps) + _leg(100, bottom, steps)
    return seq + _leg(bottoms[-1], 97, 4)


def hits(seq):
    return [h for h in detect_all_patterns(_df(seq)) if h.kind == 'pat_tri_asc']


def test_four_confirmed_contacts_form_then_break_without_moving_lines():
    seq = triangle()
    forming = hits(seq)
    assert len(forming) == 1 and forming[0].forming
    assert len(forming[0].touch_points) == 4
    pending = hits(seq + [101.5])
    assert len(pending) == 1 and pending[0].forming
    assert pending[0].completed_at is None
    completed = hits(seq + [101.5, 102.])
    assert len(completed) == 1 and completed[0].completed_at == len(seq) + 1
    assert completed[0].touch_points == forming[0].touch_points
    assert hits(seq + [101.5, 102., 105., 106.])[0].completed_at == len(seq) + 1


def test_failed_break_and_lower_boundary_failure():
    seq = triangle()
    assert hits(seq + [101.5, 99.])[0].forming
    assert not hits(seq + [98., 85., 84.])


def test_slow_rising_support_over_longer_structure():
    assert hits(triangle(bottoms=(88, 91), steps=25))[0].forming


def test_rectangle_and_too_short_structure_are_excluded():
    assert not hits(triangle(bottoms=(88, 88)))
    assert not hits(triangle(steps=4))
