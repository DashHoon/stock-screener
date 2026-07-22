"""10년 데이터 마이그레이션 — Claude 없이 독립 실행하는 스크립트.

사용법 (터미널에서):
    cd /Volumes/WorkDrive/WebService/StockScreener
    nohup .venv/bin/python scripts/migrate_10y.py > migrate_10y.log 2>&1 &
    tail -f migrate_10y.log          # 진행 확인 (Ctrl+C로 보기만 종료)

특징:
- 이어받기: 이미 10년치로 교체된 종목은 건너뛴다. 몇 번을 재실행해도 안전.
- 행업 방어: 요청당 20초 타임아웃, 실패 종목은 마지막에 한 번 더 재시도.
- 로컬 config(BACKFILL_YEARS)와 무관하게 10년으로 강제한다.

⚠️ 로컬 캐시만 바꾼다. 서비스(CI)에 반영하려면 마이그레이션 완료 후:
   1) batch/config.py 의 BACKFILL_YEARS = 10
   2) .github/workflows/daily-batch.yml 캐시 키에 버전 접두어 추가 (예: ohlcv-cache-10y-)
   → push하면 다음 CI 실행이 서버 캐시를 새로 구축한다 (병렬+타임아웃 적용됨).
   이 전환 전까지는 토요일 CI 재백필이 2년 기준으로 돌므로 서비스는 2년 범위 유지.
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from batch import config  # noqa: E402

config.BACKFILL_YEARS = 10  # 이 스크립트에 한해 10년 강제

from batch.collector import backfill, master  # noqa: E402

YEARS_CUTOFF = "2024-06-01"  # 캐시 시작일이 이보다 늦으면 아직 2년치로 간주


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    log = logging.getLogger("migrate")

    stocks = master.load_or_fetch_master(refresh=False)
    codes = stocks["code"].tolist()

    todo = []
    for c in codes:
        df = backfill.load_cached(c)
        if df is None or len(df) == 0 or df["date"].iloc[0] >= YEARS_CUTOFF:
            todo.append(c)
    log.info("대상 %d / 전체 %d (나머지는 이미 10년치)", len(todo), len(codes))
    if not todo:
        log.info("할 일 없음 — 마이그레이션 완료 상태")
        return

    t0 = time.time()
    result = backfill.update_all(todo, rebuild=True)
    failed = [c for c, v in result.items() if v < 0]
    log.info("1차 완료 %.1f분, 실패 %d", (time.time() - t0) / 60, len(failed))

    if failed:
        log.info("실패 %d종목 재시도", len(failed))
        result2 = backfill.update_all(failed, rebuild=True)
        still = [c for c, v in result2.items() if v < 0]
        log.info("재시도 후 실패 %d: %s", len(still), ",".join(still[:20]))

    done = sum(
        1 for c in codes
        if (df := backfill.load_cached(c)) is not None
        and len(df) and df["date"].iloc[0] < YEARS_CUTOFF
    )
    log.info("최종: 10년치 확보 %d / %d (%.0f%%)", done, len(codes), done / len(codes) * 100)


if __name__ == "__main__":
    main()
