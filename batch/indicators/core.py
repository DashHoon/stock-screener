"""RSI / MACD / 볼린저밴드 계산 (pandas 벡터화)."""

import numpy as np
import pandas as pd

from batch import config


def _wilder_smooth(s: pd.Series, period: int) -> pd.Series:
    """Wilder 평활: 첫 period개 평균을 시드로 alpha=1/period 재귀 평균."""
    vals = s.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    if len(vals) <= period:
        return pd.Series(out, index=s.index)
    seed = vals[1 : period + 1].mean()  # vals[0]은 diff로 생긴 NaN
    smoothed = (
        pd.Series(np.concatenate([[seed], vals[period + 1 :]]))
        .ewm(alpha=1 / period, adjust=False)
        .mean()
        .to_numpy()
    )
    out[period:] = smoothed
    return pd.Series(out, index=s.index)


def rsi(close: pd.Series, period: int = config.RSI_PERIOD) -> pd.Series:
    """Wilder RSI. SMA 시드 + 지수평활(alpha=1/period), HTS/TradingView와 동일."""
    delta = close.diff()
    avg_gain = _wilder_smooth(delta.clip(lower=0.0), period)
    avg_loss = _wilder_smooth((-delta).clip(lower=0.0), period)
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    # 하락이 전혀 없는 구간(avg_loss=0)은 RSI 100
    out = out.where(avg_loss != 0, 100.0)
    out[avg_gain.isna() | avg_loss.isna()] = float("nan")
    return out


def macd(
    close: pd.Series,
    fast: int = config.MACD_FAST,
    slow: int = config.MACD_SLOW,
    signal: int = config.MACD_SIGNAL,
) -> pd.DataFrame:
    """columns: macd, macd_signal, macd_hist"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame(
        {"macd": line, "macd_signal": sig, "macd_hist": line - sig}
    )


def bollinger(
    close: pd.Series,
    period: int = config.BB_PERIOD,
    n_std: float = config.BB_STD,
) -> pd.DataFrame:
    """columns: bb_upper, bb_mid, bb_lower, pct_b, bb_width"""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)  # HTS 관행: 모표준편차
    upper = mid + n_std * std
    lower = mid - n_std * std
    width = (upper - lower) / mid
    pct_b = (close - lower) / (upper - lower)
    return pd.DataFrame(
        {"bb_upper": upper, "bb_mid": mid, "bb_lower": lower,
         "pct_b": pct_b, "bb_width": width}
    )


def compute_indicators(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """OHLCV DataFrame(date, open..volume)에 지표 컬럼을 붙여 돌려준다."""
    df = ohlcv.reset_index(drop=True).copy()
    close = df["close"].astype(float)
    df["rsi"] = rsi(close)
    df = pd.concat([df, macd(close), bollinger(close)], axis=1)
    # 백테스트 품질 필터용 파생 컬럼
    vol = df["volume"].astype(float)
    vol_ma20 = vol.rolling(20).mean()
    df["vol_ratio20"] = (vol / vol_ma20).where(vol_ma20 > 0)  # 20일 평균 대비 거래량 배수
    ma120 = close.rolling(120).mean()
    df["ma120_gap"] = (close / ma120 - 1) * 100  # 120일선 대비 이격 % (양수=추세 위)
    return df
