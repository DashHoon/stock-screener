import pandas as pd

from batch.indicators.resample import resample_ohlcv


def _daily():
    # 2주(월~금 + 월~수), 하루 1봉
    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
             "2026-01-12", "2026-01-13", "2026-01-14"]
    n = len(dates)
    return pd.DataFrame({
        "date": dates,
        "open": [100 + i for i in range(n)],
        "high": [110 + i for i in range(n)],
        "low": [90 + i for i in range(n)],
        "close": [105 + i for i in range(n)],
        "volume": [1000] * n,
    })


def test_weekly_ohlcv():
    w = resample_ohlcv(_daily(), "w")
    assert len(w) == 2
    first = w.iloc[0]
    assert first["date"] == "2026-01-09"  # 주의 마지막 거래일
    assert first["open"] == 100           # 월요일 시가
    assert first["high"] == 114           # 금요일 고가 (최대)
    assert first["low"] == 90             # 월요일 저가 (최소)
    assert first["close"] == 109          # 금요일 종가
    assert first["volume"] == 5000
    # 미완성 주(월~수)도 포함
    assert w.iloc[1]["date"] == "2026-01-14"
    assert w.iloc[1]["volume"] == 3000


def test_monthly_ohlcv():
    m = resample_ohlcv(_daily(), "m")
    assert len(m) == 1
    row = m.iloc[0]
    assert row["date"] == "2026-01-14"
    assert row["open"] == 100 and row["close"] == 112
    assert row["volume"] == 8000
