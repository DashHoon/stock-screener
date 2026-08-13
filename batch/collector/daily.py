"""공공데이터포털 일별 시세 수집 (금융위원회_주식시세정보 getStockPriceInfo).

basDt(기준일자) 하루치를 전 종목 페이징으로 받는다. 하루 지연 시세.
API 키는 환경변수 DATA_GO_KR_API_KEY (GitHub Secrets / .env).

키가 없거나 아직 미갱신이면 빈 DataFrame을 돌려주고,
run.py는 FinanceDataReader 증분 갱신으로 폴백한다.
"""

import logging
import os
import time

import pandas as pd
import requests

from batch import config
from batch.collector import backfill
from batch.collector.backfill import cache_path, load_cached

log = logging.getLogger(__name__)

BASE_URL = (
    "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
)
PAGE_SIZE = 1000
# 포털이 간헐적으로 접속을 안 받는다. GitHub 러너(해외 IP)에서 특히 잦고,
# 한 번 끊길 때마다 배치가 통째로 죽었다 (2026-08-13 #63·#64 연속 실패:
# ConnectTimeout, 51초 만에 exit 1). 페이지 단위로 재시도한다.
FETCH_RETRIES = 4
FETCH_BACKOFF = 5  # 초. 5 → 10 → 20 으로 늘려 가며 기다린다


def api_key() -> str | None:
    return os.environ.get("DATA_GO_KR_API_KEY") or None


def _get_page(params: dict, timeout: int) -> dict:
    """한 페이지를 받아 body를 돌려준다. 접속 실패는 물러서며 재시도한다.

    끝까지 실패하면 마지막 예외를 그대로 올린다 — 호출부(fetch_day)가 잡아서
    '그날 수집 없음'으로 넘긴다. 없는 데이터를 억지로 만드는 것보다 낫다.
    """
    last: Exception | None = None
    for attempt in range(FETCH_RETRIES):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["response"]["body"]
        except (requests.RequestException, ValueError, KeyError) as e:
            last = e
            if attempt == FETCH_RETRIES - 1:
                break
            wait = FETCH_BACKOFF * (2**attempt)
            log.warning(
                "공공 API 응답 실패 (%d/%d) — %ds 후 재시도: %s",
                attempt + 1, FETCH_RETRIES, wait, type(e).__name__,
            )
            time.sleep(wait)
    raise last  # type: ignore[misc]


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
        body = _get_page(
            {
                "serviceKey": key,
                "resultType": "json",
                "numOfRows": PAGE_SIZE,
                "pageNo": page,
                "basDt": bas_dt,
            },
            timeout,
        )
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
    # 거래가 없던 날은 시/고/저가 0으로 오고 종가만 채워진다 (거래량 0).
    # 그 행을 버리면 해당 종목이 그날 갱신되지 않는다 — 2026-08-05 기준 146종목이
    # 이에 해당했고(한화·드림어스컴퍼니 등), 지금까지는 fdr(네이버)이 뒤에서 메워
    # 드러나지 않았다. 네이버 경로를 걷어내면서 표면화됐다.
    # 종가로 시/고/저를 채운다 — 거래 없는 날의 표준 표기이며 지표 계산도 이걸 쓴다.
    no_trade = (out[["open", "high", "low"]] == 0).all(axis=1) & (out["close"] > 0)
    for c in ("open", "high", "low"):
        out.loc[no_trade, c] = out.loc[no_trade, "close"]
    # 종가까지 0인 행만 버린다 (상장폐지·데이터 결손)
    out = out[(out[["open", "high", "low", "close"]] != 0).all(axis=1)]
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = out[c].astype("int64")
    log.info("basDt=%s %d종목 수집", bas_dt, len(out))
    return out.reset_index(drop=True)


def is_discontinuous(prev_close: float, new_close: float) -> bool:
    """전일 종가 대비 변동이 임계치를 넘는가 (기업행위로 인한 수정주가 의심).

    한국 주식은 가격제한폭(±30%)이 있어 그 이상의 변동은 정상 거래로 불가능하다.
    임계치(REBUILD_JUMP_PCT)와 오탐 비용은 config 주석 참고.
    """
    if prev_close <= 0:
        return False
    return abs(new_close / prev_close - 1) * 100 >= config.REBUILD_JUMP_PCT


def merge_into_cache(day: pd.DataFrame) -> int:
    """하루치 수집분을 종목별 parquet 캐시에 병합. 갱신한 종목 수를 돌려준다.

    전일 대비 비정상 급변 종목은 병합하지 않고 캐시를 통째로 재수집한다
    (기업행위로 과거 가격이 소급 수정됐을 가능성 — 섞어 붙이면 가짜 시그널 발생).
    """
    updated = 0
    suspects: list[str] = []
    for code, g in day.groupby("code"):
        cached = load_cached(code)
        if cached is None:
            continue  # 백필된 적 없는 종목(신규상장 등)은 다음 백필에서 처리
        if g["date"].iloc[-1] <= cached["date"].iloc[-1]:
            continue
        if is_discontinuous(cached["close"].iloc[-1], g["close"].iloc[-1]):
            suspects.append(code)
            continue
        merged = (
            pd.concat([cached, g[cached.columns]])
            .drop_duplicates("date")
            .sort_values("date")
            .reset_index(drop=True)
        )
        merged.to_parquet(cache_path(code), index=False)
        updated += 1

    rebuilt = 0
    for code in suspects:
        try:
            if backfill.rebuild_one(code):
                rebuilt += 1
        except Exception as e:
            log.warning("%s 캐시 재구축 실패: %s", code, e)
    if suspects:
        log.info("급변 감지 %d종목 → 재구축 %d종목 성공: %s",
                 len(suspects), rebuilt, ",".join(suspects))
    log.info("캐시 병합: %d종목 갱신", updated)
    return updated
