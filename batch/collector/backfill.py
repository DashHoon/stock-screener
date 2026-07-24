"""과거 일봉 백필 + 캐시 증분 갱신.

종목별 parquet(batch/data/cache/ohlcv/{code}.parquet)에 저장한다.
- 캐시가 없으면 BACKFILL_YEARS 만큼 전체 수집
- 캐시가 있으면 마지막 날짜 이후만 이어받는다 (재실행/중단 안전)
- 오늘 날짜 행은 장중 미완성 데이터일 수 있어 버린다

소스는 FinanceDataReader(네이버). 공공 API는 일별 하루치 수집(daily.py) 전용.
"""

import datetime as dt
import logging
from zoneinfo import ZoneInfo

import pandas as pd

from batch import config

log = logging.getLogger(__name__)

COLUMNS = ["date", "open", "high", "low", "close", "volume"]

KST = ZoneInfo("Asia/Seoul")
# 장 마감(15:30) 후 이 시각(KST)을 넘겼으면 당일 봉을 확정 종가로 취급한다.
# 그 전(장중)이면 오늘 봉은 미완성이라 버린다. 러너가 UTC라 KST로 명시 계산.
SETTLE_HOUR = 16


def latest_complete_date() -> str:
    """확정된 최신 일봉 날짜(KST 기준). 장 마감·정산 후면 오늘, 아니면 어제."""
    now = dt.datetime.now(KST)
    if now.hour >= SETTLE_HOUR:
        return now.date().isoformat()
    return (now.date() - dt.timedelta(days=1)).isoformat()


def cache_path(code: str):
    return config.OHLCV_CACHE_DIR / f"{code}.parquet"


def load_cached(code: str) -> pd.DataFrame | None:
    p = cache_path(code)
    if p.exists():
        return pd.read_parquet(p)
    return None


def _fetch_range(code: str, start_iso: str) -> pd.DataFrame | None:
    """start부터 오늘까지 일봉 수집. 긴 구간은 2년 조각으로 나눠 받는다.

    수집원(네이버)이 대용량(수년치) 요청 연타 시 응답을 조르는 것이 확인되어,
    검증된 크기(~2년)를 넘는 요청은 분할한다. (2026-07 실측: 10년 통짜 요청은
    200건 부근부터 정체, 2년 조각은 수천 건도 정상)
    """
    import FinanceDataReader as fdr

    start = dt.date.fromisoformat(start_iso)
    today = dt.date.today()
    if (today - start).days <= 800:
        return fdr.DataReader(code, start_iso)

    frames = []
    cur = start
    while cur < today:
        end = min(cur + dt.timedelta(days=729), today)
        piece = fdr.DataReader(code, cur.isoformat(), end.isoformat())
        if piece is not None and not piece.empty:
            frames.append(piece)
        cur = end + dt.timedelta(days=1)
    if not frames:
        return None
    return pd.concat(frames)


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
    # 확정 최신일까지만 유지 (장중이면 오늘 미완성 봉 제외, 마감 후면 오늘 포함)
    return out[out["date"] <= latest_complete_date()].reset_index(drop=True)


def update_one(code: str, start: str | None = None) -> int:
    """한 종목을 백필/증분 갱신. 추가된 행 수를 돌려준다."""
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

    if fetch_from > latest_complete_date():
        return 0

    raw = _fetch_range(code, fetch_from)
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


def rebuild_one(code: str) -> int:
    """전체 기간을 새로 받아 캐시를 통째로 교체한다 (수정주가 재반영).

    기업행위(증자·분할 등)로 과거 가격이 소급 수정된 종목에 사용.
    수신 실패나 빈 응답이면 기존 캐시를 그대로 보존한다.
    """
    start = (
        dt.date.today() - dt.timedelta(days=365 * config.BACKFILL_YEARS)
    ).isoformat()
    raw = _fetch_range(code, start)
    if raw is None or raw.empty:
        return 0
    new = _normalize(raw)
    if new.empty:
        return 0
    config.OHLCV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    new.to_parquet(cache_path(code), index=False)
    return len(new)


def update_all(
    codes: list[str],
    rebuild: bool = False,
    max_workers: int = 6,
) -> dict:
    """전 종목 백필/증분 갱신. {code: added_rows} 실패 종목은 -1.

    rebuild=True면 증분이 아니라 전체 기간을 새로 받아 교체한다 (주 1회 정합성 보정).
    네트워크 왕복 지연이 지배적이라(특히 GitHub 러너는 해외) 스레드 병렬로 수집한다.
    종목당 파일이 분리돼 있어 쓰기 충돌 없음.
    rebuild(10년 × 조각 5개 = 대량 요청)는 청크 사이에 쉬어 수집원 조르기를 예방한다.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from batch.collector.httpguard import install_timeout_guard

    # 응답 없는 연결이 스레드를 영원히 물지 않도록 requests 레벨에서 타임아웃 강제
    # (socket.setdefaulttimeout은 requests가 무시하므로 소용없음)
    install_timeout_guard(15)

    fetch = rebuild_one if rebuild else update_one
    chunk_size = 300 if rebuild else len(codes) or 1
    result: dict[str, int] = {}
    done = 0
    for ci in range(0, len(codes), chunk_size):
        chunk = codes[ci : ci + chunk_size]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(fetch, code): code for code in chunk}
            for fut in as_completed(futures):
                code = futures[fut]
                try:
                    result[code] = fut.result()
                except Exception as e:
                    log.warning("%s 수집 실패: %s", code, e)
                    result[code] = -1
                done += 1
                if done % 200 == 0:
                    log.info("진행 %d/%d", done, len(codes))
        if rebuild and ci + chunk_size < len(codes):
            rate = len(chunk) / max(time.time() - t0, 0.1)
            cooldown = 90 if rate < 1 else 30  # 느려졌으면 조르기 신호 → 더 쉼
            time.sleep(cooldown)

    # 네이버 조르기로 타임아웃 난 종목은 잠시 쉬었다 재시도한다 (증분 수집 한정).
    # 동시요청을 낮춰 얌전히 재시도하면 대부분 회수된다 (실측 4% → 1% 미만).
    if not rebuild:
        for attempt in range(1, 3):
            failed = [c for c, v in result.items() if v == -1]
            if not failed:
                break
            time.sleep(20)
            log.info("타임아웃 %d종목 재시도 (%d차)", len(failed), attempt)
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(fetch, code): code for code in failed}
                for fut in as_completed(futures):
                    code = futures[fut]
                    try:
                        result[code] = fut.result()
                    except Exception as e:
                        log.warning("%s 재시도 실패: %s", code, e)
                        result[code] = -1

    ok = sum(1 for v in result.values() if v >= 0)
    log.info("백필 완료: 성공 %d / 실패 %d", ok, len(codes) - ok)
    return result
