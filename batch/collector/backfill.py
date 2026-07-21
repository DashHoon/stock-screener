"""과거 일봉 백필 + 캐시 증분 갱신.

종목별 parquet(batch/data/cache/ohlcv/{code}.parquet)에 저장한다.
- 캐시가 없으면 BACKFILL_YEARS 만큼 전체 수집
- 캐시가 있으면 마지막 날짜 이후만 이어받는다 (재실행/중단 안전)
- 오늘 날짜 행은 장중 미완성 데이터일 수 있어 버린다

소스는 FinanceDataReader(네이버). 공공 API는 일별 하루치 수집(daily.py) 전용.
"""

import datetime as dt
import logging
import time

import pandas as pd

from batch import config

log = logging.getLogger(__name__)

COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def cache_path(code: str):
    return config.OHLCV_CACHE_DIR / f"{code}.parquet"


def load_cached(code: str) -> pd.DataFrame | None:
    p = cache_path(code)
    if p.exists():
        return pd.read_parquet(p)
    return None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.reset_index().rename(
        columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        }
    )[COLUMNS]
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    for c in ["open", "high", "low", "close"]:
        out[c] = out[c].astype("int64")
    out["volume"] = out["volume"].astype("int64")
    # 거래정지 등으로 OHLC가 0인 행 제거
    out = out[(out[["open", "high", "low", "close"]] != 0).all(axis=1)]
    # 오늘(미완성 봉) 제거
    today = dt.date.today().isoformat()
    return out[out["date"] < today].reset_index(drop=True)


def update_one(code: str, start: str | None = None) -> int:
    """한 종목을 백필/증분 갱신. 추가된 행 수를 돌려준다."""
    import FinanceDataReader as fdr

    cached = load_cached(code)
    if cached is not None and len(cached):
        fetch_from = (
            dt.date.fromisoformat(cached["date"].iloc[-1]) + dt.timedelta(days=1)
        ).isoformat()
    else:
        cached = None
        fetch_from = start or (
            dt.date.today() - dt.timedelta(days=365 * config.BACKFILL_YEARS)
        ).isoformat()

    if fetch_from >= dt.date.today().isoformat():
        return 0

    raw = fdr.DataReader(code, fetch_from)
    if raw is None or raw.empty:
        return 0
    new = _normalize(raw)
    if new.empty:
        return 0

    merged = (
        pd.concat([cached, new]).drop_duplicates("date").sort_values("date")
        if cached is not None
        else new
    ).reset_index(drop=True)

    config.OHLCV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(cache_path(code), index=False)
    return len(new)


def update_all(codes: list[str], sleep_every: int = 50, sleep_sec: float = 1.0) -> dict:
    """전 종목 백필/증분 갱신. {code: added_rows} 실패 종목은 -1."""
    result: dict[str, int] = {}
    for i, code in enumerate(codes, 1):
        try:
            result[code] = update_one(code)
        except Exception as e:
            log.warning("%s 수집 실패: %s", code, e)
            result[code] = -1
        if i % sleep_every == 0:
            log.info("진행 %d/%d", i, len(codes))
            time.sleep(sleep_sec)
    ok = sum(1 for v in result.values() if v >= 0)
    log.info("백필 완료: 성공 %d / 실패 %d", ok, len(codes) - ok)
    return result
