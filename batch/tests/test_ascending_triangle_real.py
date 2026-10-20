"""Sunic System 171090: published daily OHLCV through 2026-10-16.

The fixture comes from web/public/data/chart/171090.json on the data branch
(public-API prices; the earlier Naver copy had wrong bars on 09-14..09-23).
A crash to 46,550 on 07-29 rebounds to a ~74,000 ceiling, then rising lows
under that ceiling break out on 10-13 — the triangle starts after the crash
low, not at it. Future tails below are explicitly synthetic.
"""
from pathlib import Path

import pandas as pd

from batch.patterns import detect_all_patterns
from batch.patterns.swing import build_ctx
from batch.patterns.trend import _register_candidates


def candles(until=None):
    df = pd.read_csv(Path(__file__).parent / 'fixtures/171090_triangle.csv')
    return df if until is None else df[df.date <= until].reset_index(drop=True)


def triangles(df):
    return [h for h in detect_all_patterns(df) if h.kind == 'pat_tri_asc'
            and df.date.iloc[h.structure_span[0]] >= '2026-07-01']


def append_candle(df, close, high=None):
    previous = float(df.close.iloc[-1])
    row = dict(date='2026-10-09', open=previous, close=close,
               high=max(previous, close) + 100 if high is None else high,
               low=min(previous, close) - 100, volume=50000)
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def test_sunic_breakout_is_caught_after_the_crash_low():
    df = candles()
    hit, = triangles(df)
    assert df.date.iloc[hit.structure_span[0]] == '2026-08-07'
    assert df.date.iloc[hit.completed_at] == '2026-10-13'
    assert 73000 <= hit.neckline <= 75400
    assert len(hit.touch_points) >= 5
    # Recognized on 10-02 and completed on its own date, without later bars.
    done, = triangles(candles('2026-10-13'))
    assert done.completed_at == hit.completed_at and done.points == hit.points
    waiting, = triangles(candles('2026-10-12'))
    assert waiting.forming and waiting.pending == 'up' and not waiting.pending_against
    assert triangles(candles('2026-10-02'))[0].forming
    assert not triangles(candles('2026-10-01'))


def test_sunic_fixed_resistance_requires_close_confirmation():
    df = candles('2026-10-08')
    base, = triangles(df)
    assert base.forming and base.pending is None
    atr = build_ctx(df).atr[-1]
    wick = append_candle(df, 74000, high=base.neckline + .75*atr)
    assert triangles(wick)[0].forming
    first = append_candle(df, base.neckline + .8*atr)
    assert triangles(first)[0].forming and triangles(first)[0].pending == 'up'
    confirmed = append_candle(first, base.neckline + .8*atr)
    hit, = triangles(confirmed)
    assert hit.completed_at == len(confirmed)-1 and not hit.forming
    assert hit.touch_points == base.touch_points
    assert hit.neckline == base.neckline
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
