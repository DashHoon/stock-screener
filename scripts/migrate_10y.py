"""10년 데이터 마이그레이션 — Claude 없이 독립 실행하는 스크립트. (v2: 분할 요청)

사용법 (터미널에서):
    cd /Volumes/WorkDrive/WebService/StockScreener
    nohup .venv/bin/python scripts/migrate_10y.py > migrate_10y.log 2>&1 &
    tail -f migrate_10y.log          # 진행 확인 (Ctrl+C로 보기만 종료)

수집원(네이버)이 "10년치 통짜 요청"을 연타하면 응답을 조르는 것이 확인되어,
검증된 크기인 2년 조각 5개로 나눠 받고 일정량마다 쉬어간다.

- 이어받기: 이미 10년치로 교체된 종목은 건너뛴다. 재실행 안전.
- 행업 방어: 소켓 20초 타임아웃 + 조각 단위 재시도.
- 실패 종목은 기존 캐시를 보존하고 마지막에 한 번 더 재시도.

⚠️ 로컬 캐시만 바꾼다. 완료 후 서비스(CI) 전환은 Claude에게 "10년 전환해줘"라고 요청.
"""

import datetime as dt
import logging
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch.collector import master  # noqa: E402
from batch.collector.backfill import _normalize, cache_path, load_cached  # noqa: E402

YEARS = 10
SLICE_DAYS = 730            # 검증된 요청 크기 (2년)
WORKERS = 4
CHUNK = 300                 # 이만큼 처리할 때마다
COOLDOWN_SEC = 45           # 이만큼 쉰다 (조르기 방지)
YEARS_CUTOFF = "2024-06-01"  # 캐시 시작일이 이보다 늦으면 아직 2년치로 간주

log = logging.getLogger("migrate")


def fetch_10y_sliced(code: str) -> pd.DataFrame | None:
    """2년 조각 5개로 10년치를 받아 합친다. 조각 실패 시 1회 재시도."""
    import FinanceDataReader as fdr

    today = dt.date.today()
    start = today - dt.timedelta(days=365 * YEARS)
    frames = []
    cur = start
    while cur < today:
        end = min(cur + dt.timedelta(days=SLICE_DAYS - 1), today)
        for attempt in (1, 2):
            try:
                piece = fdr.DataReader(code, cur.isoformat(), end.isoformat())
                break
            except Exception:
                if attempt == 2:
                    return None
                time.sleep(2)
        if piece is not None and not piece.empty:
            frames.append(piece)
        cur = end + dt.timedelta(days=1)
    if not frames:
        return None
    merged = _normalize(pd.concat(frames))
    return merged.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def rebuild_10y(code: str) -> bool:
    df = fetch_10y_sliced(code)
    if df is None or df.empty:
        return False  # 기존 캐시 보존
    df.to_parquet(cache_path(code), index=False)
    return True


def run(codes: list[str]) -> list[str]:
    """청크 단위 병렬 처리 + 청크 사이 쿨다운. 실패 코드 목록을 돌려준다."""
    failed: list[str] = []
    done = 0
    for ci in range(0, len(codes), CHUNK):
        chunk = codes[ci : ci + CHUNK]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(rebuild_10y, c): c for c in chunk}
            for fut in as_completed(futures):
                c = futures[fut]
                try:
                    if not fut.result():
                        failed.append(c)
                except Exception as e:
                    log.warning("%s 실패: %s", c, e)
                    failed.append(c)
                done += 1
        rate = len(chunk) / max(time.time() - t0, 0.1)
        log.info("진행 %d/%d (청크 속도 %.1f종목/초, 누적 실패 %d)",
                 done, len(codes), rate, len(failed))
        if ci + CHUNK < len(codes):
            # 청크가 비정상적으로 느려졌으면 조르기 신호 → 더 길게 쉰다
            cooldown = COOLDOWN_SEC * (3 if rate < 1 else 1)
            log.info("쿨다운 %d초", cooldown)
            time.sleep(cooldown)
    return failed


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    socket.setdefaulttimeout(20)

    stocks = master.load_or_fetch_master(refresh=False)
    codes = stocks["code"].tolist()
    todo = []
    for c in codes:
        df = load_cached(c)
        if df is None or len(df) == 0 or df["date"].iloc[0] >= YEARS_CUTOFF:
            todo.append(c)
    log.info("대상 %d / 전체 %d (나머지는 이미 10년치)", len(todo), len(codes))
    if not todo:
        log.info("할 일 없음 — 마이그레이션 완료 상태")
        return

    t0 = time.time()
    failed = run(todo)
    log.info("1차 완료 %.1f분, 실패 %d", (time.time() - t0) / 60, len(failed))
    if failed:
        log.info("실패 %d종목 재시도 (60초 후)", len(failed))
        time.sleep(60)
        still = run(failed)
        log.info("재시도 후 실패 %d: %s", len(still), ",".join(still[:20]))

    ok = sum(
        1 for c in codes
        if (df := load_cached(c)) is not None
        and len(df) and df["date"].iloc[0] < YEARS_CUTOFF
    )
    log.info("최종: 10년치 확보 %d / %d (%.0f%%)", ok, len(codes), ok / len(codes) * 100)
    log.info("다음 단계: Claude에게 '10년 전환해줘' 요청 (서비스 설정 전환 + 재산출·배포)")


if __name__ == "__main__":
    main()
