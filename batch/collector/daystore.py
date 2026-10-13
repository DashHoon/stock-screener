"""종목 일봉의 단일 원천 — 공공데이터포털 '일자별 전 종목 시세'.

2026-10-13 전환. 그 전에는 평일엔 공공 API(KRX 정규장 종가), 주말 재백필과
급변 종목 재구축엔 네이버(시간외 거래가 섞인 값)를 써서 두 출처가 한 차트에
섞였다. 같은 날 가격이 주마다 바뀌었고(10-08 기준 83% 종목), 네이버가 버리는
거래정지일과 공공 API가 평평한 봉으로 주는 거래정지일이 엇갈려 190종목 차트에
구멍이 났다. 네이버는 매일 대량으로 부르면 막히기도 한다.

이제 원천은 하나다:
  1. 거래일마다 그날 전 종목을 한 번에 받아 날짜별 파일로 둔다 (하루 1회 호출)
  2. 종목별 시계열은 매 회차 이 파일들에서 새로 만든다 — 캐시가 원천과 어긋날
     수 없다
  3. 수정주가는 응답의 기준가(종가 - 전일 대비)로 계산한다. 기준가가 전일
     종가와 다른 날이 권리 변동일이고, 그 비율을 이전 봉 전체에 곱한다
거래일 달력은 지수(네이버 2회 호출)에서 가져와 '빠진 날'을 시장 단위로 판정한다.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging

import numpy as np
import pandas as pd

from batch import config
from batch.collector import daily

log = logging.getLogger(__name__)

DAY_DIR = config.CACHE_DIR / "days"
NO_TRADE_PATH = config.DATA_DIR / "no_trade_days.json"
# 공급처가 며칠 뒤 값을 고치는 경우가 있어 최근 며칠은 매 회차 다시 받는다
REFRESH_RECENT = 3
# 포털 장애 중엔 더 두드리지 않는다
MAX_CONSECUTIVE_FAILURES = 3
PRICE_COLS = ["open", "high", "low", "close"]
# 이보다 작은 기준가 차이는 호가 단위 반올림이다 (스팩 등에서 0.14%가 반복해서
# 잡힌다 — 그대로 곱하면 과거 가격이 조금씩 밀린다). 실제 권리 변동은 연말
# 주식배당(~2%)이 가장 작은 축이다.
MIN_ADJUST = 0.005


def day_path(day: str):
    return DAY_DIR / f"{day}.parquet"


def stored_days() -> list[str]:
    if not DAY_DIR.exists():
        return []
    return sorted(p.stem for p in DAY_DIR.glob("*.parquet"))


def _no_trade_days() -> set[str]:
    try:
        return set(json.loads(NO_TRADE_PATH.read_text()))
    except Exception:
        return set()


def _remember_no_trade(day: str) -> None:
    days = _no_trade_days() | {day}
    NO_TRADE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NO_TRADE_PATH.write_text(json.dumps(sorted(days)))


def market_calendar() -> list[str] | None:
    """거래일 목록(과거→최근). 코스피 지수 일봉 날짜를 그대로 쓴다.

    지수는 하루 하나라 휴장일이 정확히 빠져 있다. 받지 못하면 None — 호출부가
    평일 달력으로 대신한다.
    """
    from batch.collector.indices import fetch_index_ohlcv

    try:
        df = fetch_index_ohlcv("KS11")
    except Exception as e:  # noqa: BLE001
        log.warning("거래일 달력(지수) 수집 실패: %s", e)
        return None
    if df is None or df.empty:
        return None
    return df["date"].astype(str).tolist()


def _weekday_calendar(start: dt.date) -> list[str]:
    """지수를 못 받았을 때의 대비책. 알려진 휴장일만 뺀 평일."""
    skip = _no_trade_days()
    out, d = [], start
    while d <= dt.date.today():
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


@dataclasses.dataclass
class SyncResult:
    latest: str | None          # 받아 둔 가장 최근 거래일
    gaps: list[str]             # latest 이전인데 없는 거래일 (배포하면 안 되는 상태)
    pending: list[str]          # latest 이후 아직 공급처에 안 올라온 거래일 (정상)
    fetched: int
    complete: bool = True       # 포털 장애로 중간에 멈췄으면 False — 배포하면 안 된다


def sync(history_bars: int = config.HISTORY_BARS, force: bool = False) -> SyncResult:
    """창(history_bars 거래일) 안의 빠진 날을 받는다.

    빈 응답이 온 날은 두 가지다: 공급처가 아직 안 올린 최근 날(pending)과,
    지난 날인데 끝내 비어 있는 날(gap). 후자는 차트에 구멍이 나므로 호출부가
    배포를 막는다.
    """
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    cal = market_calendar()
    from_index = cal is not None
    if not from_index:
        cal = _weekday_calendar(dt.date.today() - dt.timedelta(days=int(history_bars * 1.6)))
    window = cal[-history_bars:]

    have = set(stored_days())
    todo = [d for d in window if force or d not in have]
    # 최근 몇 거래일은 고침이 있을 수 있어 다시 받는다
    recent = [d for d in window if d in have][-REFRESH_RECENT:]
    todo = sorted(set(todo) | set(recent))

    fetched = failures = 0
    empty: list[str] = []
    unreached: list[str] = []
    for i, d in enumerate(todo):
        try:
            day = daily.fetch_day(d.replace("-", ""))
        except Exception:
            failures += 1
            log.warning("공공 API 수집 실패 %s", d)
            if failures >= MAX_CONSECUTIVE_FAILURES:
                log.warning("연속 실패 %d회 — 이번 회차 수집 중단", failures)
                unreached = [x for x in todo[i + 1:] if x not in have]
                break
            continue
        failures = 0
        if day.empty:
            empty.append(d)
            continue
        day.to_parquet(day_path(d), index=False)
        have.add(d)
        fetched += 1

    in_window = [d for d in window if d in have]
    latest = in_window[-1] if in_window else None
    gaps, pending = [], []
    for d in window:
        if d in have:
            continue
        if latest is not None and d < latest:
            if not from_index and d in empty:
                # 평일 달력이면 빈 날은 휴장일이다 (충분히 지난 날만 확정)
                if (dt.date.today() - dt.date.fromisoformat(d)).days >= 3:
                    _remember_no_trade(d)
                continue
            gaps.append(d)
        else:
            pending.append(d)
    if unreached:
        log.warning("미수집 %d일 (다음 회차에 이어서): %s…", len(unreached), unreached[:3])
    log.info("일자별 시세 동기화: 신규 %d일, 최신 %s, 구멍 %d일, 대기 %d일",
             fetched, latest, len(gaps), len(pending))
    _prune(window)
    return SyncResult(latest, gaps, pending, fetched, complete=not unreached)


def _prune(window: list[str]) -> None:
    """창 밖 날짜 파일 정리 — 캐시가 끝없이 커지지 않게."""
    if not window:
        return
    for p in DAY_DIR.glob("*.parquet"):
        if p.stem < window[0]:
            p.unlink()


def adjust(g: pd.DataFrame, calendar_index: dict[str, int]) -> pd.DataFrame:
    """한 종목의 원시 일봉(날짜순)에 수정주가를 적용한다.

    기준가가 전일 종가와 다른 날 t가 권리 변동일이다. f = 기준가 / 전일 종가를
    t 이전 모든 봉의 가격에 곱하고 거래량은 나눈다. 전일 봉이 바로 앞 거래일이
    아닐 때(그 사이 행이 없을 때)는 비교 대상이 틀리므로 보정하지 않는다.
    """
    g = g.sort_values("date").reset_index(drop=True)
    n = len(g)
    if n < 2:
        return g.drop(columns=["base"], errors="ignore")
    close = g["close"].to_numpy(dtype=float)
    base = g["base"].to_numpy(dtype=float)
    pos = g["date"].map(calendar_index).to_numpy()
    f = np.ones(n)
    for i in range(1, n):
        if base[i] <= 0 or close[i - 1] <= 0 or base[i] == close[i - 1]:
            continue
        if pos[i] != pos[i - 1] + 1:
            continue
        ratio = base[i] / close[i - 1]
        if abs(ratio - 1) >= MIN_ADJUST:
            f[i] = ratio
    # 봉 i에 곱할 값 = f[i+1] × f[i+2] × … (이후 모든 권리 변동의 누적)
    mult = np.append(np.cumprod(f[::-1])[::-1][1:], 1.0)
    out = g.drop(columns=["base"]).copy()
    if (mult != 1.0).any():
        for c in PRICE_COLS:
            out[c] = np.rint(out[c].to_numpy(dtype=float) * mult).astype("int64")
        out["volume"] = np.rint(out["volume"].to_numpy(dtype=float) / mult).astype("int64")
    return out


def build_cache(window: list[str] | None = None) -> int:
    """날짜별 파일 → 종목별 OHLCV 캐시(backfill.load_cached가 읽는 형식).

    매 회차 통째로 다시 만든다. 원천에 없는 종목의 캐시 파일은 지운다.
    """
    days = window or stored_days()
    frames = [pd.read_parquet(day_path(d)) for d in days if day_path(d).exists()]
    if not frames:
        return 0
    allrows = pd.concat(frames, ignore_index=True)
    cal_index = {d: i for i, d in enumerate(sorted(allrows["date"].unique()))}
    config.OHLCV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written = set()
    cols = ["date", "open", "high", "low", "close", "volume"]
    for code, g in allrows.groupby("code", sort=False):
        adj = adjust(g, cal_index)[cols]
        adj.to_parquet(config.OHLCV_CACHE_DIR / f"{code}.parquet", index=False)
        written.add(code)
    for p in config.OHLCV_CACHE_DIR.glob("*.parquet"):
        if p.stem not in written:
            p.unlink()
    log.info("종목별 캐시 재구성: %d종목 (%d거래일)", len(written), len(cal_index))
    return len(written)
