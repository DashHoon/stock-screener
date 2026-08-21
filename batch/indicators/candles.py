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
- cdl_hanging                       : 교수형 (상승 후, 긴 아래꼬리 — 망치와 같은 모양·다른 위치)
- cdl_inv_hammer                    : 역망치형 (하락 후, 긴 위꼬리 — 유성과 같은 모양·다른 위치)
- cdl_harami_bull / cdl_harami_bear : 상승/하락 잉태형 (전봉 몸통 안에 오늘 작은 몸통)
- cdl_3soldiers / cdl_3crows        : 적삼병 / 흑삼병 (같은 색 큰 봉 3연속, 계단식)
- cdl_tweezer_bottom / _top         : 족집게 바닥 / 천장 (이틀 저가·고가가 같은 수준)
- cdl_wick_top                      : 긴 윗꼬리 반복 (고점권에서 매도 압력이 되풀이)

정의는 StockCharts ChartSchool의 캔들 항목을 기준으로 삼았다 (지표 검증 때와 같은
출처). 위꼬리·아래꼬리 배수, 직전 추세 요구, 몸통 포함 관계가 거기 정의를 따른다.
"""

import numpy as np
import pandas as pd

# 잡음 컷: 유의미한 봉으로 인정할 최소 크기 (종가 대비 %)
MIN_BODY_PCT = 1.0     # '큰 몸통' 판정
MIN_RANGE_PCT = 1.5    # 꼬리형(망치/유성)의 최소 변동폭
DOJI_RANGE_PCT = 2.5   # 도지의 최소 변동폭 (더 엄격 — 흔한 잡음 컷)
DOJI_BODY_FRAC = 0.05  # 도지 몸통 ≤ 변동폭의 5%
TREND_BARS = 5         # 직전 추세 판정 봉 수
TWEEZER_TOL = 0.1      # 족집게: 두 저가(고가) 차이 ≤ 변동폭의 10%

# 긴 윗꼬리 반복 (cdl_wick_top)
WICK_BODY_X = 1.5       # 위꼬리 ≥ 몸통의 1.5배
WICK_RANGE_FRAC = 0.40  # 위꼬리 ≥ 변동폭의 40%
WICK_VOL_X = 1.0        # 거래량 ≥ 20일 평균 (없으면 매도 압력이 아니라 그냥 한산한 것)
WICK_NEAR_HIGH = 0.90   # 최근 60봉 고가의 90% 이상 구간에서만
WICK_WIN = 10           # 창
WICK_NEED = 3           # 창 안에 이만큼 나오면 '반복'으로 본다


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

    # 교수형: 망치와 같은 모양인데 상승 후에 나온다 (위치가 의미를 바꾼다)
    res["cdl_hanging"] = (
        uptrend & (rng_pct >= MIN_RANGE_PCT)
        & (lower >= 2 * body) & (upper <= body) & (body > 0)
    )
    # 역망치형: 유성과 같은 모양인데 하락 후에 나온다
    res["cdl_inv_hammer"] = (
        downtrend & (rng_pct >= MIN_RANGE_PCT)
        & (upper >= 2 * body) & (lower <= body) & (body > 0)
    )

    # 잉태형(harami): 전봉이 큰 몸통, 오늘 몸통이 그 안에 완전히 들어가고 색이 반대.
    # 장악형의 반대 구조다 — 장악은 오늘이 어제를 삼키고, 잉태는 어제가 오늘을 품는다.
    hi1, lo1 = np.maximum(o1, c1), np.minimum(o1, c1)
    inside = (np.maximum(o, c) <= hi1) & (np.minimum(o, c) >= lo1)
    harami_core = (sh(body_pct) >= MIN_BODY_PCT) & inside & (body < 0.5 * body1)
    res["cdl_harami_bull"] = harami_core & bear1 & bull & downtrend
    res["cdl_harami_bear"] = harami_core & bull1 & bear & uptrend

    # 적삼병/흑삼병: 같은 색 큰 봉 3연속 + 계단식 전진.
    # 시가가 전봉 몸통 안에서 열리고 종가가 전봉 종가를 넘어야 한다 (candlescanner 정의).
    o2b, c2b = sh(o, 2), sh(c, 2)
    big0 = body_pct >= MIN_BODY_PCT
    big1 = sh(body_pct) >= MIN_BODY_PCT
    big2b = sh(body_pct, 2) >= MIN_BODY_PCT
    bull2b = sh(bull.astype(float), 2) == 1
    bear2b = sh(bear.astype(float), 2) == 1
    res["cdl_3soldiers"] = (
        bull & bull1 & bull2b & big0 & big1 & big2b
        & (c > c1) & (c1 > c2b)
        & (o <= c1) & (o >= o1) & (o1 <= c2b) & (o1 >= o2b)
    )
    res["cdl_3crows"] = (
        bear & bear1 & bear2b & big0 & big1 & big2b
        & (c < c1) & (c1 < c2b)
        & (o >= c1) & (o <= o1) & (o1 >= c2b) & (o1 <= o2b)
    )

    # 족집게: 이틀 저가(고가)가 사실상 같은 수준. 지지·저항이 확인된 자리다.
    h1, l1 = sh(h), sh(l)
    same_low = np.abs(l - l1) <= TWEEZER_TOL * np.maximum(rng, 1e-9)
    same_high = np.abs(h - h1) <= TWEEZER_TOL * np.maximum(rng, 1e-9)
    res["cdl_tweezer_bottom"] = (
        downtrend & same_low & (rng_pct >= MIN_RANGE_PCT) & bear1 & bull
    )
    res["cdl_tweezer_top"] = (
        uptrend & same_high & (rng_pct >= MIN_RANGE_PCT) & bull1 & bear
    )

    # 긴 윗꼬리 반복 — 오를 때마다 위에서 눌리는 일이 되풀이되는 상태.
    #
    # 봉 하나로는 유성형이 이미 잡는다. 여기서 보는 건 '반복'이다. 다이버전스처럼
    # 되풀이 자체가 신호인 종류라 창(WICK_WIN) 안의 횟수로 판정한다.
    #
    # 거래량 조건을 넣는다 — 거래량 없이 생긴 윗꼬리는 매도 압력이 아니라 그냥
    # 거래가 없어 생긴 매물대다 (2026-08-18 조사).
    vol = ind["volume"].astype(float).to_numpy()
    vol_ma = pd.Series(vol).rolling(20, min_periods=10).mean().to_numpy()
    wick_bar = (
        (rng > 0)
        & (upper >= WICK_BODY_X * np.maximum(body, 1e-9))
        & (upper >= WICK_RANGE_FRAC * rng)
        & (rng_pct >= MIN_RANGE_PCT)
        & (vol >= WICK_VOL_X * np.nan_to_num(vol_ma, nan=np.inf))
    )
    # 고점권에서만 의미가 있다 — 바닥에서 나오는 윗꼬리는 반등 시도다
    roll_high = pd.Series(h).rolling(60, min_periods=20).max().to_numpy()
    near_high = c >= WICK_NEAR_HIGH * np.nan_to_num(roll_high, nan=np.inf)
    cnt = pd.Series(wick_bar.astype(int)).rolling(WICK_WIN).sum().to_numpy()
    res["cdl_wick_top"] = (
        wick_bar & near_high & (np.nan_to_num(cnt) >= WICK_NEED)
    )

    return {
        k: [int(i) for i in np.flatnonzero(np.nan_to_num(v.astype(float)) == 1)]
        for k, v in res.items()
    }
