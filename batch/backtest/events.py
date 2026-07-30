"""종목별 이벤트 스트림 추출 — 백테스트 엔진의 재료.

이벤트 = "그 날 발생했다"고 말할 수 있는 것 (인덱스 리스트로 표현).
지표값 조건(when)은 이벤트가 아니라 해당일의 지표 DataFrame에서 평가한다.
"""

import numpy as np
import pandas as pd

from batch import config
from batch.indicators.divergence import detect_divergences


def _cross_up(a: pd.Series, b) -> list[int]:
    """a가 b를 상향 돌파한 인덱스 목록. b는 Series 또는 상수."""
    if not isinstance(b, pd.Series):
        b = pd.Series(float(b), index=a.index)
    prev_le = a.shift(1) <= b.shift(1)
    now_gt = a > b
    return list(np.flatnonzero((prev_le & now_gt).fillna(False).to_numpy()))


def build_events(ind: pd.DataFrame) -> dict[str, list[int]]:
    """지표 DataFrame(일봉) → 이벤트명: 발생 인덱스 목록.

    다이버전스는 '확정일'(두 번째 피벗 + 우측 lookback) 기준 — 실전에서
    그 시점에야 알 수 있는 신호이므로 백테스트 진입점도 확정일로 한다.
    """
    zero = pd.Series(0.0, index=ind.index)
    events: dict[str, list[int]] = {
        "macd_golden": _cross_up(ind["macd"], ind["macd_signal"]),
        "macd_dead": _cross_up(ind["macd_signal"], ind["macd"]),
        "macd_zero_up": _cross_up(ind["macd"], zero),
        "rsi_cross_up_30": _cross_up(ind["rsi"], 30.0),   # 과매도 탈출
        "rsi_cross_down_70": _cross_up(70.0 - ind["rsi"], zero),  # 과매수 이탈
        "bb_lower_touch": list(
            np.flatnonzero(
                (ind["low"] <= ind["bb_lower"]).fillna(False).to_numpy()
            )
        ),
        "bb_upper_touch": list(
            np.flatnonzero(
                (ind["high"] >= ind["bb_upper"]).fillna(False).to_numpy()
            )
        ),
    }

    divs = detect_divergences(
        ind["high"].astype(float), ind["low"].astype(float), ind["rsi"]
    )
    n = len(ind)
    for kind in ("div_reg_bull", "div_reg_bear", "div_hid_bull", "div_hid_bear"):
        events[kind] = sorted(
            e.confirmed_at for e in divs if e.kind == kind and e.confirmed_at < n
        )
        # 연속 다이버전스(피벗 3개 이상). 2연속과 성과를 비교하려고 따로 낸다.
        events[kind + "_x3"] = sorted(
            e.confirmed_at
            for e in divs
            if e.kind == kind
            and e.confirmed_at < n
            and getattr(e, "chain", 2) >= config.DIV_CHAIN_MIN
        )

    # 단기 캔들 패턴 이벤트
    from batch.indicators.candles import detect_candles

    events.update(detect_candles(ind))

    # 차트 패턴 완성(돌파)일 이벤트
    from batch.patterns import PATTERN_KINDS, detect_all_patterns

    pats = detect_all_patterns(ind)
    for kind in PATTERN_KINDS:
        events[kind] = sorted(
            p.completed_at for p in pats
            if p.kind == kind and p.completed_at is not None and p.completed_at < n
        )
    return events
