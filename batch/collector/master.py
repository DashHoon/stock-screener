"""종목 마스터: KRX 상장 종목 목록 수집·필터.

시세·시총 목록은 FinanceDataReader의 KRX 목록, 업종·회사 개요는 KRX KIND
상장법인목록을 직접 받는다.
pykrx의 get_market_ticker_list는 KRX 엔드포인트 변경으로 빈 값을 돌려줘 사용하지 않음(2026-07 기준).
"""

import logging
from html.parser import HTMLParser

import pandas as pd
import requests

from batch import config
from batch.sectors import ETC, sector_of

log = logging.getLogger(__name__)

# KOSPI(STK), KOSDAQ(KSQ)만. KONEX(KNX) 제외
MARKETS = {"STK": "KOSPI", "KSQ": "KOSDAQ"}

# KRX KIND 상장법인목록 (엑셀 내려받기 = EUC-KR HTML 표 한 장, 전 법인 1회 호출).
# 예전엔 fdr.StockListing("KRX-DESC")를 썼는데, 그건 KRX가 아니라 FDR 저자의 GitHub
# 캐시 저장소에서 '오늘 날짜' CSV를 읽는다. 그 저장소의 desc 폴더가 2026-09-17에
# 멈춰 매일 404가 났고, 4주간 회사 개요가 비고 업종은 캐시 폴백으로 버텼다.
# 캐시가 원래 가공하던 원본이 이 표라 컬럼이 같다.
KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do"
KIND_COLS = {
    "종목코드": "Code", "업종": "Industry", "주요제품": "Products", "상장일": "ListingDate",
    "대표자명": "Representative", "홈페이지": "HomePage", "지역": "Region",
}
KIND_MIN_ROWS = 1000   # 상장법인 2,700여 개. 이보다 짧으면 응답이 잘린 것
DESC_COLS = ["Industry", "Products", "ListingDate", "Representative", "HomePage", "Region"]
# 캐시(stocks.parquet) 컬럼 ↔ 원본 컬럼. 수집 실패 시 마지막 성공값으로 채운다
CACHE_COLS = {"industry": "Industry", "products": "Products", "listing_date": "ListingDate",
              "ceo": "Representative", "homepage": "HomePage", "region": "Region"}


class _TableParser(HTMLParser):
    """표의 행을 셀 문자열 목록으로. KIND 표는 중첩이 없어 이 정도로 충분하다."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def fetch_kind_desc(timeout: int = 30) -> pd.DataFrame:
    """KIND 상장법인목록 → Code + DESC_COLS. 비거나 형식이 바뀌었으면 예외."""
    r = requests.get(
        KIND_URL, params={"method": "download", "searchType": 13},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout,
    )
    r.raise_for_status()
    p = _TableParser()
    p.feed(r.content.decode("euc-kr", errors="replace"))
    if len(p.rows) < 2:
        raise ValueError("KIND 상장법인목록이 비어 있다")
    header, body = p.rows[0], [row for row in p.rows[1:] if len(row) == len(p.rows[0])]
    missing = set(KIND_COLS) - set(header)
    if missing:
        raise ValueError(f"KIND 상장법인목록 형식 변경 — 없는 컬럼 {sorted(missing)}")
    df = pd.DataFrame(body, columns=header).rename(columns=KIND_COLS)[["Code", *DESC_COLS]]
    df["Code"] = df["Code"].str.strip().str.zfill(6)
    df = df.replace("", None).drop_duplicates("Code")
    if len(df) < KIND_MIN_ROWS:
        raise ValueError(f"KIND 상장법인목록이 너무 짧다 ({len(df)}행)")
    return df


def _cached_desc() -> pd.DataFrame | None:
    """캐시된 마스터의 업종·회사 개요 (index=code, 컬럼=DESC_COLS). 수집 실패 시 폴백용."""
    if not config.STOCKS_CACHE.exists():
        return None
    try:
        prev = pd.read_parquet(config.STOCKS_CACHE)
    except Exception:
        log.exception("캐시 마스터 읽기 실패")
        return None
    cols = [c for c in CACHE_COLS if c in prev]
    if "code" not in prev or not cols:
        return None
    return prev.set_index("code")[cols].rename(columns=CACHE_COLS)


def fetch_stock_master() -> pd.DataFrame:
    """전 종목 마스터를 수집해 필터링한 DataFrame을 돌려준다.

    columns: code, name, market, close, change_pct, marcap(억원), industry, sector
    제외: KONEX, 스팩, 우선주(종목코드 끝자리 != '0')
    시가총액 내림차순 정렬 (백테스트 large 유니버스가 순서에 의존).
    """
    import FinanceDataReader as fdr

    raw = fdr.StockListing("KRX")
    df = raw[raw["MarketId"].isin(MARKETS)].copy()
    # 업종(통계청 산업분류)과 회사 개요(주요제품·상장일·대표자·홈페이지·지역)는
    # KRX 목록에 없고 KIND 상장법인목록에 있다 → code로 조인.
    try:
        df = df.merge(fetch_kind_desc(), on="Code", how="left")
    except Exception:
        # 회사 정보만 실패한 것이므로 시세 마스터까지 버리지는 않는다. 아래에서
        # 마지막으로 성공한 캐시 값으로 채운다 — None으로 두면 전 종목이 '기타'가
        # 되고, 그 결과가 다시 캐시를 덮어써 하루치 실패가 영구화된다.
        log.exception("업종·회사 개요 수집 실패 — 캐시 값으로 폴백")
        for c in DESC_COLS:
            df[c] = None

    # 수집이 성공해도 신규·정리매매 종목은 값이 빌 수 있다. 빈 칸만 캐시로 메운다.
    prev = _cached_desc()
    if prev is not None:
        for c in DESC_COLS:
            if c in prev:
                hole = df[c].isna() | df[c].astype(str).str.strip().eq("")
                df.loc[hole, c] = df.loc[hole, "Code"].map(prev[c])
    df = df[~df["Name"].str.contains("스팩", na=False)]
    df = df[df["Code"].str.endswith("0")]  # 우선주 제외 (5·7·9 등으로 끝남)

    df["Industry"] = df["Industry"].fillna("").astype(str).str.strip()

    # 거래정지·신규상장 종목은 Close/ChagesRatio가 숫자 대신 '-'로 올 수 있다.
    # 한 종목의 '-' 때문에 전체 마스터 갱신을 버리지 않도록 0으로 정규화한다.
    close = pd.to_numeric(df.get("Close"), errors="coerce").fillna(0)
    change_pct = pd.to_numeric(df.get("ChagesRatio"), errors="coerce").fillna(0)
    # Marcap(원) → 억원. 결측·0은 -1로 두어 필터에서 '알 수 없음'으로 취급
    marcap_won = pd.to_numeric(df.get("Marcap"), errors="coerce").fillna(0)
    out = pd.DataFrame(
        {
            "code": df["Code"],
            "name": df["Name"],
            "market": df["MarketId"].map(MARKETS),
            "close": close.astype("int64"),
            "change_pct": change_pct.round(2),
            "marcap": (marcap_won / 1e8).round().astype("int64").where(marcap_won > 0, -1),
            "industry": df["Industry"],
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
