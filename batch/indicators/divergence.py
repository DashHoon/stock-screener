"""RSI 다이버전스 판정.

RSI에서 피벗 고점/저점을 찾고(좌우 lookback), 연속한 피벗 쌍에서
가격 방향과 RSI 방향을 비교한다.

- regular bullish : 가격 저점 하락(LL) + RSI 저점 상승(HL)
- hidden  bullish : 가격 저점 상승(HL) + RSI 저점 하락(LL)
- regular bearish : 가격 고점 상승(HH) + RSI 고점 하락(LH)
- hidden  bearish : 가격 고점 하락(LH) + RSI 고점 상승(HH)

RSI 존 필터: bull형은 RSI 피벗이 과매도권(DIV_RSI_BULL_ZONE 미만)에 걸쳐야,
bear형은 과매수권(DIV_RSI_BEAR_ZONE 초과)에 걸쳐야 유효한 신호로 본다.
중간 지대(40~60)에서 생기는 약한 다이버전스는 잡음이 많아 제외.

피벗은 우측 lookback 만큼 지나야 확정되므로, 이벤트 확정 시점은
두 번째 피벗 + PIVOT_RIGHT 봉이다.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from batch import config


@dataclass
class Divergence:
    kind: str          # div_reg_bull | div_hid_bull | div_reg_bear | div_hid_bear
    idx_from: int      # 첫 피벗 위치 (행 인덱스)
    idx_to: int        # 두 번째 피벗 위치
    confirmed_at: int  # 확정 봉 위치 (idx_to + PIVOT_RIGHT)
    price_from: float
    price_to: float
    rsi_from: float
    rsi_to: float
    # 연속 다이버전스 사슬 길이(피벗 개수). 2 = 보통의 한 쌍,
    # 3 이상 = 같은 종류가 피벗을 공유하며 연달아 이어진 상태.
    # 고점이 계속 높아지는데 RSI 고점은 계속 낮아지는 식으로 여러 번 반복되면
    # 한 번 어긋난 것보다 추세 소진 신호로 훨씬 강하게 본다.
    chain: int = 2


def find_pivots(
    values: pd.Series,
    left: int = config.PIVOT_LEFT,
    right: int = config.PIVOT_RIGHT,
) -> tuple[np.ndarray, np.ndarray]:
    """(고점 인덱스, 저점 인덱스). i가 좌 left·우 right 봉보다 극값이면 피벗."""
    v = values.to_numpy(dtype=float)
    n = len(v)
    highs, lows = [], []
    for i in range(left, n - right):
        if np.isnan(v[i]):
            continue
        window = v[i - left : i + right + 1]
        if np.isnan(window).any():
            continue
        center = v[i]
        others = np.delete(window, left)
        if center > others.max():
            highs.append(i)
        elif center < others.min():
            lows.append(i)
    return np.array(highs, dtype=int), np.array(lows, dtype=int)


def detect_divergences(
    price_high: pd.Series,
    price_low: pd.Series,
    rsi: pd.Series,
    left: int = config.PIVOT_LEFT,
    right: int = config.PIVOT_RIGHT,
    min_bars: int = config.DIV_MIN_BARS,
    max_bars: int = config.DIV_MAX_BARS,
    bull_zone: float = config.DIV_RSI_BULL_ZONE,
    bear_zone: float = config.DIV_RSI_BEAR_ZONE,
) -> list[Divergence]:
    """전체 구간의 다이버전스 이벤트 목록 (시간순)."""
    rsi_highs, rsi_lows = find_pivots(rsi, left, right)
    events: list[Divergence] = []

    ph = price_high.to_numpy(dtype=float)
    pl = price_low.to_numpy(dtype=float)
    rv = rsi.to_numpy(dtype=float)

    for pivots, price, is_low in ((rsi_lows, pl, True), (rsi_highs, ph, False)):
        prev_kind: str | None = None   # 직전 쌍의 종류
        prev_b: int | None = None      # 직전 쌍의 두 번째 피벗
        run = 2                        # 현재 사슬의 피벗 개수
        for a, b in zip(pivots[:-1], pivots[1:]):
            if not (min_bars <= b - a <= max_bars):
                prev_kind, prev_b = None, None  # 건너뛴 구간이 있으면 사슬이 끊긴다
                continue
            dp = price[b] - price[a]
            dr = rv[b] - rv[a]
            if dp == 0 or dr == 0:
                prev_kind, prev_b = None, None
                continue
            if is_low:
                if min(rv[a], rv[b]) >= bull_zone:  # 존 필터: 과매도권 밖은 잡음
                    continue
                if dp < 0 and dr > 0:
                    kind = "div_reg_bull"
                elif dp > 0 and dr < 0:
                    kind = "div_hid_bull"
                else:
                    continue
            else:
                if max(rv[a], rv[b]) <= bear_zone:  # 존 필터: 과매수권 밖은 잡음
                    continue
                if dp > 0 and dr < 0:
                    kind = "div_reg_bear"
                elif dp < 0 and dr > 0:
                    kind = "div_hid_bear"
                else:
                    continue
            # 직전 쌍과 피벗을 공유하고 종류가 같으면 사슬이 이어진 것으로 본다.
            # (a,b)·(b,c)가 모두 하락 다이버전스면 피벗 3개짜리 사슬이 된다.
            if prev_kind == kind and prev_b == a:
                run += 1
            else:
                run = 2
            prev_kind, prev_b = kind, int(b)
            events.append(
                Divergence(
                    kind=kind,
                    chain=run,
                    idx_from=int(a),
                    idx_to=int(b),
                    confirmed_at=int(b) + right,
                    price_from=float(price[a]),
                    price_to=float(price[b]),
                    rsi_from=float(rv[a]),
                    rsi_to=float(rv[b]),
                )
            )
    events.sort(key=lambda e: e.confirmed_at)
    return events


def latest_flags(
    events: list[Divergence],
    last_idx: int,
    recent_bars: int = config.DIV_RECENT_BARS,
) -> dict[str, bool]:
    """마지막 봉 기준 다이버전스 플래그. 종류별 기본 4종 + 연속(_x3) 4종.

    최근 recent_bars 봉 안에서 확정된 이벤트만 인정한다.
    """
    base = ("div_reg_bull", "div_reg_bear", "div_hid_bull", "div_hid_bear")
    flags = {k: False for k in base}
    flags.update({k + "_x3": False for k in base})
    for e in events:
        if last_idx - recent_bars < e.confirmed_at <= last_idx:
            flags[e.kind] = True
            if e.chain >= config.DIV_CHAIN_MIN:
                flags[e.kind + "_x3"] = True
    return flags
