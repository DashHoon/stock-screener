"""지표 DataFrame → 당일 시그널 플래그 12종."""

import pandas as pd

from batch import config
from batch.indicators.divergence import Divergence, detect_divergences, latest_flags


def _crossed_up(a: pd.Series, b: pd.Series) -> bool:
    """마지막 봉에서 a가 b를 상향 돌파했는가."""
    if len(a) < 2 or a.iloc[-2:].isna().any() or b.iloc[-2:].isna().any():
        return False
    return bool(a.iloc[-2] <= b.iloc[-2] and a.iloc[-1] > b.iloc[-1])


def compute_flags(ind: pd.DataFrame) -> tuple[dict[str, bool], list[Divergence]]:
    """지표가 붙은 DataFrame(마지막 행 = 최신일)에서 플래그와 다이버전스 이벤트를 계산."""
    last = ind.iloc[-1]
    zero = pd.Series(0.0, index=ind.index)

    events = detect_divergences(
        ind["high"].astype(float), ind["low"].astype(float), ind["rsi"]
    )
    div = latest_flags(events, last_idx=len(ind) - 1)

    squeeze = False
    width = ind["bb_width"].dropna()
    if len(width) >= config.BB_SQUEEZE_WINDOW:
        window = width.iloc[-config.BB_SQUEEZE_WINDOW:]
        squeeze = bool(window.iloc[-1] <= window.min() * 1.001)  # 부동소수 여유

    flags = {
        "rsi_overbought": bool(last["rsi"] >= config.RSI_OVERBOUGHT),
        "rsi_oversold": bool(last["rsi"] <= config.RSI_OVERSOLD),
        **div,
        "macd_golden": _crossed_up(ind["macd"], ind["macd_signal"]),
        "macd_dead": _crossed_up(ind["macd_signal"], ind["macd"]),
        "macd_zero_up": _crossed_up(ind["macd"], zero),
        "bb_upper_touch": bool(last["high"] >= last["bb_upper"])
        if pd.notna(last["bb_upper"]) else False,
        "bb_lower_touch": bool(last["low"] <= last["bb_lower"])
        if pd.notna(last["bb_lower"]) else False,
        "bb_squeeze": squeeze,
    }
    return flags, events
