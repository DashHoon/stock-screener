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
    code: str, name: str, ind: pd.DataFrame, sig: dict[str, int],
    marcap: int = -1, market: str = "",
    industry: str = "", sector: str = "",
) -> dict:
    """latest.json의 stocks[] 한 건. sig = {시그널: 마지막 발생 N봉 전(0=오늘)}

    marcap: 시가총액(억원, -1=알 수 없음). market: 'KOSPI'|'KOSDAQ'
    """
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
        "cap": int(marcap),
        "mkt": market,
        "ind": industry,  # 통계청 업종명 (업종맵 2단계)
        "sec": sector,    # 투자자용 섹터 대분류 (업종맵 1단계)
        "sig": sig,
        "rsi": _round(last["rsi"], 1),
        "m": [int(x) for x in ind["close"].iloc[-20:]],  # 최근 20봉 스파크라인
    }


def write_latest(date: str, stocks: list[dict], indices: list[dict] | None = None) -> None:
    config.SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"date": date, "indices": indices or [], "stocks": stocks}
    (config.SIGNALS_DIR / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def timeframe_payload(
    ind: pd.DataFrame,
    events: list[Divergence],
    bars: int,
    patterns: list | None = None,  # 공통 인터페이스: kind/points/neckline/completed_at/forming
    candles: dict[str, list[int]] | None = None,  # 캔들 패턴 {kind: [발생 인덱스]}
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
        if not pts or pts[0][0] < 0:
            continue  # 차트 범위 밖에서 시작한 패턴 제외
        entry = {
            "kind": p.kind,
            "points": [[dates[i], round(float(v), 2)] for i, v in pts],
            "neckline": p.neckline,
            "grade": getattr(p, "grade", "B"),   # 형태 신뢰도 A/B/C
            "shape": int(getattr(p, "shape", 0)),
            "completed_date": (
                dates[p.completed_at - offset]
                if p.completed_at is not None and p.completed_at - offset < len(dates)
                else None
            ),
            "forming": p.forming,
        }
        pts2 = [
            (i - offset, price)
            for i, price in getattr(p, "points2", []) or []
            if i - offset >= 0
        ]
        if pts2:
            entry["points2"] = [[dates[i], round(float(v), 2)] for i, v in pts2]
        pats.append(entry)

    # 캔들 패턴: 차트 범위 내 발생일 목록 {kind: [date, ...]}
    cdl: dict[str, list[str]] = {}
    for kind, idxs in (candles or {}).items():
        ds = [dates[i - offset] for i in idxs if i - offset >= 0]
        if ds:
            cdl[kind] = ds

    out = {
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
    if cdl:
        out["candles"] = cdl
    return out


def archive_payload(ind: pd.DataFrame, before: str) -> dict | None:
    """`before`(YYYY-MM-DD) 이전 일봉 구간. 가격·거래량·RSI만 담는다.

    패턴·다이버전스·캔들 마킹은 최근분에만 싣는다 — 10년 구간에 다 그리면
    화면이 마커로 덮이고, 용량도 두 배가 된다.

    볼린저밴드(20일)·MACD도 뺀다. 10년을 한 화면에 놓으면 20일 밴드는 선 하나로
    뭉개져 읽을 수 없는데 용량은 전체의 40%를 차지한다 (415MB → 256MB).
    """
    old = ind[ind["date"].astype(str) < before]
    if len(old) < 30:
        return None

    def col(name_, nd=0):
        return [_round(v, nd) for v in old[name_]]

    return {
        "dates": old["date"].tolist(),
        "open": old["open"].tolist(),
        "high": old["high"].tolist(),
        "low": old["low"].tolist(),
        "close": old["close"].tolist(),
        "volume": old["volume"].tolist(),
        "rsi": col("rsi", 1),
    }


def write_chart_archive(code: str, payload: dict | None) -> bool:
    """일봉 아카이브 파일. 내용이 그대로면 다시 쓰지 않는다.

    아카이브는 확정된 과거라 대부분의 날에 한 글자도 안 바뀐다. 그대로 덮어써도
    git은 내용으로 판단해 새로 담지 않지만, 2,566개 파일을 매일 다시 쓰는 디스크·
    배포 비용은 남는다. 바뀐 종목(수정주가 조정 등)만 쓰도록 걸러낸다.
    """
    path = config.CHART_DIR / f"{code}.arc.json"
    if payload is None:
        return False
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if path.exists() and path.read_text(encoding="utf-8") == body:
        return False
    config.CHART_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return True


def write_chart(code: str, name: str, tf: dict[str, dict]) -> None:
    """종목 상세 차트 json v2. tf = {"d": payload, "w": payload, "m": payload}"""
    payload = {"code": code, "name": name, "tf": tf}
    config.CHART_DIR.mkdir(parents=True, exist_ok=True)
    (config.CHART_DIR / f"{code}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
