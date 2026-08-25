"""매크로 지표 수집 — 금리·물가·경기·달러/유동성.

출처는 셋이다:
- FRED(미 세인트루이스 연준) — 미국 금리·물가·경기. 공개 데이터라 키가 필요 없다
- FinanceDataReader — 원/달러 환율
- 한국은행 ECOS — 국내 기준금리·국고채·물가·통화량 (ECOS_API_KEY 필요)

FRED의 한국 계열은 쓰지 않는다. 실측 결과 CPI가 2023-11, M2가 2017-05에서
멈춰 있고 기준금리 값은 아예 틀렸다. 그래서 국내 지표는 ECOS에서 직접 받는다
(2026-08-25 도입).

ECOS 키가 없으면 국내 계열만 조용히 빠지고 나머지는 그대로 나간다 — 키를
아직 안 넣은 환경에서도 배치가 멈추지 않게 하려는 것이다.

금리는 주가와 성격이 다르다:
- 시가·고가·저가가 없다. 종가 하나뿐이라 캔들이 아니라 라인이다
- 패턴 탐지를 붙이지 않는다. 쌍바닥·플래그는 수급과 심리가 만드는 형태인데
  국채 금리는 연준 정책과 물가가 움직인다. 그림은 그려지지만 뜻이 없다
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

import pandas as pd

from batch import config

log = logging.getLogger("batch.macro")

YEARS = 10          # 받아 둘 기간
RETRIES = 3
BACKOFF = 4         # 초. 4 → 8 → 16
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"
ECOS_MAX_ROWS = 10000   # 일별 10년치도 3천 건 미만이라 한 번에 받는다


@dataclass(frozen=True)
class Series:
    key: str          # 파일명·앱에서 쓰는 키
    code: str         # 수집 주소. 'FRED:…'·'USD/KRW'는 FinanceDataReader,
                      # 'ECOS:{통계표}/{주기}/{항목}'은 한국은행 ECOS
    name: str         # 화면에 보이는 이름
    unit: str         # 단위 표기 ('%', '원', 'pt' …)
    topics: tuple[str, ...]   # 어느 주제에 실을지
    note: str = ""    # 한 줄 설명 (앱의 ⓘ가 쓴다)
    decimals: int = 2
    # 'yoy'면 전년동월비 상승률(%)로 바꾼다. 지수·잔액은 수준을 봐도 읽히지 않고
    # (물가지수 119.77이 몇 %인지 알 수 없다) 뉴스에 나오는 숫자도 상승률이다.
    transform: str = ""


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
    # 국내 계열을 앞에 둔다. 국내 주식을 보는 앱인데 미국채를 넷 지나야
    # 기준금리가 나오면 순서가 거꾸로다.
    Series("kr_base", "ECOS:722Y001/D/0101000", "한국은행 기준금리", "%", ("rate",),
           "한국은행 금융통화위원회가 정하는 정책금리. 예금·대출 금리와 채권 금리가 모두 여기서 출발한다."),
    Series("kr_ktb3y", "ECOS:817Y002/D/010200000", "국고채 3년", "%", ("rate",),
           "국내 채권시장의 기준. 기준금리가 앞으로 어떻게 될지에 대한 시장의 예상이 먼저 반영된다."),
    Series("kr_ktb10y", "ECOS:817Y002/D/010210000", "국고채 10년", "%", ("rate",),
           "국내 장기 금리. 3년물보다 높으면 정상, 낮으면(역전) 시장이 경기 둔화를 보고 있다는 뜻으로 읽는다."),
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
    Series("kr_cpi", "ECOS:901Y009/M/0", "한국 소비자물가 상승률", "%", ("inflation",),
           "통계청이 발표하는 소비자물가지수의 전년 같은 달 대비 상승률. 한국은행이 목표(2%)로 삼는 숫자이고, "
           "기준금리를 올릴지 내릴지의 근거가 된다. 월 1회 발표라 한 달쯤 늦게 반영된다.",
           1, "yoy"),
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
    Series("kr_m2", "ECOS:161Y005/M/BBHS00", "한국 M2 증가율", "%", ("dollar",),
           "시중에 도는 돈(현금·예금·수익증권 등)이 1년 전보다 얼마나 늘었는지. 늘어난 돈의 일부가 "
           "자산으로 흘러 들어가므로 유동성을 가늠하는 데 쓴다. 두 달쯤 늦게 발표된다.",
           1, "yoy"),
    Series("dxy", "FRED:DTWEXBGS", "달러 인덱스 (광의)", "pt", ("dollar",),
           "주요 교역상대 통화 대비 달러의 값. 달러가 강해지면 신흥국에서 자금이 빠지는 경향이 있다."),
    Series("fed_assets", "FRED:WALCL", "연준 총자산", "조$", ("dollar",),
           "연준이 들고 있는 자산 규모. 늘면 시장에 돈을 푼 것, 줄면 거둬들인 것으로 본다. 주 1회 발표.", 2),
    # 조$로 바꾸면 최근처럼 잔액이 줄었을 때 0.00으로 뭉개진다. 십억$ 그대로 둔다.
    Series("reverse_repo", "FRED:RRPONTSYD", "역레포 잔액", "십억$", ("dollar",),
           "금융기관이 하루 동안 연준에 맡겨 둔 돈. 갈 곳 없는 유동성이 얼마나 되는지를 보여준다.", 1),
]

BY_KEY = {s.key: s for s in SERIES}


def _ecos_key() -> str | None:
    return os.environ.get("ECOS_API_KEY") or None


def _fetch_ecos(spec: str, start: str) -> pd.DataFrame | None:
    """ECOS로 한 계열. spec은 '{통계표}/{주기}/{항목}'.

    ECOS는 주기에 따라 기간 표기가 다르다 (일별 YYYYMMDD, 월별 YYYYMM).
    응답의 DATA_VALUE는 문자열이고 결측이 빈 문자열로 오므로 숫자로 못 바꾸는
    행은 버린다.
    """
    import requests

    key = _ecos_key()
    if not key:
        return None
    try:
        stat, cycle, item = spec.split("/")
    except ValueError:
        log.warning("ECOS 코드 형식이 잘못됐다: %s", spec)
        return None

    s = pd.Timestamp(start)
    end = pd.Timestamp.today()
    fmt = "%Y%m%d" if cycle == "D" else "%Y%m"
    url = (f"{ECOS_BASE}/{key}/json/kr/1/{ECOS_MAX_ROWS}/{stat}/{cycle}"
           f"/{s.strftime(fmt)}/{end.strftime(fmt)}/{item}")

    for attempt in range(RETRIES):
        try:
            res = requests.get(url, timeout=30)
            res.raise_for_status()
            body = res.json()
            if "RESULT" in body:   # ECOS는 오류도 200으로 준다
                # 키가 틀렸거나 데이터가 없는 것 — 재시도해도 같다
                log.warning("ECOS %s 응답: %s", spec, body["RESULT"].get("MESSAGE"))
                return None
            rows = body.get("StatisticSearch", {}).get("row") or []
            recs = []
            for r in rows:
                v = (r.get("DATA_VALUE") or "").strip()
                if not v:
                    continue
                try:
                    recs.append((r["TIME"], float(v)))
                except ValueError:
                    continue
            if not recs:
                return None
            idx = pd.to_datetime([x[0] for x in recs], format=fmt)
            df = pd.DataFrame({"value": [x[1] for x in recs]}, index=idx).sort_index()
            if cycle == "D":
                # ECOS 일별은 주말·휴일에도 직전 값을 그대로 채워 준다. 기준금리가
                # 10년에 3,650점이 되는데, 앱은 계열 종류와 무관하게 최근 500점을
                # 그리므로 이 계열만 창이 1.4년으로 짧아진다. 주말을 빼서 다른 금리
                # 계열(영업일 기준)과 창을 맞춘다. 주말 값은 직전 영업일의 복사라
                # 버려도 잃는 정보가 없다.
                df = df[df.index.dayofweek < 5]
            return df
        except Exception as e:  # noqa: BLE001 — 어떤 실패든 재시도 대상
            wait = BACKOFF * (2**attempt)
            log.warning("ECOS %s 수집 실패(%s) — %d초 후 재시도", spec, e, wait)
            if attempt < RETRIES - 1:
                time.sleep(wait)
    return None


def _fetch(code: str, start: str) -> pd.DataFrame | None:
    """계열 하나. 코드 접두사로 출처를 가른다."""
    if code.startswith("ECOS:"):
        return _fetch_ecos(code[5:], start)

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
    if s.transform == "yoy":
        # 월별 계열 전용. 12칸 전과 비교하되 '12행 전'이 아니라 '12개월 전'으로
        # 찾는다 — 중간에 결측이 있으면 행 간격과 개월 수가 어긋난다.
        by_month = {d.strftime("%Y-%m"): v for d, v in ser.items()}
        pairs = []
        for d, v in ser.items():
            ago = by_month.get((d - pd.DateOffset(years=1)).strftime("%Y-%m"))
            if ago:
                pairs.append((d, (v / ago - 1) * 100))
        if not pairs:
            return {}
        ser = pd.Series([v for _, v in pairs], index=[d for d, _ in pairs])

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

    series = SERIES
    if not _ecos_key():
        # 키를 안 넣은 환경(예: 시크릿 등록 전)에서는 국내 계열만 빼고 돌린다.
        # 계열마다 실패 경고를 다섯 번 찍는 것보다 한 번 알려 주는 게 낫다.
        skipped = [s.key for s in SERIES if s.code.startswith("ECOS:")]
        log.warning("ECOS_API_KEY 없음 — 국내 계열 %d개 건너뜀 (%s)",
                    len(skipped), ", ".join(skipped))
        series = [s for s in SERIES if not s.code.startswith("ECOS:")]

    summary: list[dict] = []
    failed: list[str] = []
    for s in series:
        df = _fetch(s.code, start)
        if df is None:
            # 한 계열이 막혀도 나머지는 낸다. 화면에서 그 항목만 빠진다.
            failed.append(s.key)
            log.warning("%s(%s) 건너뜀", s.key, s.code)
            continue
        p = _payload(s, df)
        if not p:
            failed.append(s.key)
            log.warning("%s 값이 비어 건너뜀", s.key)
            continue
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
    # 단독 실행(배포 스크립트가 이렇게 부른다)에서도 .env의 ECOS_API_KEY를 읽어야
    # 한다. batch.run은 자기 안에서 부르지만 이쪽은 별도 진입점이다.
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    print(run())
