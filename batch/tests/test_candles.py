"""캔들 패턴 탐지 합성 데이터 테스트."""

import pandas as pd

from batch.indicators.candles import detect_candles


def _df(rows):
    """rows: [(open, high, low, close), ...]"""
    n = len(rows)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": [r[0] for r in rows],
        "high": [r[1] for r in rows],
        "low": [r[2] for r in rows],
        "close": [r[3] for r in rows],
        "volume": [1] * n,
    })


def _downtrend(start=120, days=8):
    # 완만한 하락 (직전 추세 조건 충족용)
    return [(start - i, start - i + 0.3, start - i - 1.3, start - i - 1) for i in range(days)]


def _uptrend(start=100, days=8):
    return [(start + i, start + i + 1.3, start + i - 0.3, start + i + 1) for i in range(days)]


def test_bullish_engulfing():
    rows = _downtrend()
    last = rows[-1][3]                       # ~112
    rows.append((last, last + 0.2, last - 2.2, last - 2))       # 음봉 (몸통 2)
    rows.append((last - 2.5, last + 1.7, last - 2.7, last + 1.5))  # 몸통이 전봉을 감싸는 양봉
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_engulf_bull"]


def test_hammer_needs_downtrend():
    rows = _downtrend()
    last = rows[-1][3]
    # 긴 아래꼬리 망치: 몸통 0.5, 아래꼬리 3, 위꼬리 0.1
    rows.append((last, last + 0.6, last - 3, last + 0.5))
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_hammer"]

    # 같은 봉이라도 상승 후면 망치형 아님
    rows2 = _uptrend()
    last2 = rows2[-1][3]
    rows2.append((last2, last2 + 0.6, last2 - 3, last2 + 0.5))
    hits2 = detect_candles(_df(rows2))
    assert len(rows2) - 1 not in hits2.get("cdl_hammer", [])


def test_shooting_star():
    rows = _uptrend()
    last = rows[-1][3]
    rows.append((last, last + 3, last - 0.1, last - 0.5))  # 긴 위꼬리 음봉
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_shooting"]


def test_doji():
    rows = _uptrend()
    last = rows[-1][3]
    rows.append((last, last + 2, last - 2, last + 0.05))  # 몸통 극소, 변동폭 큼
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_doji"]


def test_morning_star():
    rows = _downtrend(days=9)
    last = rows[-1][3]                                   # 하락 끝
    rows.append((last, last + 0.2, last - 3.2, last - 3))          # 1: 큰 음봉
    rows.append((last - 3.4, last - 3.0, last - 3.8, last - 3.5))  # 2: 작은 몸통
    rows.append((last - 3.2, last + 0.2, last - 3.4, last - 0.5))  # 3: 큰 양봉, 1봉 중간 위
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_morning"]


def test_piercing_line():
    rows = _downtrend()
    last = rows[-1][3]
    rows.append((last, last + 0.2, last - 2.2, last - 2))        # 큰 음봉 (몸통 last~last-2)
    rows.append((last - 2.5, last - 0.4, last - 2.7, last - 0.6))  # 아래서 출발, 중간 위 마감
    hits = detect_candles(_df(rows))
    assert len(rows) - 1 in hits["cdl_pierce"]
