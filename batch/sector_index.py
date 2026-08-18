"""업종 지수 — 섹터별 시가총액 가중 지수를 만든다.

업종맵은 '오늘 얼마나 올랐나'만 보여준다. 그 업종이 몇 달째 오르는 중인지,
지금이 고점인지 바닥인지는 안 보인다. 지수 시계열을 만들면 종목과 똑같이
차트·지표·패턴을 태울 수 있다.

만드는 법
---------
현재 시가총액 ÷ 현재가로 주식수를 역산해 고정하고, 과거 종가에 곱해 더한다.
기준일(첫 봉)을 1000으로 정규화한다.

    지수(t) = Σ(주식수_i × 종가_i,t) / Σ(주식수_i × 종가_i,0) × 1000

시가·고가·저가도 같은 방식으로 가중합해 캔들을 만든다.

한계 — 화면에 밝혀야 한다
------------------------
1. 지수의 고가는 개별 종목 고가의 합이 아니다. 종목마다 고점 시각이 달라
   실제 지수 고가보다 높게 나온다. 근사값이다.
2. 주식수를 현재 값으로 고정하므로 과거 증자·분할·자사주 소각이 반영되지
   않는다. 최근 1~2년은 정확하고 10년 전으로 갈수록 오차가 커진다.
3. 상장 전 구간이 없는 종목은 그 구간에서 빠진다 — 편입 시점에 지수가 튀지
   않도록, 각 날짜에 '그날 데이터가 있는 종목'만으로 전일 대비 수익률을
   계산해 누적한다(체인 방식). 종목 수가 변해도 계단이 생기지 않는다.
"""

import logging

import numpy as np
import pandas as pd

from batch import config

log = logging.getLogger(__name__)

BASE = 1000.0
# 지수를 만들 최소 종목 수. 한두 종목짜리 섹터는 그 종목 차트와 다를 게 없다.
MIN_MEMBERS = 3
# 지수 계산에 넣을 최소 봉 수 (지표 워밍업)
MIN_BARS = config.MIN_ROWS_FOR_INDICATORS


def build_index(members: list[tuple[str, float, pd.DataFrame]]) -> pd.DataFrame | None:
    """(코드, 주식수, ohlcv) 목록 → 지수 OHLCV.

    members의 ohlcv는 date 오름차순이어야 한다.
    """
    if len(members) < MIN_MEMBERS:
        return None

    # 날짜 축을 합집합으로 잡고 종목별 시가총액 시계열을 만든다
    cols = {}
    for code, shares, df in members:
        if df is None or len(df) < 2:
            continue
        s = df.set_index("date")
        for c in ("open", "high", "low", "close"):
            cols[(code, c)] = s[c].astype(float) * shares
    if not cols:
        return None
    wide = pd.DataFrame(cols)
    wide.index.name = "date"
    wide = wide.sort_index()

    close = wide.xs("close", axis=1, level=1)
    # 그날 값이 있는 종목만으로 전일 대비 수익률 — 종목이 늘고 줄어도 계단이 안 생긴다
    prev = close.shift(1)
    both = close.notna() & prev.notna()
    num = close.where(both).sum(axis=1)
    den = prev.where(both).sum(axis=1)
    ret = (num / den).replace([np.inf, -np.inf], np.nan)
    ret.iloc[0] = 1.0
    ret = ret.fillna(1.0)
    idx_close = BASE * ret.cumprod()

    # 시·고·저는 같은 날 종가 대비 비율을 가중평균해 종가 지수에 곱한다.
    # (그날 시가총액 합의 비율이므로 종목 편입·이탈에 영향받지 않는다)
    out = pd.DataFrame({"date": idx_close.index, "close": idx_close.to_numpy()})
    for c in ("open", "high", "low"):
        part = wide.xs(c, axis=1, level=1)
        ok = part.notna() & close.notna()
        ratio = part.where(ok).sum(axis=1) / close.where(ok).sum(axis=1)
        out[c] = (idx_close * ratio.fillna(1.0)).to_numpy()

    out["volume"] = 0  # 지수에 거래량 개념이 없다 — 차트에서 거래량 패널은 비운다
    out = out[["date", "open", "high", "low", "close", "volume"]]
    out = out[out["close"] > 0].reset_index(drop=True)
    return out if len(out) >= MIN_BARS else None
