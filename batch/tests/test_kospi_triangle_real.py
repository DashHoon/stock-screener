"""KOSPI (KS11): published daily OHLCV through 2026-10-08.

The fixture comes from web/public/data/chart/KS11.json on the data branch.
A 42% crash (06-25 → 07-29) followed by a tight range used to be drawn as one
symmetric triangle and one falling wedge whose lines reached back over the
crash. The range itself is an ascending triangle under a 7,217 ceiling.
"""
from pathlib import Path

import pandas as pd

from batch.patterns import detect_all_patterns
from batch.patterns.util import structure_span

TRENDLINE = ('pat_tri_', 'pat_wedge_', 'pat_bwedge_', 'pat_broadening')


def candles(until=None):
    df = pd.read_csv(Path(__file__).parent / 'fixtures/KS11_triangle.csv')
    return df if until is None else df[df.date <= until].reset_index(drop=True)


def recent(df):
    out = []
    for h in detect_all_patterns(df):
        start = df.date.iloc[structure_span(h)[0]]
        if h.kind.startswith(TRENDLINE) and start >= '2026-05-01':
            out.append((h, start))
    return out


def test_crash_and_rebound_are_not_one_structure():
    for h, start in recent(candles()):
        assert start >= '2026-07-29', (h.kind, start)


def test_range_after_crash_is_an_ascending_triangle():
    df = candles('2026-10-07')
    (hit, start), = recent(df)
    assert hit.kind == 'pat_tri_asc' and hit.forming
    assert start == '2026-08-07'
    assert hit.neckline == 7216.62
    assert hit.points2[-1][1] < df.close.iloc[-1] < hit.neckline


def test_first_close_below_support_is_shown_as_pending_breakdown():
    (hit, start), = recent(candles())
    assert hit.kind == 'pat_tri_asc' and start == '2026-08-07'
    assert hit.forming and hit.completed_at is None
    assert hit.pending == 'down' and hit.pending_against
