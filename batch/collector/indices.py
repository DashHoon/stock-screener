"""코스피/코스닥 지수 수집 (네이버 차트 API, 실패 시 FinanceDataReader).

FDR의 KS11/KQ11은 KRX가 출처인데, 2026-09-17 장중 값에서 갱신이 멈췄다
(그날 봉도 장중 미완성 값). 종목 시세와 같은 날짜까지 받으려면 네이버를 1순위로 쓴다.
"""

import datetime as dt
import logging
import re

import pandas as pd
import requests

from batch import config

log = logging.getLogger(__name__)

INDICES = [("KS11", "코스피"), ("KQ11", "코스닥")]
SPARK_DAYS = 20

NAVER_URL = "https://fchart.stock.naver.com/sise.nhn"
NAVER_SYMBOL = {"KS11": "KOSPI", "KQ11": "KOSDAQ"}
TIMEOUT = 20


def _fetch_naver(sym: str, start: str) -> pd.DataFrame | None:
    """네이버 일봉. 항목은 'YYYYMMDD|시|고|저|종|거래량(천주)'."""
    days = (dt.date.today() - dt.date.fromisoformat(start)).days
    resp = requests.get(
        NAVER_URL,
        params={"symbol": NAVER_SYMBOL[sym], "timeframe": "day",
                "count": days, "requestType": 0},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    rows = []
    # 응답은 EUC-KR XML이라 파서가 거부한다. 필요한 값은 ASCII뿐이니 정규식으로 뽑는다.
    for data in re.findall(r'<item data="([^"]+)"', resp.content.decode("ascii", "replace")):
        d, o, h, lo, c, v = data.split("|")
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "open": float(o), "high": float(h),
                     "low": float(lo), "close": float(c), "volume": int(v) * 1000})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    return df[df["date"] >= start]


def _fetch_fdr(sym: str, start: str) -> pd.DataFrame | None:
    import FinanceDataReader as fdr

    raw = fdr.DataReader(sym, start)
    if raw is None or raw.empty:
        return None
    out = raw.reset_index().rename(
        columns={"Date": "date", "Open": "open", "High": "high",
                 "Low": "low", "Close": "close", "Volume": "volume"}
    )[["date", "open", "high", "low", "close", "volume"]]
    out["date"] = pd.to_datetime(out["date"]).dt.date.astype(str)
    return out


def fetch_index_ohlcv(sym: str) -> pd.DataFrame | None:
    """지수 일봉 OHLCV(최근 BACKFILL_YEARS년). 종목 차트 파이프라인과 동일 스키마.

    지수는 소수점 값이라 종목과 달리 float로 유지한다. 오늘 미완성 봉 제거.
    """
    start = (dt.date.today() - dt.timedelta(days=365 * config.BACKFILL_YEARS)).isoformat()
    out = None
    for name, fetch in (("네이버", _fetch_naver), ("FDR", _fetch_fdr)):
        try:
            out = fetch(sym, start)
        except Exception as e:  # noqa: BLE001 — 어떤 실패든 다음 출처로
            log.warning("지수 %s %s 수집 실패: %s", sym, name, e)
            continue
        if out is not None and not out.empty:
            break
    if out is None or out.empty:
        return None
    for c in ["open", "high", "low", "close"]:
        out[c] = out[c].astype(float)
    out["volume"] = out["volume"].fillna(0).astype("int64")
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    # 장중이면 오늘 미완성 봉 제외, 마감 후면 오늘 포함 (종목 수집과 동일 기준)
    from batch.collector.backfill import latest_complete_date

    return out[out["date"] <= latest_complete_date()].reset_index(drop=True)


def summarize(sym: str, name: str, ohlcv: pd.DataFrame) -> dict | None:
    """초기 화면 카드용: 최근값·등락률·미니차트용 종가."""
    if ohlcv is None or len(ohlcv) < 2:
        return None
    close = ohlcv["close"].astype(float)
    last, prev = float(close.iloc[-1]), float(close.iloc[-2])
    return {
        "code": sym,
        "name": name,
        "date": ohlcv["date"].iloc[-1],
        "close": round(last, 2),
        "change_pct": round((last / prev - 1) * 100, 2) if prev else None,
        "spark": [round(float(x), 2) for x in close.iloc[-SPARK_DAYS:]],
    }
