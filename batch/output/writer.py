"""정적 JSON 산출: signals/latest.json + chart/{code}.json (v2: 일/주/월 타임프레임)"""

import json
import math

import pandas as pd

from batch import config
from batch.indicators.divergence import Divergence


def _round(v, nd=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    if nd == 0:
        return int(round(float(v)))
    return round(float(v), nd)


def stock_entry(
    code: str, name: str, ind: pd.DataFrame, sig: dict[str, int]
) -> dict:
    """latest.json의 stocks[] 한 건. sig = {시그널: 마지막 발생 N봉 전(0=오늘)}"""
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
        "sig": sig,
        "rsi": _round(last["rsi"], 1),
    }


def write_latest(date: str, stocks: list[dict]) -> None:
    config.SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"date": date, "stocks": stocks}
    (config.SIGNALS_DIR / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def timeframe_payload(
    ind: pd.DataFrame,
    events: list[Divergence],
    bars: int,
    patterns: list | None = None,  # 공통 인터페이스: kind/points/neckline/completed_at/forming
) -> dict:
    """한 타임프레임 분량의 차트 데이터. 최근 `bars`개 봉 + 다이버전스 마킹.

    지표값은 가격 축 스케일이라 정수로 반올림해 용량을 줄인다 (RSI만 소수 1자리).
    """
    tail = ind.iloc[-bars:].reset_index(drop=True)
    offset = len(ind) - len(tail)
    dates = tail["date"].tolist()

    def col(name_, nd=0):
        return [_round(v, nd) for v in tail[name_]]

    divs = []
    for e in events:
        i, j = e.idx_from - offset, e.idx_to - offset
        if i < 0:
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

    pats = []
    for p in patterns or []:
        pts = [(i - offset, price) for i, price in p.points]
        if pts[0][0] < 0:
            continue  # 차트 범위 밖에서 시작한 패턴 제외
        pats.append(
            {
                "kind": p.kind,
                "points": [[dates[i], round(float(v), 2)] for i, v in pts],
                "neckline": p.neckline,
                "completed_date": (
                    dates[p.completed_at - offset]
                    if p.completed_at is not None and p.completed_at - offset < len(dates)
                    else None
                ),
                "forming": p.forming,
            }
        )

    return {
        "dates": dates,
        "patterns": pats,
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


def write_chart(code: str, name: str, tf: dict[str, dict]) -> None:
    """종목 상세 차트 json v2. tf = {"d": payload, "w": payload, "m": payload}"""
    payload = {"code": code, "name": name, "tf": tf}
    config.CHART_DIR.mkdir(parents=True, exist_ok=True)
    (config.CHART_DIR / f"{code}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
