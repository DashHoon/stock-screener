"""코스피/코스닥 지수 수집 (FinanceDataReader)."""

import datetime as dt
import logging

import pandas as pd

from batch import config

log = logging.getLogger(__name__)

INDICES = [("KS11", "코스피"), ("KQ11", "코스닥")]
SPARK_DAYS = 20


def fetch_indices() -> list[dict]:
    """지수별 최근값·등락률·미니차트용 종가. 실패 시 빈 리스트."""
    import FinanceDataReader as fdr

    out = []
    for sym, name in INDICES:
        try:
            df = fdr.DataReader(sym, "2026-01-01")
            if df is None or len(df) < 2:
                continue
            close = df["Close"].astype(float)
            last, prev = float(close.iloc[-1]), float(close.iloc[-2])
            out.append({
                "code": sym,
                "name": name,
                "close": round(last, 2),
                "change_pct": round((last / prev - 1) * 100, 2) if prev else None,
                "spark": [round(float(x), 2) for x in close.iloc[-SPARK_DAYS:]],
            })
        except Exception as e:
            log.warning("지수 %s 수집 실패: %s", sym, e)
    return out


def fetch_index_ohlcv(sym: str) -> pd.DataFrame | None:
    """지수 일봉 OHLCV(최근 BACKFILL_YEARS년). 종목 차트 파이프라인과 동일 스키마.

    지수는 소수점 값이라 종목과 달리 float로 유지한다. 오늘 미완성 봉 제거.
    """
    import FinanceDataReader as fdr

    start = (dt.date.today() - dt.timedelta(days=365 * config.BACKFILL_YEARS)).isoformat()
    raw = fdr.DataReader(sym, start)
    if raw is None or raw.empty:
        return None
    out = raw.reset_index().rename(
        columns={"Date": "date", "Open": "open", "High": "high",
                 "Low": "low", "Close": "close", "Volume": "volume"}
    )[["date", "open", "high", "low", "close", "volume"]]
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    for c in ["open", "high", "low", "close"]:
        out[c] = out[c].astype(float)
    out["volume"] = out["volume"].fillna(0).astype("int64")
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    today = dt.date.today().isoformat()
    return out[out["date"] < today].reset_index(drop=True)
