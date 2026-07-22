"""백테스트 엔진 단위 테스트 — 합성 데이터로 매칭·수익률·집계 검증."""

import numpy as np
import pandas as pd
import pytest

from batch.backtest.engine import aggregate, find_entries, measure
from batch.backtest.events import _cross_up, build_events


def _ind(close_list, rsi_list=None, macd=None, macd_signal=None):
    n = len(close_list)
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": close_list, "high": close_list, "low": close_list,
        "close": close_list, "volume": [100] * n,
        "rsi": rsi_list or [50.0] * n,
        "macd": macd or [0.0] * n,
        "macd_signal": macd_signal or [0.0] * n,
        "macd_hist": [0.0] * n,
        "bb_upper": [np.inf] * n, "bb_mid": close_list, "bb_lower": [0.0] * n,
        "pct_b": [0.5] * n, "bb_width": [0.2] * n,
    })
    return df


def test_cross_up():
    a = pd.Series([1.0, 2.0, 3.0, 2.0, 3.0])
    b = pd.Series([2.5, 2.5, 2.5, 2.5, 2.5])
    assert _cross_up(a, b) == [2, 4]
    assert _cross_up(pd.Series([25.0, 29.0, 31.0]), 30.0) == [2]


def test_trigger_only_strategy_and_returns():
    # 진입일(2) 종가 100 → 5일 후 110 (+10%)
    close = [100.0] * 3 + [102, 104, 106, 108, 110] + [100.0] * 60
    ind = _ind(close, macd=[-1, -1, 1] + [1] * 65, macd_signal=[0.0] * 68)
    events = build_events(ind)
    assert 2 in events["macd_golden"]

    strat = {"id": "t", "trigger": "macd_golden", "confirm": None}
    entries = find_entries(ind, events, strat)
    assert entries[0] == 2
    samples = measure(ind, [2])
    assert samples[5][0] == pytest.approx(10.0)


def test_trigger_when_filters():
    ind = _ind([100.0] * 70, macd=[-1, 1] + [1] * 68, macd_signal=[0.0] * 70)
    events = build_events(ind)
    assert 1 in events["macd_golden"]
    # macd < 0 조건: 발생일 macd=1이므로 탈락
    strat = {"id": "t", "trigger": "macd_golden", "when": [["macd", "<", 0]], "confirm": None}
    assert find_entries(ind, events, strat) == []


def test_confirm_sequence_with_when():
    # 트리거(golden)@1 → 확인(rsi_cross_up_30)@4, 그날 rsi=35(>=30 조건 통과)
    rsi = [25, 25, 25, 28, 35] + [50.0] * 65
    ind = _ind([100.0] * 70, rsi_list=rsi, macd=[-1, 1] + [1] * 68, macd_signal=[0.0] * 70)
    events = build_events(ind)
    assert 4 in events["rsi_cross_up_30"]

    strat = {
        "id": "t", "trigger": "macd_golden",
        "confirm": {"event": "rsi_cross_up_30", "within_days": 5, "when": [["rsi", ">=", 30]]},
    }
    assert find_entries(ind, events, strat) == [4]

    # 기한 2일이면 4-1=3 > 2 → 탈락
    strat2 = {
        "id": "t2", "trigger": "macd_golden",
        "confirm": {"event": "rsi_cross_up_30", "within_days": 2, "when": []},
    }
    assert find_entries(ind, events, strat2) == []


def test_duplicate_suppression():
    # 골든크로스가 5일 간격으로 반복 → 최소 보유기간(60일) 내 중복은 억제
    macd, sig = [], []
    for k in range(20):
        macd += [-1, 1, 1, 1, 1]
    ind = _ind([100.0] * 100, macd=macd[:100], macd_signal=[0.0] * 100)
    events = build_events(ind)
    strat = {"id": "t", "trigger": "macd_golden", "confirm": None}
    entries = find_entries(ind, events, strat)
    # 5일마다 발생하지만 min_gap=60 억제 → 100일 안에서 2건(1일, 66일)만
    assert len(entries) == 2
    assert entries[1] - entries[0] >= 60


def test_aggregate():
    agg = aggregate({5: [10.0, -5.0, 5.0], 10: [], 20: [1.0], 60: [2.0, 2.0]})
    assert agg["5"]["n"] == 3 and agg["5"]["win"] == pytest.approx(66.7)
    assert agg["10"] is None
    assert agg["60"]["mean"] == pytest.approx(2.0)
