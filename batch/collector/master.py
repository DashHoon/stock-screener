"""종목 마스터: KRX 상장 종목 목록 수집·필터.

FinanceDataReader의 KRX 목록(네이버/KRX 소스)을 사용한다.
pykrx의 get_market_ticker_list는 KRX 엔드포인트 변경으로 빈 값을 돌려줘 사용하지 않음(2026-07 기준).
"""

import logging

import pandas as pd

from batch import config
from batch.sectors import ETC, sector_of

log = logging.getLogger(__name__)

# KOSPI(STK), KOSDAQ(KSQ)만. KONEX(KNX) 제외
MARKETS = {"STK": "KOSPI", "KSQ": "KOSDAQ"}


def _cached_industry() -> pd.Series | None:
    """캐시된 마스터의 code→industry. 업종 수집 실패 시 폴백용."""
    if not config.STOCKS_CACHE.exists():
        return None
    try:
        prev = pd.read_parquet(config.STOCKS_CACHE, columns=["code", "industry"])
    except Exception:
        log.exception("캐시 업종 읽기 실패")
        return None
    prev = prev.dropna(subset=["industry"])
    return prev.set_index("code")["industry"] if len(prev) else None


def fetch_stock_master() -> pd.DataFrame:
    """전 종목 마스터를 수집해 필터링한 DataFrame을 돌려준다.

    columns: code, name, market, close, change_pct, marcap(억원), industry, sector
    제외: KONEX, 스팩, 우선주(종목코드 끝자리 != '0')
    시가총액 내림차순 정렬 (백테스트 large 유니버스가 순서에 의존).
    """
    import FinanceDataReader as fdr

    raw = fdr.StockListing("KRX")
    df = raw[raw["MarketId"].isin(MARKETS)].copy()
    # 업종(통계청 산업분류)은 KRX 목록에 없고 KRX-DESC에만 있다 → code로 조인.
    # 같은 호출에 회사 개요(주요제품·상장일·대표자·홈페이지·지역)도 들어 있다 —
    # 종목 페이지의 '어떤 회사인가'는 이 값들로 만든다. 따로 받을 필요가 없다.
    try:
        d = fdr.StockListing("KRX-DESC")[
            ["Code", "Industry", "Products", "ListingDate",
             "Representative", "HomePage", "Region"]
        ]
        df = df.merge(d, on="Code", how="left")
    except Exception:
        # 업종만 실패한 것이므로 시세 마스터까지 버리지는 않는다. 대신 마지막으로
        # 성공한 캐시의 업종을 그대로 쓴다 — None으로 두면 전 종목이 '기타'가
        # 되고, 그 결과가 다시 캐시를 덮어써 하루치 실패가 영구화된다
        # (업종맵이 '기타' 한 칸으로 퇴화하는데 배치는 성공으로 끝난다).
        prev = _cached_industry()
        log.exception(
            "업종 수집 실패 — %s",
            f"캐시 업종 {len(prev)}종목으로 폴백" if prev is not None else "캐시도 없어 미상 처리",
        )
        df["Industry"] = df["Code"].map(prev) if prev is not None else None
        for c in ("Products", "ListingDate", "Representative", "HomePage", "Region"):
            df[c] = None
    df = df[~df["Name"].str.contains("스팩", na=False)]
    df = df[df["Code"].str.endswith("0")]  # 우선주 제외 (5·7·9 등으로 끝남)

    # Marcap(원) → 억원. 결측·0은 -1로 두어 필터에서 '알 수 없음'으로 취급
    marcap_won = pd.to_numeric(df.get("Marcap"), errors="coerce").fillna(0)
    out = pd.DataFrame(
        {
            "code": df["Code"],
            "name": df["Name"],
            "market": df["MarketId"].map(MARKETS),
            "close": df["Close"].astype("int64"),
            "change_pct": df["ChagesRatio"].astype(float).round(2),
            "marcap": (marcap_won / 1e8).round().astype("int64").where(marcap_won > 0, -1),
            "industry": df["Industry"],   # 위 try/except 양쪽에서 항상 채워진다
            # 회사 개요 (종목 페이지) — 전부 KRX 상장법인 공시 정보다
            "products": df["Products"],
            "listing_date": df["ListingDate"],
            "ceo": df["Representative"],
            "homepage": df["HomePage"],
            "region": df["Region"],
            # 종목코드도 넘긴다 — 공식 업종이 실제 사업과 어긋나는 종목은
            # sectors.OVERRIDE가 코드로 잡아준다 (삼성전자→반도체 등)
            "sector": [
                sector_of(ind, code)
                for ind, code in zip(df["Industry"], df["Code"], strict=True)
            ],
        }
    )
    out = out.sort_values("marcap", ascending=False).reset_index(drop=True)
    etc_pct = (out["sector"] == ETC).mean() * 100 if len(out) else 0.0
    # 업종 미상이 절반을 넘으면 업종맵이 '기타'로 쏠린다 — 조용히 지나가지 않도록
    # 에러로 남긴다 (배치 자체는 시세·시그널이 정상이므로 계속 진행).
    (log.error if etc_pct > 50 else log.info)(
        "종목 마스터 %d개 (원본 %d개, 업종 미상 %.1f%%)", len(out), len(raw), etc_pct
    )
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
