"""백테스트 엔진: 전략(trigger → confirm → hold) 매칭과 성과 집계.

전략 정의 형식 (strategies.py 참고):
{
  "id": "div-then-golden",
  "name": "상승 다이버전스 → 골든크로스 확인",
  "trigger": "div_reg_bull",
  "when": [["macd", "<", 0]],        # (선택) trigger 당일 지표 조건 (AND)
  "confirm": {                       # 없으면 trigger 당일 진입
      "event": "macd_golden",
      "within_days": 10,             # trigger 다음날부터 N거래일 안
      "when": [["rsi", ">=", 40]],   # 확인일 지표 조건 (AND)
  },
  "desc": "...",
}

진입은 신호 확정일 종가. 성과는 진입 후 H거래일 종가 수익률.
같은 종목에서 진입 후 최소 보유기간(HOLD 최댓값)이 지나기 전의 중복 신호는
독립 표본이 아니므로 건너뛴다 (표본 부풀리기 방지).
"""

import statistics
from typing import Any

import pandas as pd

HORIZONS = [5, 10, 20, 60]

OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def _check_when(ind: pd.DataFrame, i: int, conds: list[list]) -> bool:
    for col, op, value in conds:
        v = ind[col].iloc[i]
        if pd.isna(v) or not OPS[op](float(v), float(value)):
            return False
    return True


def find_entries(
    ind: pd.DataFrame, events: dict[str, list[int]], strategy: dict[str, Any]
) -> list[int]:
    """전략에 맞는 진입 인덱스 목록 (중복 신호 억제 포함)."""
    triggers = events.get(strategy["trigger"], [])
    trig_when = strategy.get("when") or []
    if trig_when:
        triggers = [t for t in triggers if _check_when(ind, t, trig_when)]
    confirm = strategy.get("confirm")
    entries: list[int] = []
    min_gap = max(HORIZONS)
    last_entry = -(10**9)

    if confirm is None:
        candidates = triggers
    else:
        confirm_set = events.get(confirm["event"], [])
        candidates = []
        for t in triggers:
            # trigger 다음날부터 within_days 안의 첫 확인 이벤트
            for c in confirm_set:
                if c <= t:
                    continue
                if c - t > confirm["within_days"]:
                    break
                if _check_when(ind, c, confirm.get("when", [])):
                    candidates.append(c)
                break  # 기한 내 첫 확인 이벤트만 본다 (조건 불충족 시 그 트리거는 버림)

    for i in sorted(set(candidates)):
        if i - last_entry < min_gap:
            continue
        entries.append(i)
        last_entry = i
    return entries


def measure(ind: pd.DataFrame, entries: list[int]) -> dict[int, list[float]]:
    """진입 인덱스별 H거래일 후 수익률(%) 수집."""
    close = ind["close"].astype(float).to_numpy()
    out: dict[int, list[float]] = {h: [] for h in HORIZONS}
    n = len(close)
    for i in entries:
        for h in HORIZONS:
            j = i + h
            if j < n and close[i] > 0:
                out[h].append((close[j] / close[i] - 1) * 100)
    return out


def aggregate(samples: dict[int, list[float]]) -> dict[str, Any]:
    """호라이즌별 표본 → 승률/평균/중앙값 통계."""
    result: dict[str, Any] = {}
    for h, rets in samples.items():
        if not rets:
            result[str(h)] = None
            continue
        wins = sum(1 for r in rets if r > 0)
        result[str(h)] = {
            "n": len(rets),
            "win": round(wins / len(rets) * 100, 1),
            "mean": round(statistics.fmean(rets), 2),
            "median": round(statistics.median(rets), 2),
        }
    return result


def merge_samples(
    total: dict[int, list[float]], part: dict[int, list[float]]
) -> None:
    for h in HORIZONS:
        total[h].extend(part[h])
