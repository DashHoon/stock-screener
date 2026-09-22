"""Cached SK Hynix reference: five contacts, followed by a causal breakdown."""
from pathlib import Path

import pandas as pd

from batch.patterns.trend import detect_trendline_patterns


def test_hynix_five_contacts_and_frozen_breakdown():
    df = pd.read_csv(Path(__file__).parent / 'fixtures/000660_broadening.csv',
                     parse_dates=['date']).set_index('date')
    def target(frame):
        return [h for h in detect_trendline_patterns(frame)
                if h.kind == 'pat_bwedge_rise'
                and frame.index[h.structure_span[0]] == pd.Timestamp('2026-05-15')]
    full = target(df)
    assert len(full) == 1
    hit = full[0]
    assert len(hit.touch_points) == 5
    assert df.index[hit.completed_at] == pd.Timestamp('2026-07-13')
    earlier = target(df.loc[:'2026-06-30'])
    assert len(earlier) == 1 and earlier[0].forming
    assert earlier[0].touch_points == hit.touch_points
    before_break = target(df.loc[:'2026-07-10'])
    assert all(h.completed_at is None for h in before_break)
