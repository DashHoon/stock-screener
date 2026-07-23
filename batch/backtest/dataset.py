"""클라이언트 백테스트용 경량 데이터셋 산출.

브라우저가 사용자 정의 조합 백테스트를 직접 돌릴 수 있도록,
종목별 [종가 시계열 + 각 시그널의 발생일 인덱스]를 하나의 JSON으로 낸다.
서버는 이 정적 파일만 서빙하고 계산은 클라이언트가 한다 (서버 비용 0).

포맷 (web/public/data/bt/dataset.json):
{
  "date": "YYYY-MM-DD",
  "horizons": [5,10,20,60],
  "sigKeys": ["rsi_oversold", ...],        # 시그널 인덱스 매핑
  "stocks": [
    {"code","name","cap",
     "c": [860, 862, ...],                 # 종가 (인덱스 = 거래일 순번)
     "e": {"3":[12,45,...], "7":[...]}}    # sigKeys 인덱스 → 발생일 인덱스 목록
  ]
}
날짜 배열은 담지 않는다(백테스트는 인덱스 i·i+h만 쓰므로). 결과 표시에
필요한 기간은 전역 date(최신일)와 첫 종목 상장길이로 대략 안내한다.

용량 관리: 시총 상위 CAP_LIMIT 종목만 담는다 (대형주에서 신호 신뢰도가
높다는 실험 결과 + 파일 크기 억제). 정렬은 종목 마스터의 시총 내림차순.
"""

import argparse
import datetime as dt
import json
import logging
import time

from batch import config
from batch.backtest.engine import HORIZONS
from batch.backtest.events import build_events
from batch.collector import backfill, master
from batch.indicators.core import compute_indicators

log = logging.getLogger("bt-dataset")

BT_DIR = config.OUTPUT_DIR / "bt"
CAP_LIMIT = 800          # 담을 종목 수 (시총 상위). 0=전 종목
MIN_ROWS = 250           # 이보다 짧은 종목 제외


def build(limit_stocks: int = CAP_LIMIT) -> dict:
    stocks = master.load_or_fetch_master(refresh=False)
    if limit_stocks:
        stocks = stocks.head(limit_stocks)

    # 시그널 키 집합을 먼저 확정 (첫 종목 기준으로 안정적 순서)
    sig_keys: list[str] = []
    sig_idx: dict[str, int] = {}

    out_stocks = []
    latest = ""
    for row in stocks.itertuples():
        ohlcv = backfill.load_cached(row.code)
        if ohlcv is None or len(ohlcv) < MIN_ROWS:
            continue
        ind = compute_indicators(ohlcv)
        events = build_events(ind)
        e_enc: dict[str, list[int]] = {}
        for k, idxs in events.items():
            if not idxs:
                continue
            if k not in sig_idx:
                sig_idx[k] = len(sig_keys)
                sig_keys.append(k)
            e_enc[str(sig_idx[k])] = [int(i) for i in idxs]

        out_stocks.append({
            "code": row.code,
            "name": row.name,
            "cap": int(getattr(row, "marcap", -1)),
            "c": [int(x) for x in ind["close"].tolist()],
            "e": e_enc,
        })
        latest = max(latest, ind["date"].iloc[-1])

    return {
        "date": latest,
        "horizons": HORIZONS,
        "sigKeys": sig_keys,
        "stocks": out_stocks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=CAP_LIMIT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.time()
    payload = build(args.limit)
    BT_DIR.mkdir(parents=True, exist_ok=True)
    path = BT_DIR / "dataset.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    mb = path.stat().st_size / 1024 / 1024
    log.info("백테스트 데이터셋: %d종목, %.1fMB (%.0f초)",
             len(payload["stocks"]), mb, time.time() - t0)


if __name__ == "__main__":
    main()
