"""단기 캔들 패턴 탐지 (일봉, 벡터화).

반전형 캔들은 '직전 추세' 문맥이 있어야 의미가 있으므로,
상승 반전형은 직전 5봉 하락, 하락 반전형은 직전 5봉 상승을 요구한다.

종류 (키 = 스크리너 시그널 키):
- cdl_engulf_bull / cdl_engulf_bear : 상승/하락 장악형 (몸통이 전봉 몸통을 감쌈)
- cdl_hammer                        : 망치형 (하락 후, 긴 아래꼬리)
- cdl_shooting                      : 유성형 (상승 후, 긴 위꼬리)
- cdl_doji                          : 도지 (몸통이 극소, 변동폭은 유의미)
- cdl_pierce / cdl_darkcloud        : 관통형 / 흑운형 (전봉 몸통 절반 회복/침범)
- cdl_morning / cdl_evening         : 샛별형 / 저녁별형 (3봉 반전)
"""

import numpy as np
import pandas as pd

# 잡음 컷: 유의미한 봉으로 인정할 최소 크기 (종가 대비 %)
MIN_BODY_PCT = 1.0     # '큰 몸통' 판정
MIN_RANGE_PCT = 1.5    # 꼬리형(망치/유성)의 최소 변동폭
DOJI_RANGE_PCT = 2.5   # 도지의 최소 변동폭 (더 엄격 — 흔한 잡음 컷)
DOJI_BODY_FRAC = 0.05  # 도지 몸통 ≤ 변동폭의 5%
TREND_BARS = 5         # 직전 추세 판정 봉 수


def detect_candles(ind: pd.DataFrame) -> dict[str, list[int]]:
    o = ind["open"].astype(float).to_numpy()
    h = ind["high"].astype(float).to_numpy()
    l = ind["low"].astype(float).to_numpy()
    c = ind["close"].astype(float).to_numpy()
    n = len(c)
    if n < TREND_BARS + 3:
        return {}

    body = np.abs(c - o)
    rng = h - l
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    bull = c > o
    bear = c < o
    body_pct = np.divide(body, c, out=np.zeros_like(body), where=c > 0) * 100
    rng_pct = np.divide(rng, c, out=np.zeros_like(rng), where=c > 0) * 100

    # 직전 추세: i-1 종가 vs i-1-TREND_BARS 종가
    prev_ret = np.full(n, 0.0)
    prev_ret[TREND_BARS + 1:] = c[TREND_BARS:-1] / np.maximum(c[:-TREND_BARS - 1], 1e-9) - 1
    downtrend = prev_ret < 0
    uptrend = prev_ret > 0

    def sh(a, k=1):  # k봉 앞(과거) 값
        out = np.full(n, np.nan)
        out[k:] = a[:-k]
        return out

    o1, c1 = sh(o), sh(c)
    body1, bull1, bear1 = sh(body), sh(bull.astype(float)) == 1, sh(bear.astype(float)) == 1

    res: dict[str, np.ndarray] = {}

    # 장악형: 오늘 몸통이 전봉 몸통을 완전히 감싸고 색이 반대, 오늘 몸통이 유의미
    engulf_core = (body_pct >= MIN_BODY_PCT) & (body > body1)
    res["cdl_engulf_bull"] = (
        engulf_core & bull & bear1
        & (o <= c1) & (c >= o1) & downtrend
    )
    res["cdl_engulf_bear"] = (
        engulf_core & bear & bull1
        & (o >= c1) & (c <= o1) & uptrend
    )

    # 망치형: 아래꼬리 ≥ 몸통 2배, 위꼬리는 몸통 이하, 하락 후
    res["cdl_hammer"] = (
        downtrend & (rng_pct >= MIN_RANGE_PCT)
        & (lower >= 2 * body) & (upper <= body) & (body > 0)
    )
    # 유성형: 위꼬리 ≥ 몸통 2배, 아래꼬리는 몸통 이하, 상승 후
    res["cdl_shooting"] = (
        uptrend & (rng_pct >= MIN_RANGE_PCT)
        & (upper >= 2 * body) & (lower <= body) & (body > 0)
    )

    # 도지: 몸통이 변동폭의 5% 이하, 변동폭 2.5% 이상 (의미 있는 공방일만)
    res["cdl_doji"] = (rng_pct >= DOJI_RANGE_PCT) & (body <= DOJI_BODY_FRAC * rng)

    # 관통형: 전봉 큰 음봉 + 오늘 양봉이 전봉 시가 아래에서 출발해 몸통 중간 위로 마감
    mid1 = (o1 + c1) / 2
    big_bear1 = bear1 & (sh(body_pct) >= MIN_BODY_PCT)
    big_bull1 = bull1 & (sh(body_pct) >= MIN_BODY_PCT)
    res["cdl_pierce"] = (
        downtrend & big_bear1 & bull
        & (o < c1) & (c > mid1) & (c < o1)
    )
    # 흑운형: 대칭
    res["cdl_darkcloud"] = (
        uptrend & big_bull1 & bear
        & (o > c1) & (c < mid1) & (c > o1)
    )

    # 샛별형/저녁별형 (3봉): 큰 봉 → 작은 몸통 → 반대색 큰 봉이 첫 봉 몸통 중간 돌파
    o2, c2 = sh(o, 2), sh(c, 2)
    body2 = sh(body, 2)
    bear2 = sh(bear.astype(float), 2) == 1
    bull2 = sh(bull.astype(float), 2) == 1
    big2 = sh(body_pct, 2) >= MIN_BODY_PCT
    small1 = body1 <= 0.5 * body2
    mid2 = (o2 + c2) / 2
    dt2 = np.full(n, False)
    dt2[2:] = downtrend[:-2]
    ut2 = np.full(n, False)
    ut2[2:] = uptrend[:-2]
    res["cdl_morning"] = (
        dt2 & bear2 & big2 & small1 & bull
        & (body_pct >= MIN_BODY_PCT) & (c > mid2)
    )
    res["cdl_evening"] = (
        ut2 & bull2 & big2 & small1 & bear
        & (body_pct >= MIN_BODY_PCT) & (c < mid2)
    )

    return {
        k: [int(i) for i in np.flatnonzero(np.nan_to_num(v.astype(float)) == 1)]
        for k, v in res.items()
    }
