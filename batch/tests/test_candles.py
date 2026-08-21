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


def _bars(rows):
    """rows = [(o,h,l,c,vol), ...] → detect_candles 입력 형식"""
    import pandas as pd
    o, h, l, c, v = zip(*rows)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=len(rows)).astype(str),
        "open": o, "high": h, "low": l, "close": c, "volume": v,
    })


def test_hanging_vs_hammer_is_position():
    """같은 모양이라도 위치가 다르면 다른 패턴이다.

    망치형과 교수형은 몸통·꼬리 비율이 같다. 하락 뒤면 망치(반등), 상승 뒤면
    교수형(경고)이다 — 이 구분이 깨지면 둘 중 하나가 늘 오탐이 된다.
    """
    def shape(px):                                  # 긴 아래꼬리, 짧은 몸통
        return (px, px * 1.005, px * 0.92, px * 1.004, 1000)

    down = [(110 - i, 111 - i, 109 - i, 110 - i, 1000) for i in range(8)]
    up = [(100 + i, 101 + i, 99 + i, 100.5 + i, 1000) for i in range(8)]

    got_down = detect_candles(_bars(down + [shape(102)]))
    got_up = detect_candles(_bars(up + [shape(108)]))

    assert got_down.get("cdl_hammer"), "하락 뒤 같은 모양은 망치형"
    assert not got_down.get("cdl_hanging"), "하락 뒤에는 교수형이 아니다"
    assert got_up.get("cdl_hanging"), "상승 뒤 같은 모양은 교수형"
    assert not got_up.get("cdl_hammer"), "상승 뒤에는 망치형이 아니다"


def test_wick_top_needs_repetition_and_volume():
    """긴 윗꼬리 반복 — 한 번으로는 안 잡히고, 거래량이 없으면 안 잡힌다.

    한 봉짜리는 유성형이 이미 잡는다. 이 패턴이 보는 건 '되풀이'다.
    거래량 없이 생긴 윗꼬리는 매도 압력이 아니라 한산해서 생긴 자국이다.
    """
    base = [(100 + i, 101 + i, 99 + i, 100.5 + i, 1000) for i in range(40)]  # 상승 추세

    def wick(px, vol):
        return (px, px * 1.06, px * 0.995, px * 1.005, vol)   # 위꼬리 긴 봉

    # 거래량 실린 위꼬리 3개 (창 10봉 안)
    loud = base + [wick(140, 3000), (140, 141, 139, 140, 1000),
                   wick(141, 3000), (141, 142, 140, 141, 1000), wick(141, 3000)]
    # 같은 모양인데 거래량이 평균 아래
    quiet = base + [wick(140, 100), (140, 141, 139, 140, 1000),
                    wick(141, 100), (141, 142, 140, 141, 1000), wick(141, 100)]

    assert detect_candles(_bars(loud)).get("cdl_wick_top"), "거래량 실린 반복은 잡혀야 한다"
    assert not detect_candles(_bars(quiet)).get("cdl_wick_top"), "거래량 없으면 잡지 않는다"
