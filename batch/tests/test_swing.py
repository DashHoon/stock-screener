"""스윙(ZigZag) 층 단위 테스트 — 교대·임계·확정 시점·추세선."""

import numpy as np
import pandas as pd

from batch.patterns.swing import build_ctx, fit_swing_trendline, wilder_atr, zigzag


def _df(closes, spread=0.005):
    closes = [float(c) for c in closes]
    n = len(closes)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n).astype(str),
        "open": closes,
        "high": [c * (1 + spread) for c in closes],
        "low": [c * (1 - spread) for c in closes],
        "close": closes,
        "volume": [1] * n,
    })


def _leg(a, b, steps):
    return [a + (b - a) * i / steps for i in range(1, steps + 1)]


def test_atr_positive_and_scaled():
    df = _df([100] * 5 + _leg(100, 120, 10) + _leg(120, 105, 10))
    atr = wilder_atr(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy())
    assert len(atr) == len(df)
    assert (atr > 0).all()
    # 봉당 ~2% 움직임 + 1% 봉폭 → ATR은 가격의 1~4% 수준이어야 정상
    assert 0.5 < atr[-1] < 6.0


def test_zigzag_alternates_and_filters_noise():
    # 큰 스윙(±15%) 사이에 1% 잔파동 — 잔파동은 스윙이 되면 안 된다
    seq = [100.0] * 3
    seq += _leg(100, 115, 8)                     # 상승
    seq += [115 - 0.5 * (i % 2) for i in range(6)]  # 고점권 1% 잔파동
    seq += _leg(115, 98, 8)                      # 하락
    seq += _leg(98, 112, 8)                      # 상승
    df = _df(seq)
    ctx = build_ctx(df)
    sw = ctx.minor
    confirmed = [s for s in sw if s.confirmed_at is not None]
    # 교대 검증
    for a, b in zip(sw[:-1], sw[1:]):
        assert a.is_high != b.is_high
        assert a.idx < b.idx
    # 잔파동 구간에서 스윙이 나오지 않아야: 확정 스윙은 저-고-저 3개 수준
    assert 2 <= len(confirmed) <= 4
    highs = [s for s in confirmed if s.is_high]
    assert highs and abs(highs[0].price - 115 * 1.005) / 115 < 0.02


def test_zigzag_confirmation_is_causal():
    # 스윙 확정 봉은 극점 이후 임계 반전이 일어난 봉 — 항상 극점보다 뒤
    seq = [100.0] * 3 + _leg(100, 120, 10) + _leg(120, 100, 10) + _leg(100, 118, 10)
    df = _df(seq)
    ctx = build_ctx(df)
    for s in ctx.minor:
        if s.confirmed_at is not None:
            assert s.confirmed_at > s.idx


def test_zigzag_last_extreme_is_provisional():
    seq = [100.0] * 3 + _leg(100, 120, 10) + _leg(120, 104, 8)
    df = _df(seq)
    ctx = build_ctx(df)
    assert ctx.minor and ctx.minor[-1].confirmed_at is None


def test_major_coarser_than_minor():
    # 중간 파동(고저폭 포함 ~5.5%)은 minor에는 잡히고 major(임계 ~6%)에는 안 잡힌다
    seq = [100.0] * 3
    for _ in range(3):
        seq += _leg(100, 104.5, 8) + _leg(104.5, 100, 8)
    seq += _leg(100, 130, 12) + _leg(130, 100, 12)   # 큰 파동
    df = _df(seq)
    ctx = build_ctx(df)
    n_minor = len([s for s in ctx.minor if s.confirmed_at is not None])
    n_major = len([s for s in ctx.major if s.confirmed_at is not None])
    assert n_minor > n_major >= 1


def test_fit_swing_trendline_ignores_outlier():
    # 고점 4개 중 3개가 일직선(100선), 1개가 아래로 처짐 → 선은 3개를 관통해야
    xs = [0, 10, 20, 30]
    ys = [100.0, 95.0, 100.0, 100.0]
    atr = np.full(40, 1.0)
    line, touches = fit_swing_trendline(xs, ys, atr, upper=True)
    assert touches >= 3
    assert abs(line.at(0) - 100) < 1.0 and abs(line.at(30) - 100) < 1.0
    # 회귀였다면 selope가 음수 절편 ~97로 왜곡됐을 것


def test_fit_swing_trendline_no_violation():
    # 저항선: 어떤 고점도 선 위로 크게 삐져나오면 안 된다
    xs = [0, 8, 16, 24]
    ys = [110.0, 108.0, 106.5, 104.0]
    atr = np.full(30, 0.8)
    line, _ = fit_swing_trendline(xs, ys, atr, upper=True)
    for x, y in zip(xs, ys):
        assert y <= line.at(x) + 0.8 * 0.25 + 1e-9


def test_fit_swing_trendline_degenerate_same_x():
    # 모든 점이 같은 x — 앵커 쌍이 없어도 크래시 없이 폴백해야 한다
    atr = np.full(10, 1.0)
    line, touches = fit_swing_trendline([3, 3], [100.0, 105.0], atr, upper=True)
    assert line is not None and touches == 2


def test_zigzag_invariants_and_degenerate_inputs():
    # 불변식: 교대·idx 증가·confirmed_at 단조·잠정 극점은 마지막 1개뿐
    seq = [100.0] * 3
    for a, b in ((100, 118), (118, 96), (96, 120), (120, 100), (100, 125)):
        seq += _leg(a, b, 7)
    ctx = build_ctx(_df(seq))
    for sw in (ctx.minor, ctx.major):
        for a, b in zip(sw[:-1], sw[1:]):
            assert a.is_high != b.is_high and a.idx < b.idx
        confirms = [s.confirmed_at for s in sw if s.confirmed_at is not None]
        assert confirms == sorted(confirms)
        assert all(s.confirmed_at is not None for s in sw[:-1])
    # 경계 입력: 1행·동일가(거래정지)·종가 0 오염 — 무예외 + 가짜 스윙 폭주 없음
    assert build_ctx(_df([100.0])).minor == []
    halt = build_ctx(_df([5000.0] * 200, spread=0.0))
    assert [s for s in halt.minor if s.confirmed_at is not None] == []
    dirty = build_ctx(_df([0.0] * 100, spread=0.0))
    assert [s for s in dirty.minor if s.confirmed_at is not None] == []


def test_zigzag_outside_bar_keeps_swing_low():
    # 아웃사이드 바(신저가+큰 양봉 반전)가 있어도: 저점 스윙은 그 봉에 찍히고
    # 교대·인과 불변식이 유지된다. (그 봉의 반대편 극값은 다음 레그에서 제외되는
    # 한계가 있어, 넥라인류는 스윙 가격이 아닌 실제 배열 극값으로 재야 한다 —
    # double.py/multi.py가 그렇게 한다.)
    closes = [100.0] * 3 + _leg(100, 130, 8) + _leg(130, 106, 5) + _leg(112, 128, 8)
    df = _df(closes)
    ob = 3 + 8 + 5  # 마지막 하락봉 직후 = 아웃사이드 바로 만든다
    df.loc[ob, "low"] = 98.0    # 신저가
    df.loc[ob, "high"] = 118.0  # 동시에 넓은 위꼬리
    ctx = build_ctx(df)
    lows = [s for s in ctx.minor if not s.is_high and s.confirmed_at is not None]
    assert lows and min(s.price for s in lows) == 98.0
    for a, b in zip(ctx.minor[:-1], ctx.minor[1:]):
        assert a.is_high != b.is_high and a.idx < b.idx
