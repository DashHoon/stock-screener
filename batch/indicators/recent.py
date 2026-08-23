"""시그널별 '마지막 발생이 몇 봉 전인지' 계산 (스크리너 기간 필터용).

- 이벤트형(다이버전스 4종 + 연속 4종, MACD 크로스/0선): 마지막 발생일 기준
- 상태형(RSI 과열/과매도, BB 터치, 스퀴즈): 마지막으로 조건을 만족한 날 기준
- RECENT_MAX_BARS(63봉 ≈ 3개월)보다 오래된 것은 결과에서 생략
"""

import numpy as np
import pandas as pd

from batch import config
from batch.backtest.events import _cross_up
from batch.indicators.candles import detect_candles
from batch.indicators.divergence import Divergence


def _last_true(mask: pd.Series, n: int) -> int | None:
    """True인 마지막 위치가 몇 봉 전인지 (없으면 None)."""
    idx = np.flatnonzero(mask.fillna(False).to_numpy())
    if len(idx) == 0:
        return None
    return n - 1 - int(idx[-1])


def _last_index(indices: list[int], n: int) -> int | None:
    valid = [int(i) for i in indices if i < n]  # numpy int → JSON 직렬화 가능하게
    if not valid:
        return None
    return n - 1 - max(valid)


def compute_recent(
    ind: pd.DataFrame,
    div_events: list[Divergence],
    max_bars: int = config.RECENT_MAX_BARS,
) -> dict[str, int]:
    """시그널 12종의 마지막 발생 경과 봉 수. {signal: bars_ago(0=오늘)}"""
    n = len(ind)
    zero = pd.Series(0.0, index=ind.index)

    squeeze = ind["bb_width"] <= ind["bb_width"].rolling(
        config.BB_SQUEEZE_WINDOW
    ).min() * 1.001

    candidates: dict[str, int | None] = {
        "rsi_overbought": _last_true(ind["rsi"] >= config.RSI_OVERBOUGHT, n),
        "rsi_oversold": _last_true(ind["rsi"] <= config.RSI_OVERSOLD, n),
        "macd_golden": _last_index(_cross_up(ind["macd"], ind["macd_signal"]), n),
        "macd_dead": _last_index(_cross_up(ind["macd_signal"], ind["macd"]), n),
        "macd_zero_up": _last_index(_cross_up(ind["macd"], zero), n),
        "bb_upper_touch": _last_true(ind["high"] >= ind["bb_upper"], n),
        "bb_lower_touch": _last_true(ind["low"] <= ind["bb_lower"], n),
        "bb_squeeze": _last_true(squeeze, n),
    }
    # 이격도 과열/침체 — RSI 과매수/과매도와 같은 상태형 시그널.
    for ma, (high, low) in config.DISPARITY_BANDS.items():
        col = ind.get(f"disp{ma}")
        if col is None:
            continue
        candidates[f"disp{ma}_high"] = _last_true(col >= high, n)
        candidates[f"disp{ma}_low"] = _last_true(col <= low, n)
    for kind in ("div_reg_bull", "div_reg_bear", "div_hid_bull", "div_hid_bear"):
        candidates[kind] = _last_index(
            [e.confirmed_at for e in div_events if e.kind == kind], n
        )
        # 연속 다이버전스: 같은 종류가 피벗을 공유하며 DIV_CHAIN_MIN개 이상 이어진 것만
        candidates[kind + "_x3"] = _last_index(
            [
                e.confirmed_at
                for e in div_events
                if e.kind == kind and getattr(e, "chain", 2) >= config.DIV_CHAIN_MIN
            ],
            n,
        )

    # 단기 캔들 패턴 (장악형 등)
    for kind, idxs in detect_candles(ind).items():
        candidates[kind] = _last_index(idxs, n)

    return {
        k: v for k, v in candidates.items() if v is not None and v <= max_bars
    }
