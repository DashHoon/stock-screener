"""Sunic System 171090: published daily OHLCV through 2026-09-30.

The fixture comes from web/public/data/chart/171090.json on the data branch.
Future tails below are explicitly synthetic, not market observations.
"""
from pathlib import Path

import pandas as pd

from batch.patterns import detect_all_patterns
from batch.patterns.swing import build_ctx
from batch.patterns.trend import _register_candidates


def candles():
    return pd.read_csv(Path(__file__).parent / 'fixtures/171090_triangle.csv')


def triangles(df):
    return [h for h in detect_all_patterns(df) if h.kind == 'pat_tri_asc'
            and df.date.iloc[h.structure_span[0]] >= '2026-07-01']


def append_candle(df, close, high=None):
    previous = float(df.close.iloc[-1])
    row = dict(date='2026-10-01', open=previous, close=close,
               high=max(previous, close) + 100 if high is None else high,
               low=min(previous, close) - 100, volume=50000)
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def test_sunic_forming_is_available_without_future_bars():
    df = candles()
    hit, = triangles(df)
    assert hit.forming and hit.completed_at is None
    assert hit.neckline == 74200
    assert df.date.iloc[hit.structure_span[0]] == '2026-07-29'
    assert df.date.iloc[hit.confirmed_at] == '2026-09-16'
    assert len(hit.touch_points) >= 5
    assert hit.points2[-1][1] < df.close.iloc[-1] < hit.neckline
    for end in (hit.confirmed_at, len(df)-2):
        earlier, = triangles(df.iloc[:end+1])
        assert earlier.forming
        assert earlier.touch_points == hit.touch_points
        assert earlier.structure_span == hit.structure_span
    assert not triangles(df.iloc[:hit.confirmed_at])


def test_sunic_fixed_resistance_requires_close_confirmation():
    df = candles()
    base, = triangles(df)
    atr = build_ctx(df).atr[-1]
    wick = append_candle(df, 71000, high=base.neckline + .75*atr)
    assert triangles(wick)[0].forming
    first = append_candle(df, base.neckline + .8*atr)
    assert triangles(first)[0].forming
    confirmed = append_candle(first, base.neckline + .8*atr)
    hit, = triangles(confirmed)
    assert hit.completed_at == len(confirmed)-1 and not hit.forming
    assert hit.touch_points == base.touch_points
    assert hit.neckline == base.neckline
    later, = triangles(append_candle(confirmed, 80000))
    assert later.completed_at == hit.completed_at
    assert later.points == hit.points and later.points2 == hit.points2
    assert not triangles(append_candle(df, 60000))


def test_new_triangle_needs_fresh_contacts_on_both_sides_after_failure():
    old = dict(kind='pat_tri_asc', confirmed_at=30, terminal=35,
               status='invalidated', quality=5, span=(0, 29),
               anchors=frozenset([0, 7, 14, 22, 29]))
    new = dict(old, confirmed_at=45, terminal=46, status='forming',
               span=(7, 44), anchors=frozenset([7, 14, 22, 29, 36, 44]),
               boundary_touches=((7, 36), (14, 44)))
    assert _register_candidates([old, new]) == [old, new]
    for sides in (((7, 29), (14, 44)), ((7, 36), (14, 22))):
        one_side = dict(new, boundary_touches=sides)
        assert _register_candidates([old, one_side]) == [old]
    future_failure = dict(old, terminal=46)
    assert _register_candidates([future_failure, new]) == [future_failure]
