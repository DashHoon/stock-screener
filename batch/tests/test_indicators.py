import numpy as np
import pandas as pd
import pytest

from batch.indicators.core import bollinger, macd, rsi


def test_rsi_all_up_is_100():
    s = pd.Series(np.arange(1, 40, dtype=float))
    assert rsi(s).iloc[-1] == pytest.approx(100.0)


def test_rsi_all_down_is_0():
    s = pd.Series(np.arange(40, 1, -1, dtype=float))
    assert rsi(s).iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_rsi_known_value():
    # StockCharts RSI 튜토리얼 원본 데이터 — 공표값: 첫 RSI 70.53, 마지막 57.97
    closes = pd.Series([
        44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245,
        45.8433, 46.0826, 45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028,
        46.0328, 46.4116, 46.2222, 45.6439,
    ])
    r = rsi(closes)
    assert r.iloc[14] == pytest.approx(70.53, abs=0.01)
    assert r.iloc[-1] == pytest.approx(57.97, abs=0.01)


def test_rsi_warmup_is_nan():
    s = pd.Series(np.random.default_rng(0).normal(100, 1, 30).cumsum() + 1000)
    r = rsi(s)
    assert r.iloc[:14].isna().all()
    assert r.iloc[14:].notna().all()
    assert ((r.dropna() >= 0) & (r.dropna() <= 100)).all()


def test_macd_columns_and_hist_identity():
    s = pd.Series(np.random.default_rng(1).normal(0, 1, 100).cumsum() + 500)
    m = macd(s)
    assert list(m.columns) == ["macd", "macd_signal", "macd_hist"]
    np.testing.assert_allclose(m["macd_hist"], m["macd"] - m["macd_signal"])


def test_macd_constant_series_is_zero():
    s = pd.Series([100.0] * 60)
    m = macd(s)
    assert abs(m["macd"].iloc[-1]) < 1e-9
    assert abs(m["macd_hist"].iloc[-1]) < 1e-9


def test_bollinger_basic():
    s = pd.Series(np.random.default_rng(2).normal(0, 5, 100).cumsum() + 1000)
    b = bollinger(s)
    tail = b.dropna()
    assert (tail["bb_upper"] >= tail["bb_mid"]).all()
    assert (tail["bb_mid"] >= tail["bb_lower"]).all()
    # 종가가 정확히 중심선이면 %B = 0.5
    flat = pd.Series([100.0] * 19 + [100.0] * 20)
    # 상수 시계열은 표준편차 0 → 밴드 붕괴, pct_b는 NaN이어야 한다 (0으로 나누기 방어 확인)
    bf = bollinger(flat)
    assert bf["bb_width"].dropna().eq(0).all()


def test_bollinger_pct_b_position():
    # 마지막 값이 20일 최고보다 훨씬 크면 %B > 1
    s = pd.Series([100.0 + i * 0.1 for i in range(40)] + [200.0])
    b = bollinger(s)
    assert b["pct_b"].iloc[-1] > 1
