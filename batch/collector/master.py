"""종목 마스터: KRX 상장 종목 목록 수집·필터.

종목 목록·시장·시총·상장주식수는 공공 API 일자별 시세(daystore의 최신 거래일
파일)에서, 업종·회사 개요는 KRX KIND 상장법인목록에서 받는다.

2026-10-13 전환. 예전 목록원(fdr.StockListing("KRX"))은 FDR 저자의 GitHub 캐시를
읽는데, 하루에도 여러 번 갱신돼 시총이 시세보다 하루 앞선 값이었다 (10-12 데이터에
10-13 시총 — 하이닉스 -10%). 업종 지수의 주식 수(시총÷종가)도 그만큼 틀어졌다.
같은 저장소의 회사 정보 폴더는 9/17에 조용히 멈췄다. 이제 목록·시세·시총이 한
응답에서 나오므로 날짜가 어긋날 수 없고, 목록 = 그날 시세가 있는 종목이라
상장폐지·신규상장이 바로 반영된다. 전환 시점 대조: 2,579종목·종목명·시장 모두 일치.
"""

import logging
from html.parser import HTMLParser

import pandas as pd
import requests

from batch import config
from batch.sectors import ETC, sector_of

log = logging.getLogger(__name__)

# KOSPI·KOSDAQ만. KONEX 제외
MARKETS = ("KOSPI", "KOSDAQ")

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


def _latest_day() -> pd.DataFrame:
    """daystore의 가장 최근 거래일 전 종목 행. 마스터 컬럼이 없는 옛 파일이면 예외."""
    from batch.collector import daystore

    days = daystore.stored_days()
    if not days:
        raise ValueError("일자별 시세가 없다 — 수집 후 마스터를 만든다")
    day = pd.read_parquet(daystore.day_path(days[-1]))
    if "name" not in day:
        raise ValueError(f"{days[-1]} 파일에 종목명이 없다 (전환 전 파일)")
    return day


def fetch_stock_master(day: pd.DataFrame | None = None) -> pd.DataFrame:
    """전 종목 마스터를 만들어 필터링한 DataFrame을 돌려준다.

    day: 공공 API 하루치 전 종목 (daily.fetch_day 형식). 없으면 daystore의 최신 거래일.
    columns: code, name, market, close, change_pct, marcap(억원), industry, sector, 회사 개요
    제외: KONEX, 스팩, 우선주(종목코드 끝자리 != '0')
    시가총액 내림차순 정렬 (백테스트 large 유니버스가 순서에 의존).
    """
    raw = _latest_day() if day is None else day
    df = raw[raw["market"].isin(MARKETS)].rename(columns={"code": "Code", "name": "Name"})
    df = df.copy()
    # 업종(통계청 산업분류)과 회사 개요(주요제품·상장일·대표자·홈페이지·지역)는
    # 공공 API 시세에 없고 KIND 상장법인목록에 있다 → code로 조인.
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

    base = df["base"].astype(float)
    change_pct = (df["close"] / base.where(base > 0) - 1).mul(100).fillna(0)
    marcap_won = df["mcap"].astype(float)
    out = pd.DataFrame(
        {
            "code": df["Code"],
            "name": df["Name"],
            "market": df["market"],
            "close": df["close"].astype("int64"),
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
