"""컵앤핸들 탐지 합성 데이터 테스트."""

import numpy as np
import pandas as pd

from batch.patterns.cup import detect_cup_handle


def _df(closes):
    closes = [float(c) for c in closes]
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [1] * n,
    })


def _cup_shape(rim=100, depth_pct=20, cup_len=60, handle_len=10,
               handle_dip_pct=5, breakout=True, v_shape=False, pad=10):
    """컵앤핸들 종가 시퀀스: 상승 → 좌림 → U자 컵 → 우림 → 핸들 → (돌파)"""
    seq = [rim * (0.9 + 0.1 * i / 10) for i in range(10)]  # 좌림으로 상승
    seq += [rim * 1.002]  # 좌림 (단독 극값)
    bottom = rim * (1 - depth_pct / 100)
    if v_shape:
        half = cup_len // 2
        seq += [rim - (rim - bottom) * i / half for i in range(1, half)]
        seq += [bottom]
        seq += [bottom + (rim - bottom) * i / half for i in range(1, half + 1)]
    else:
        # 포물선 U자
        for i in range(1, cup_len):
            t = i / cup_len
            seq.append(bottom + (rim - bottom) * (2 * t - 1) ** 2)
    seq += [rim * 1.001]  # 우림
    handle_bottom = rim * (1 - handle_dip_pct / 100)
    half_h = max(handle_len // 2, 1)
    seq += [rim - (rim - handle_bottom) * i / half_h for i in range(1, half_h + 1)]
    seq += [handle_bottom + (rim - handle_bottom) * i / half_h for i in range(1, half_h)]
    if breakout:
        seq += [rim * 1.03 + i * 0.1 for i in range(pad)]
    else:
        seq += [rim * 0.99 - (i % 3) * 0.2 for i in range(pad)]
    return seq


def test_cup_handle_completed():
    df = _df(_cup_shape())
    hits = detect_cup_handle(df)
    assert len(hits) == 1
    p = hits[0]
    assert p.completed_at is not None and not p.forming
    assert p.i_left < p.i_bottom < p.i_right < p.completed_at
    # 바닥이 컵의 가운데 부근
    assert 0.2 < (p.i_bottom - p.i_left) / (p.i_right - p.i_left) < 0.8


def test_cup_handle_forming():
    df = _df(_cup_shape(breakout=False))
    hits = detect_cup_handle(df)
    assert len(hits) == 1
    assert hits[0].forming and hits[0].completed_at is None


def test_reject_v_shape():
    # 뾰족한 V자 반등은 컵이 아님 (바닥권 체류 부족)
    df = _df(_cup_shape(v_shape=True))
    assert detect_cup_handle(df) == []


def test_reject_too_deep_handle():
    # 핸들이 컵 깊이의 절반 아래까지 파이면 무효
    df = _df(_cup_shape(depth_pct=20, handle_dip_pct=15, breakout=True))
    assert detect_cup_handle(df) == []


def test_reject_shallow_cup():
    # 깊이 5%는 컵으로 보기엔 얕음 (최소 10%)
    df = _df(_cup_shape(depth_pct=5))
    assert detect_cup_handle(df) == []


def _asymmetric_cup(bottom_at=.25, breakout=True):
    seq = _cup_shape(breakout=breakout)
    for i in range(1, 60):
        t = i / 60
        side = (bottom_at - t) / bottom_at if t <= bottom_at else (t - bottom_at) / (1 - bottom_at)
        seq[10 + i] = 80 + 20 * side ** 2
    return seq


def test_asymmetric_round_cups_survive_full_pipeline():
    from batch.patterns import detect_all_patterns
    for pos in (.25, .75):
        df = _df(_asymmetric_cup(pos))
        hits = [h for h in detect_all_patterns(df) if h.kind == 'pat_cup_handle']
        assert len(hits) == 1 and hits[0].completed_at == 80
        prefix = [h for h in detect_all_patterns(df.iloc[:81]) if h.kind == 'pat_cup_handle']
        assert prefix[0].points == hits[0].points


def test_early_confirmed_handle_is_forming_not_completed():
    from batch.patterns import detect_all_patterns
    seq = _cup_shape()
    hits = [h for h in detect_all_patterns(_df(seq[:74])) if h.kind == 'pat_cup_handle']
    assert len(hits) == 1 and hits[0].forming
    assert hits[0].completed_at is None and hits[0].confirmed_at == 73
    assert not detect_cup_handle(_df(seq[:72]))


def test_single_bottom_wick_does_not_hide_a_rounded_base():
    df = _df(_cup_shape())
    df.loc[40, 'low'] = 75
    assert detect_cup_handle(df)


def test_extreme_asymmetry_and_early_break_remain_excluded():
    assert not detect_cup_handle(_df(_asymmetric_cup(.1)))
    seq = _cup_shape()[:74] + [104., 105., 106.]
    assert not detect_cup_handle(_df(seq))
