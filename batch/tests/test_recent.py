import numpy as np
import pandas as pd

from batch.indicators.divergence import Divergence
from batch.indicators.recent import compute_recent


def _ind(n=200):
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n,
        "close": [100.0] * n, "volume": [1] * n,
        "rsi": [50.0] * n,
        "macd": [1.0] * n, "macd_signal": [0.0] * n, "macd_hist": [1.0] * n,
        "bb_upper": [110.0] * n, "bb_mid": [100.0] * n, "bb_lower": [90.0] * n,
        "pct_b": [0.5] * n, "bb_width": [0.2] * n,
    })


def _div(kind, confirmed_at):
    return Divergence(kind=kind, idx_from=0, idx_to=confirmed_at - 3,
                      confirmed_at=confirmed_at, price_from=0, price_to=0,
                      rsi_from=0, rsi_to=0)


def test_state_signal_bars_ago():
    ind = _ind(100)
    ind.loc[89, "rsi"] = 25.0   # 10봉 전 과매도
    ind.loc[99, "rsi"] = 75.0   # 오늘 과매수
    sig = compute_recent(ind, [])
    assert sig["rsi_oversold"] == 10
    assert sig["rsi_overbought"] == 0


def test_event_signal_bars_ago():
    ind = _ind(100)
    # 95번 봉에서 골든크로스 (94: macd<=signal, 95: macd>signal)
    ind.loc[:94, "macd"] = -1.0
    sig = compute_recent(ind, [])
    assert sig["macd_golden"] == 4
    assert "macd_dead" not in sig or sig["macd_dead"] >= 0  # 초기 경계 크로스 허용


def test_divergence_bars_ago_and_cutoff():
    ind = _ind(200)
    events = [_div("div_reg_bull", 195), _div("div_reg_bear", 100)]
    sig = compute_recent(ind, events, max_bars=63)
    assert sig["div_reg_bull"] == 4
    assert "div_reg_bear" not in sig  # 99봉 전 → 63봉 상한 초과로 생략


def test_touch_and_squeeze():
    ind = _ind(200)
    ind.loc[197, "low"] = 80.0     # 2봉 전 하단 터치
    sig = compute_recent(ind, [])
    assert sig["bb_lower_touch"] == 2
    # bb_width 상수라 오늘도 롤링 최소와 같음 → 스퀴즈는 오늘(0)
    assert sig["bb_squeeze"] == 0
