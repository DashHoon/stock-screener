"""매크로 지표 수집 — 금리·물가·경기·달러/유동성.

출처는 FRED(미 세인트루이스 연준)와 FinanceDataReader의 환율이다.
FRED는 미 연준의 공개 데이터라 이용 제약이 없다 (KRX·네이버와 다른 점).
API 키도 필요 없다.

**한국 물가·통화량은 여기 없다.** FRED의 한국 계열은 실측 결과 CPI가
2023-11, M2가 2017-05에서 멈춰 있고 기준금리 값은 아예 틀렸다.
국내 물가·통화량은 한국은행 ECOS API가 필요하고 키 발급이 사용자 몫이다.

금리는 주가와 성격이 다르다:
- 시가·고가·저가가 없다. 종가 하나뿐이라 캔들이 아니라 라인이다
- 패턴 탐지를 붙이지 않는다. 쌍바닥·플래그는 수급과 심리가 만드는 형태인데
  국채 금리는 연준 정책과 물가가 움직인다. 그림은 그려지지만 뜻이 없다
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

import pandas as pd

from batch import config

log = logging.getLogger("batch.macro")

YEARS = 10          # 받아 둘 기간
RETRIES = 3
BACKOFF = 4         # 초. 4 → 8 → 16


@dataclass(frozen=True)
class Series:
    key: str          # 파일명·앱에서 쓰는 키
    code: str         # FinanceDataReader 코드
    name: str         # 화면에 보이는 이름
    unit: str         # 단위 표기 ('%', '원', 'pt' …)
    topics: tuple[str, ...]   # 어느 주제에 실을지
    note: str = ""    # 한 줄 설명 (앱의 ⓘ가 쓴다)
    decimals: int = 2


# 주제 4개. 장단기 금리차는 금리와 경기 양쪽에 넣는다 — 같은 값이지만
# 보는 이유가 다르다(금리에서는 곡선 모양, 경기에서는 침체 신호).
TOPICS = {
    "rate": "금리",
    "inflation": "인플레이션",
    "economy": "경기",
    "dollar": "달러와 유동성",
}

SERIES: list[Series] = [
    # ── 금리 ────────────────────────────────────────────
    Series("ust2y", "FRED:DGS2", "미국채 2년", "%", ("rate",),
           "연준이 앞으로 몇 년 안에 금리를 어떻게 할지에 대한 시장의 예상이 가장 빨리 반영되는 만기."),
    Series("ust10y", "FRED:DGS10", "미국채 10년", "%", ("rate",),
           "장기 자금의 값. 주식 가치를 계산할 때 미래 이익을 할인하는 기준으로 쓰여서, 오르면 성장주가 먼저 눌린다."),
    Series("spread10_2", "FRED:T10Y2Y", "장단기 금리차 (10년-2년)", "%p",
           ("rate", "economy"),
           "10년 금리에서 2년 금리를 뺀 값. 마이너스(역전)는 과거 미국 침체에 앞서 나타난 적이 많아 경기 신호로 널리 쓰인다."),
    Series("fedfunds", "FRED:DFF", "연방기금금리", "%", ("rate",),
           "연준이 실제로 적용하는 하루짜리 정책금리. 기대가 아니라 현재 상태를 보여준다."),
    # ── 인플레이션 ──────────────────────────────────────
    Series("breakeven10y", "FRED:T10YIE", "기대 인플레이션 10년", "%", ("inflation",),
           "물가연동국채와 일반국채의 금리 차이. 앞으로 10년 물가가 연 몇 %일지에 대한 시장의 값이다. 발표를 기다리지 않고 매일 볼 수 있다."),
    Series("forward5y5y", "FRED:T5YIFR", "5년 후 5년 기대 인플레", "%", ("inflation",),
           "지금부터 5년 뒤의 5년간 기대 물가. 당장의 유가 등락에 덜 흔들려 장기 기대를 본다."),
    Series("wti", "FRED:DCOILWTICO", "WTI 유가", "$", ("inflation",),
           "원유 가격. 운송·화학 원가를 통해 물가로 옮겨 가는 데 몇 달 걸린다."),
    Series("cpi_us", "FRED:CPIAUCSL", "미국 소비자물가지수", "pt", ("inflation",),
           "실제 발표된 물가. 월 1회라 느리지만 기대가 아니라 사실이다.", 1),
    # ── 경기 ───────────────────────────────────────────
    Series("hy_spread", "FRED:BAMLH0A0HYM2", "하이일드 스프레드", "%p", ("economy",),
           "신용등급이 낮은 회사가 국채보다 얼마나 더 높은 이자를 물어야 하는지. 벌어지면 시장이 부도 위험을 크게 본다는 뜻이다."),
    Series("vix", "FRED:VIXCLS", "VIX (공포지수)", "pt", ("economy",),
           "S&P500 옵션에 반영된 향후 30일 변동성 기대치. 급등은 시장이 겁먹었다는 표시다."),
    Series("unemp_us", "FRED:UNRATE", "미국 실업률", "%", ("economy",),
           "고용은 경기를 뒤늦게 따라오는 지표다. 나빠진 게 확인될 때는 이미 진행된 뒤인 경우가 많다.", 1),
    # ── 달러와 유동성 ───────────────────────────────────
    Series("usdkrw", "USD/KRW", "원/달러 환율", "원", ("dollar",),
           "오르면 원화가 약해졌다는 뜻. 외국인이 국내 주식을 팔 유인이 커지고, 수출 기업에는 유리하게 작용한다.", 1),
    Series("dxy", "FRED:DTWEXBGS", "달러 인덱스 (광의)", "pt", ("dollar",),
           "주요 교역상대 통화 대비 달러의 값. 달러가 강해지면 신흥국에서 자금이 빠지는 경향이 있다."),
    Series("fed_assets", "FRED:WALCL", "연준 총자산", "조$", ("dollar",),
           "연준이 들고 있는 자산 규모. 늘면 시장에 돈을 푼 것, 줄면 거둬들인 것으로 본다. 주 1회 발표.", 2),
    # 조$로 바꾸면 최근처럼 잔액이 줄었을 때 0.00으로 뭉개진다. 십억$ 그대로 둔다.
    Series("reverse_repo", "FRED:RRPONTSYD", "역레포 잔액", "십억$", ("dollar",),
           "금융기관이 하루 동안 연준에 맡겨 둔 돈. 갈 곳 없는 유동성이 얼마나 되는지를 보여준다.", 1),
]

BY_KEY = {s.key: s for s in SERIES}


def _fetch(code: str, start: str) -> pd.DataFrame | None:
    """FinanceDataReader로 한 계열. 실패하면 물러섰다 다시."""
    import FinanceDataReader as fdr

    for attempt in range(RETRIES):
        try:
            df = fdr.DataReader(code, start)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:  # noqa: BLE001 — 어떤 실패든 재시도 대상
            wait = BACKOFF * (2**attempt)
            log.warning("%s 수집 실패(%s) — %d초 후 재시도", code, e, wait)
            if attempt < RETRIES - 1:
                time.sleep(wait)
    return None


def _payload(s: Series, df: pd.DataFrame) -> dict:
    """계열 하나를 앱이 읽을 형태로. 값이 비는 날은 통째로 뺀다 —
    휴일·발표 없는 날이라 선을 이어 그리는 게 맞다."""
    col = df.columns[0]
    ser = df[col].astype(float).dropna()
    # 연준 총자산·역레포는 백만·십억 단위라 그대로 두면 자릿수를 읽을 수 없다.
    if s.key == "fed_assets":
        ser = ser / 1_000_000      # 백만$ → 조$

    dates = [d.strftime("%Y-%m-%d") for d in ser.index]
    values = [round(float(v), s.decimals) for v in ser.to_numpy()]
    last = values[-1] if values else None
    prev = values[-2] if len(values) >= 2 else None
    return {
        "key": s.key,
        "name": s.name,
        "unit": s.unit,
        "note": s.note,
        "topics": list(s.topics),
        "decimals": s.decimals,
        "date": dates[-1] if dates else None,
        "last": last,
        "change": None if last is None or prev is None else round(last - prev, s.decimals),
        "dates": dates,
        "values": values,
    }


def run() -> dict:
    """전 계열 수집 → macro/{key}.json + macro/latest.json"""
    out_dir = config.OUTPUT_DIR / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)
    start = (pd.Timestamp.today() - pd.DateOffset(years=YEARS)).strftime("%Y-%m-%d")

    summary: list[dict] = []
    failed: list[str] = []
    for s in SERIES:
        df = _fetch(s.code, start)
        if df is None:
            # 한 계열이 막혀도 나머지는 낸다. 화면에서 그 항목만 빠진다.
            failed.append(s.key)
            log.warning("%s(%s) 건너뜀", s.key, s.code)
            continue
        p = _payload(s, df)
        (out_dir / f"{s.key}.json").write_text(
            json.dumps(p, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        # latest에는 시계열을 빼고 오늘 값만 — 목록 화면이 파일 하나만 받게.
        summary.append({k: v for k, v in p.items() if k not in ("dates", "values")})

    (out_dir / "latest.json").write_text(
        json.dumps(
            {"topics": TOPICS, "series": summary},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    log.info("매크로 %d계열 산출 (실패 %d)", len(summary), len(failed))
    return {"written": len(summary), "failed": failed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    print(run())
