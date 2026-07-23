"""코스피/코스닥 지수 수집 (FinanceDataReader)."""

import logging

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
                "name": name,
                "close": round(last, 2),
                "change_pct": round((last / prev - 1) * 100, 2) if prev else None,
                "spark": [round(float(x), 2) for x in close.iloc[-SPARK_DAYS:]],
            })
        except Exception as e:
            log.warning("지수 %s 수집 실패: %s", sym, e)
    return out
