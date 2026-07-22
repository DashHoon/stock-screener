"""쌍바닥/더블탑 탐지 합성 데이터 테스트."""

import pandas as pd

from batch.patterns.double import detect_double_patterns


def _df(closes):
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": closes, "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes], "close": closes,
        "volume": [1] * n,
    })


def _w_shape(bottom1=100, peak=115, bottom2=101, breakout=True, n_pad=20):
    """W자 형태 종가 시퀀스 생성: 하락 → 바닥1 → 반등 → 바닥2 → (돌파).

    피벗 판정이 엄격 부등호라 극값이 이웃과 동률이 되지 않게 구성한다.
    """
    seq = []
    seq += [130 - i * 2 for i in range(15)]          # 하락 (130→102)
    seq += [bottom1]                                   # 바닥1 (idx 15)
    seq += [bottom1 + (peak - bottom1) * i / 10 for i in range(1, 11)]  # 반등 → peak
    seq += [peak - (peak - bottom2) * i / 10 for i in range(1, 10)]     # 재하락 (bottom2 직전까지)
    seq += [bottom2]                                   # 바닥2 (단독 극값)
    if breakout:
        seq += [bottom2 + (peak * 1.05 - bottom2) * i / 8 for i in range(1, 9)]
        seq += [peak * 1.05 + i * 0.1 for i in range(n_pad)]  # 돌파 후 완만한 상승
    else:
        seq += [bottom2 + 2 + (i % 3) * 0.5 for i in range(n_pad)]  # 넥라인 아래 횡보
    return seq


def test_double_bottom_completed():
    df = _df(_w_shape())
    hits = [p for p in detect_double_patterns(df) if p.kind == "pat_double_bottom"]
    assert len(hits) == 1
    p = hits[0]
    assert p.completed_at is not None and not p.forming
    assert p.i1 < p.ip < p.i2 < p.completed_at
    # 넥라인은 반등 고점 부근
    assert 110 < p.neckline < 120


def test_double_bottom_forming():
    df = _df(_w_shape(breakout=False))
    hits = [p for p in detect_double_patterns(df) if p.kind == "pat_double_bottom"]
    assert len(hits) == 1
    assert hits[0].forming and hits[0].completed_at is None


def test_reject_dissimilar_bottoms():
    # 두 바닥 가격 차 10% → 허용오차 3% 초과로 기각
    df = _df(_w_shape(bottom1=100, bottom2=110))
    assert [p for p in detect_double_patterns(df) if p.kind == "pat_double_bottom"] == []


def test_reject_shallow_pattern():
    # 반등 고점이 바닥보다 2%만 높음 → 최소 깊이 5% 미달로 기각
    df = _df(_w_shape(bottom1=100, peak=102, bottom2=100))
    assert [p for p in detect_double_patterns(df) if p.kind == "pat_double_bottom"] == []


def test_double_top_completed():
    # 쌍바닥의 상하 반전: 상승 → 꼭대기1 → 눌림 → 꼭대기2 → 하향 돌파
    seq = [70 + i * 2 for i in range(15)]
    seq += [100]
    seq += [100 - 15 * i / 10 for i in range(1, 11)]
    seq += [85 + 14 * i / 10 for i in range(1, 10)]
    seq += [99]
    seq += [99 - (99 - 80) * i / 8 for i in range(1, 9)]
    seq += [80.0 - i * 0.1 for i in range(20)]
    df = _df(seq)
    hits = [p for p in detect_double_patterns(df) if p.kind == "pat_double_top"]
    assert len(hits) == 1
    assert hits[0].completed_at is not None
