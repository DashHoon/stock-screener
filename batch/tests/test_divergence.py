"""합성 데이터로 다이버전스 4종 판정을 검증한다.

가격/RSI 시퀀스를 직접 만들어 detect_divergences에 넣는다
(RSI는 계산값이 아니라 임의 시퀀스 — 판정 로직만 검증).
"""

import numpy as np
import pandas as pd

from batch.indicators.divergence import detect_divergences, find_pivots, latest_flags


def _series_with_pivots(pivot_positions, pivot_values, base, n, invert=False):
    """지정 위치에 뾰족한 극값이 오는 시퀀스 생성."""
    v = np.full(n, float(base))
    # invert=True → 저점 피벗: 이웃 봉이 피벗보다 높아야 local min이 된다
    sign = 1.0 if invert else -1.0
    for pos, val in zip(pivot_positions, pivot_values):
        v[pos] = val
        for d in (1, 2, 3):
            if 0 <= pos - d < n:
                v[pos - d] = val + sign * d * 2
            if 0 <= pos + d < n:
                v[pos + d] = val + sign * d * 2
    return pd.Series(v)


def _detect(price_low_vals=None, price_high_vals=None, rsi_vals=(30, 35),
            pivots=(10, 30), n=45, lows=True):
    """두 피벗을 가진 합성 쌍을 만들어 판정 결과를 돌려준다."""
    rsi = _series_with_pivots(pivots, rsi_vals, base=50, n=n, invert=lows)
    if lows:
        low = _series_with_pivots(pivots, price_low_vals, base=110, n=n, invert=True)
        high = low + 5
    else:
        high = _series_with_pivots(pivots, price_high_vals, base=90, n=n)
        low = high - 5
    return detect_divergences(high, low, rsi, left=3, right=3, min_bars=5, max_bars=60)


def test_find_pivots_basic():
    s = pd.Series([5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1.0])
    highs, lows = find_pivots(s, left=3, right=3)
    assert 4 in lows      # 최저점
    assert 8 in highs     # 최고점


def test_regular_bullish():
    # 가격 LL(100→95) + RSI HL(28→33)
    ev = _detect(price_low_vals=(100, 95), rsi_vals=(28, 33), lows=True)
    kinds = {e.kind for e in ev}
    assert "div_reg_bull" in kinds
    e = next(e for e in ev if e.kind == "div_reg_bull")
    assert (e.idx_from, e.idx_to) == (10, 30)
    assert e.confirmed_at == 33


def test_hidden_bullish():
    # 가격 HL(95→100) + RSI LL(33→28)
    ev = _detect(price_low_vals=(95, 100), rsi_vals=(33, 28), lows=True)
    assert {e.kind for e in ev} >= {"div_hid_bull"}


def test_regular_bearish():
    # 가격 HH(100→105) + RSI LH(72→65)
    ev = _detect(price_high_vals=(100, 105), rsi_vals=(72, 65), lows=False)
    assert {e.kind for e in ev} >= {"div_reg_bear"}


def test_hidden_bearish():
    # 가격 LH(105→100) + RSI HH(65→72)
    ev = _detect(price_high_vals=(105, 100), rsi_vals=(65, 72), lows=False)
    assert {e.kind for e in ev} >= {"div_hid_bear"}


def test_no_divergence_when_same_direction():
    # 가격 LL + RSI LL → 다이버전스 아님
    ev = _detect(price_low_vals=(100, 95), rsi_vals=(33, 28), lows=True)
    assert ev == []


def test_max_bars_filter():
    # 피벗 간격이 max_bars를 넘으면 무시
    rsi = _series_with_pivots((10, 100), (28, 33), base=50, n=120, invert=True)
    low = _series_with_pivots((10, 100), (100, 95), base=110, n=120, invert=True)
    ev = detect_divergences(low + 5, low, rsi, left=3, right=3,
                            min_bars=5, max_bars=60)
    assert ev == []


def test_latest_flags_recency():
    ev = _detect(price_low_vals=(100, 95), rsi_vals=(28, 33), lows=True)
    # 확정 봉(33) 직후면 플래그 on
    assert latest_flags(ev, last_idx=33, recent_bars=3)["div_reg_bull"]
    assert latest_flags(ev, last_idx=35, recent_bars=3)["div_reg_bull"]
    # 오래 지나면 off
    assert not latest_flags(ev, last_idx=44, recent_bars=3)["div_reg_bull"]
