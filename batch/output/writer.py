"""정적 JSON 산출: signals/latest.json + chart/{code}.json"""

import json
import math

import pandas as pd

from batch import config
from batch.indicators.divergence import Divergence


def _round(v, nd=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(float(v), nd)


def stock_entry(
    code: str, name: str, ind: pd.DataFrame, flags: dict[str, bool]
) -> dict:
    """latest.json의 stocks[] 한 건."""
    last = ind.iloc[-1]
    prev_close = float(ind["close"].iloc[-2]) if len(ind) >= 2 else None
    change_pct = (
        _round((float(last["close"]) / prev_close - 1) * 100) if prev_close else None
    )
    return {
        "code": code,
        "name": name,
        "close": int(last["close"]),
        "change_pct": change_pct,
        "flags": flags,
        "rsi": _round(last["rsi"], 1),
    }


def write_latest(date: str, stocks: list[dict]) -> None:
    config.SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"date": date, "stocks": stocks}
    (config.SIGNALS_DIR / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_chart(
    code: str, name: str, ind: pd.DataFrame, events: list[Divergence]
) -> None:
    """종목 상세 차트용 json. 최근 CHART_DAYS 일 + 다이버전스 마킹."""
    tail = ind.iloc[-config.CHART_DAYS:].reset_index(drop=True)
    offset = len(ind) - len(tail)  # 이벤트 인덱스를 tail 기준으로 변환

    dates = tail["date"].tolist()

    def col(name_, nd=2):
        return [_round(v, nd) for v in tail[name_]]

    divs = []
    for e in events:
        i, j = e.idx_from - offset, e.idx_to - offset
        if i < 0:  # 차트 범위 밖에서 시작한 이벤트는 제외
            continue
        divs.append(
            {
                "kind": e.kind,
                "date_from": dates[i],
                "date_to": dates[j],
                "price_from": e.price_from,
                "price_to": e.price_to,
                "rsi_from": _round(e.rsi_from, 1),
                "rsi_to": _round(e.rsi_to, 1),
            }
        )

    payload = {
        "code": code,
        "name": name,
        "dates": dates,
        "open": tail["open"].tolist(),
        "high": tail["high"].tolist(),
        "low": tail["low"].tolist(),
        "close": tail["close"].tolist(),
        "volume": tail["volume"].tolist(),
        "rsi": col("rsi", 1),
        "macd": col("macd"),
        "macd_signal": col("macd_signal"),
        "macd_hist": col("macd_hist"),
        "bb_upper": col("bb_upper"),
        "bb_mid": col("bb_mid"),
        "bb_lower": col("bb_lower"),
        "divergences": divs,
    }
    config.CHART_DIR.mkdir(parents=True, exist_ok=True)
    (config.CHART_DIR / f"{code}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
