"""공공데이터포털 일별 시세 수집 (금융위원회_주식시세정보 getStockPriceInfo).

basDt(기준일자) 하루치를 전 종목 페이징으로 받는다. 하루 지연 시세.
API 키는 환경변수 DATA_GO_KR_API_KEY (GitHub Secrets / .env).

아직 미갱신(또는 휴장일)이면 빈 DataFrame을 돌려준다. 날짜별 저장과
수정주가 계산은 daystore.py가 맡는다.
"""

import logging
import os
import time

import pandas as pd
import requests


log = logging.getLogger(__name__)

BASE_URL = (
    "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
)
# 하루치 전 종목이 2,900행 안팎이라 한 쪽에 다 들어온다 — 하루 1회 호출.
PAGE_SIZE = 5000
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
            # 기준가 = 종가 - 전일 대비. 평소엔 전일 종가와 같고, 분할·증자 등
            # 권리 변동이 있던 날만 달라진다 — 수정주가 비율이 여기서 나온다.
            "base": pd.to_numeric(df["clpr"]) - pd.to_numeric(df["vs"]),
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
    for c in ["open", "high", "low", "close", "volume", "base"]:
        out[c] = out[c].astype("int64")
    log.info("basDt=%s %d종목 수집", bas_dt, len(out))
    return out.reset_index(drop=True)
