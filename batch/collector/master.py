"""종목 마스터: KRX 상장 종목 목록 수집·필터.

FinanceDataReader의 KRX 목록(네이버/KRX 소스)을 사용한다.
pykrx의 get_market_ticker_list는 KRX 엔드포인트 변경으로 빈 값을 돌려줘 사용하지 않음(2026-07 기준).
"""

import logging

import pandas as pd

from batch import config

log = logging.getLogger(__name__)

# KOSPI(STK), KOSDAQ(KSQ)만. KONEX(KNX) 제외
MARKETS = {"STK": "KOSPI", "KSQ": "KOSDAQ"}


def fetch_stock_master() -> pd.DataFrame:
    """전 종목 마스터를 수집해 필터링한 DataFrame을 돌려준다.

    columns: code, name, market, close, change_pct
    제외: KONEX, 스팩, 우선주(종목코드 끝자리 != '0')
    """
    import FinanceDataReader as fdr

    raw = fdr.StockListing("KRX")
    df = raw[raw["MarketId"].isin(MARKETS)].copy()
    df = df[~df["Name"].str.contains("스팩", na=False)]
    df = df[df["Code"].str.endswith("0")]  # 우선주 제외 (5·7·9 등으로 끝남)

    out = pd.DataFrame(
        {
            "code": df["Code"],
            "name": df["Name"],
            "market": df["MarketId"].map(MARKETS),
            "close": df["Close"].astype("int64"),
            "change_pct": df["ChagesRatio"].astype(float).round(2),
        }
    ).reset_index(drop=True)
    log.info("종목 마스터 %d개 (원본 %d개)", len(out), len(raw))
    return out


def load_or_fetch_master(refresh: bool = True) -> pd.DataFrame:
    """마스터를 수집해 캐시에 저장. 수집 실패 시 캐시로 폴백."""
    if not refresh and config.STOCKS_CACHE.exists():
        return pd.read_parquet(config.STOCKS_CACHE)
    try:
        df = fetch_stock_master()
        config.STOCKS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(config.STOCKS_CACHE, index=False)
        return df
    except Exception:
        if config.STOCKS_CACHE.exists():
            log.exception("마스터 수집 실패 — 캐시 사용")
            return pd.read_parquet(config.STOCKS_CACHE)
        raise
