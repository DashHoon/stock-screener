"""나머지 패턴(H&S·3중·라운드·삼각형·쐐기·플래그) 합성 데이터 테스트."""

import numpy as np
import pandas as pd

from batch.patterns import trend
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


def test_broadening_wedge_rise():
    # 고점열 상승(110→146, 봉당 +2.0) + 저점열 완만히 상승(100→112, 봉당 +0.67)
    # → 폭 확대. 마지막에 상승 지지선을 아래로 이탈 → 완성(하락 시그널).
    seq = [100.0] * 3
    tops = [110, 122, 134, 146]
    bots = [100, 104, 108, 112]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 6) + _leg(t, b, 6)
    seq += _leg(seq[-1], 96, 8) + [96.0] * 8      # 하단 이탈
    df = _df(seq)
    hits = [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"]
    assert hits and hits[0].completed_at is not None


def test_broadening_wedge_fall():
    # 고점열 완만히 하락(130→118) + 저점열 가파르게 하락(118→91) → 폭 확대.
    # 마지막에 하락 저항선을 위로 돌파 → 완성(상승 시그널).
    # 진폭은 현실 수준(끝 폭 ≈ 가격의 30%)으로 잡아 전체 창이 잠식 게이트와
    # 무관하게 깔끔히 검출되도록 한다. (게이트는 창 단위 상한이라 더 큰 진폭도
    # 부분창으로는 검출된다 — 이 테스트의 목적은 게이트가 아니라 분류·완성이다.)
    seq = [124.0] * 3
    tops = [130, 126, 122, 118]
    bots = [118, 109, 100, 91]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 6) + _leg(t, b, 6)
    seq += _leg(seq[-1], 125, 8) + [125.0] * 8    # 상단 돌파
    df = _df(seq)
    hits = [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_fall"]
    assert hits and hits[0].completed_at is not None


def test_broadening_wedge_with_curved_boundary():
    # 감속 상승 랠리 — 고점열(110→121.5→130)이 곡선을 그려 한 직선에 0.5 ATR
    # 터치 3개가 정렬될 수 없다 (코스피 2026-05~07 실측 기하의 축소판: 세 번째
    # 극점이 선에서 ~0.6 ATR). 확대 쐐기의 터치 게이트는 지지 판정(1 ATR 근접)
    # 기준이므로 이 구조를 잡아야 한다 — 엄격 터치(합5)로 되돌리면 이 테스트가
    # 깨진다.
    seq = [97.0] * 3
    tops = [110, 121.5, 130]
    bots = [100, 104.5, 109]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 6) + _leg(t, b, 6)
    seq += _leg(seq[-1], 102, 9) + [102.0] * 8    # 상승 지지선 하향 이탈
    df = _df(seq)
    hits = [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"]
    assert hits and hits[0].completed_at is not None


def test_trend_engulfing_fan_is_not_broadening_wedge(monkeypatch):
    # 대세 상승 전체를 감싸는 부채꼴 — 기울기·확대비·K 게이트는 다 통과하지만
    # 끝 폭이 가격의 절반이라 패턴이 아니라 추세 자체다 (코스피 2025-08~2026-06
    # 실측 사례의 축소판). 이 파형은 폭 게이트(BWEDGE_WIDTH_MAX_PCT)에 걸린다.
    # 주의: 잠식 게이트는 '창' 단위 상한이라, 상한을 넘는 거대 부채꼴이라도 마지막
    # 몇 스윙의 부분창이 상한 안이면 그 부분창으로는 방출될 수 있다 — 이 파형은
    # 모든 부분창이 함께 걸리도록 급하게 벌어진다.
    seq = [105.0] * 3
    tops = [110, 135, 160, 185]
    bots = [100, 107, 114, 121]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 6) + _leg(t, b, 6)
    seq += _leg(seq[-1], 100, 10) + [100.0] * 8   # 하단 이탈
    df = _df(seq)
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"] == []
    # 게이트만 풀면 잡히는 파형인지 확인 — 미검출 사유가 실제로 이 게이트임을 보장
    monkeypatch.setattr(trend, "BWEDGE_TRAVEL_MAX_PCT", 1e9)
    monkeypatch.setattr(trend, "BWEDGE_WIDTH_MAX_PCT", 1e9)
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"]


def test_bwedge_travel_gate_is_wired(monkeypatch):
    # 이동(travel) 게이트는 대부분 폭 게이트에 가려지는 백스톱이다 (실측: 단독
    # 발화 0.3% — 부분창 방출 구조상 자연 파형으로 단독 고정이 어렵다). 대신
    # 배선을 고정한다: 정상 검출되는 파형이 이동 상한을 조이면 사라져야 하며,
    # 게이트가 제거되거나 다른 양을 재게 되면 이 테스트가 깨진다.
    seq = [100.0] * 3
    tops = [110, 122, 134, 146]
    bots = [100, 104, 108, 112]
    for t, b in zip(tops, bots):
        seq += _leg(seq[-1], t, 6) + _leg(t, b, 6)
    seq += _leg(seq[-1], 96, 8) + [96.0] * 8
    df = _df(seq)
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"]
    monkeypatch.setattr(trend, "BWEDGE_TRAVEL_MAX_PCT", 10.0)  # 실측 이동 ~20%
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"] == []


def test_parallel_channel_is_not_broadening_wedge(monkeypatch):
    # 거의 평행한 상승 채널(위 +2.0, 아래 +1.7 = 기울기비 0.85).
    # 창이 길면 미세한 기울기 차만으로 폭이 1.5배를 넘어 확대비 게이트를
    # 통과한다 — BWEDGE_SLOPE_K가 이런 채널을 걸러내야 한다.
    seq = [104.0] * 3
    seq += _leg(104, 110, 6)          # 고점 x=8
    seq += _leg(110, 102.1, 3)        # 저점 x=11
    seq += _leg(102.1, 134, 9)        # 고점 x=20
    seq += _leg(134, 122.5, 3)        # 저점 x=23
    seq += _leg(122.5, 158, 9)        # 고점 x=32
    seq += _leg(158, 142.9, 3)        # 저점 x=35
    seq += _leg(142.9, 182, 9)        # 고점 x=44
    seq += _leg(182, 150, 10) + [150.0] * 8   # 하단 이탈
    df = _df(seq)
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"] == []
    # 게이트만 풀면 잡히는 파형인지 확인 — 통과 사유가 '게이트'임을 보장한다
    monkeypatch.setattr(trend, "BWEDGE_SLOPE_K", 1.0)
    assert [p for p in detect_trendline_patterns(df) if p.kind == "pat_bwedge_rise"]


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
