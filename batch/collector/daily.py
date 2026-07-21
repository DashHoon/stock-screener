"""공공데이터포털 일별 시세 수집 (금융위원회_주식시세정보 getStockPriceInfo).

basDt(기준일자) 하루치를 전 종목 페이징으로 받는다. 하루 지연 시세.
API 키는 환경변수 DATA_GO_KR_API_KEY (GitHub Secrets / .env).

키가 없거나 아직 미갱신이면 빈 DataFrame을 돌려주고,
run.py는 FinanceDataReader 증분 갱신으로 폴백한다.
"""

import logging
import os

import pandas as pd
import requests

from batch.collector.backfill import cache_path, load_cached

log = logging.getLogger(__name__)

BASE_URL = (
    "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
)
PAGE_SIZE = 1000


def api_key() -> str | None:
    return os.environ.get("DATA_GO_KR_API_KEY") or None


def fetch_day(bas_dt: str, timeout: int = 30) -> pd.DataFrame:
    """bas_dt(YYYYMMDD) 하루치 전 종목 시세. 휴장일/미갱신이면 빈 DataFrame.

    columns: code, date, open, high, low, close, volume
    """
    key = api_key()
    if not key:
        raise RuntimeError("DATA_GO_KR_API_KEY가 설정되지 않았습니다")

    rows: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            BASE_URL,
            params={
                "serviceKey": key,
                "resultType": "json",
                "numOfRows": PAGE_SIZE,
                "pageNo": page,
                "basDt": bas_dt,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()["response"]["body"]
        total = int(body.get("totalCount", 0))
        items = body.get("items") or {}
        chunk = items.get("item") or []
        if isinstance(chunk, dict):  # 결과 1건이면 dict로 옴
            chunk = [chunk]
        rows.extend(chunk)
        if page * PAGE_SIZE >= total or not chunk:
            break
        page += 1

    if not rows:
        log.info("basDt=%s 데이터 없음 (휴장일 또는 미갱신)", bas_dt)
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    out = pd.DataFrame(
        {
            "code": df["srtnCd"].str[-6:],  # 'A005930' 형태 방어
            "date": pd.to_datetime(df["basDt"]).dt.date.astype(str),
            "open": pd.to_numeric(df["mkp"]),
            "high": pd.to_numeric(df["hipr"]),
            "low": pd.to_numeric(df["lopr"]),
            "close": pd.to_numeric(df["clpr"]),
            "volume": pd.to_numeric(df["trqu"]),
        }
    )
    out = out[(out[["open", "high", "low", "close"]] != 0).all(axis=1)]
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = out[c].astype("int64")
    log.info("basDt=%s %d종목 수집", bas_dt, len(out))
    return out.reset_index(drop=True)


def merge_into_cache(day: pd.DataFrame) -> int:
    """하루치 수집분을 종목별 parquet 캐시에 병합. 갱신한 종목 수를 돌려준다."""
    updated = 0
    for code, g in day.groupby("code"):
        cached = load_cached(code)
        if cached is None:
            continue  # 백필된 적 없는 종목(신규상장 등)은 다음 백필에서 처리
        if g["date"].iloc[-1] <= cached["date"].iloc[-1]:
            continue
        merged = (
            pd.concat([cached, g[cached.columns]])
            .drop_duplicates("date")
            .sort_values("date")
            .reset_index(drop=True)
        )
        merged.to_parquet(cache_path(code), index=False)
        updated += 1
    log.info("캐시 병합: %d종목 갱신", updated)
    return updated
