"""나머지 패턴(H&S·3중·라운드·삼각형·쐐기·플래그) 합성 데이터 테스트."""

import numpy as np
import pandas as pd

from batch.patterns.flag import detect_flags
from batch.patterns.multi import detect_head_shoulders, detect_triple
from batch.patterns.round import detect_round
from batch.patterns.trend import detect_trendline_patterns


def _df(closes, highs=None, lows=None):
    closes = [float(c) for c in closes]
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": closes,
        "high": highs if highs is not None else [c * 1.005 for c in closes],
        "low": lows if lows is not None else [c * 0.995 for c in closes],
        "close": closes,
        "volume": [1] * n,
    })


def _leg(a, b, steps):
    return [a + (b - a) * i / steps for i in range(1, steps + 1)]


def test_inverse_head_shoulders():
    # 어깨 90 - 머리 80 - 어깨 91, 넥라인 ~100 → 상향 돌파
    seq = [105.0] * 3
    seq += _leg(105, 90, 8) + [89.5] + _leg(90, 100, 8)      # 왼어깨→넥
    seq += _leg(100, 80, 8) + [79.5] + _leg(80, 101, 8)      # 머리→넥
    seq += _leg(101, 91, 8) + [90.5] + _leg(91, 108, 10)     # 오른어깨→돌파
    seq += [108.0 + i * 0.1 for i in range(10)]
    df = _df(seq)
    hits = [p for p in detect_head_shoulders(df) if p.kind == "pat_hs_inv"]
    assert hits and hits[0].completed_at is not None


def test_triple_bottom():
    seq = [120.0] * 3 + _leg(120, 100, 6)
    for _ in range(3):                       # 바닥 3개 (100±1) + 반등 110
        seq += [99.5] + _leg(100, 110, 6) + _leg(110, 100.5, 6)
    seq = seq[: -6]                          # 마지막 하락 제거
    seq += _leg(110, 115, 6) + [115.0 + i * 0.1 for i in range(10)]
    df = _df(seq)
    hits = [p for p in detect_triple(df) if p.kind == "pat_triple_bottom"]
    assert hits and hits[0].completed_at is not None


def test_round_bottom():
    # 완만한 접시: 림 100 → 바닥 75 (포물선, 120봉) → 회복 → 돌파
    seq = [95.0] * 3 + _leg(95, 100, 5)
    span = 120
    for i in range(1, span):
        t = i / span
        seq.append(75 + 25 * (2 * t - 1) ** 2)
    seq += _leg(100, 106, 8) + [106.0] * 10
    df = _df(seq)
    hits = [p for p in detect_round(df) if p.kind == "pat_round_bottom"]
    assert hits and hits[0].completed_at is not None


def test_ascending_triangle():
    # 위 수평(100) + 아래 상승(88→97), 피벗이 뚜렷하게 생기도록 지그재그
    seq = [90.0] * 3
    bottoms = [88, 91, 94, 97]
    for b in bottoms:
        seq += _leg(seq[-1], 100, 5) + _leg(100, b, 5)
    seq += _leg(seq[-1], 103, 4) + [103.0 + i * 0.1 for i in range(8)]  # 위 돌파
    df = _df(seq)
    hits = [p for p in detect_trendline_patterns(df) if p.kind == "pat_tri_asc"]
    assert hits and hits[0].completed_at is not None


def test_falling_wedge():
    # 고점열 하락(112→103), 저점열 더 완만히 하락(100→97) → 수렴, 위 돌파
    seq = [100.0] * 3
    tops = [112, 108, 104, 100]
    bots = [100, 98, 96, 94]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 5) + _leg(t, b, 5)
    seq += _leg(seq[-1], 106, 4) + [106.0 + i * 0.1 for i in range(8)]
    df = _df(seq)
    hits = [p for p in detect_trendline_patterns(df) if p.kind == "pat_wedge_fall"]
    assert hits and hits[0].completed_at is not None


def test_bull_flag():
    # 깃대 +30% (10봉) → 8봉 얕은 조정 → 재돌파
    seq = [100.0] * 3 + _leg(100, 130, 10)
    seq += [130 - 3 * (i % 4) / 3 - i * 0.3 for i in range(1, 9)]  # 얕은 눌림
    seq += _leg(seq[-1], 133, 3) + [133.0] * 8
    df = _df(seq)
    hits = [p for p in detect_flags(df) if p.kind == "pat_flag_bull"]
    assert hits and hits[0].completed_at is not None


def test_flag_rejects_deep_pullback():
    # 조정이 깃대의 70%까지 파이면 플래그 아님
    seq = [100.0] * 3 + _leg(100, 130, 10)
    seq += _leg(130, 109, 8)   # 깊은 되돌림 (-21 = 70%)
    seq += [109.0] * 10
    df = _df(seq)
    assert [p for p in detect_flags(df) if p.kind == "pat_flag_bull" and p.completed_at] == []
