"""배포 전 산출물 검사. 하나라도 어긋나면 종료 코드 1 — 워크플로가 배포를 건너뛴다.

2026-10-13 도입. 그때까지는 산출물을 검사하지 않아 문제가 앱 사용자 눈으로만
발견됐다: 지수가 3주 멈춰 있었고(9/17), 190종목 차트에 거래정지일 구멍이
있었고, 같은 날 가격이 평일(공공 API)과 주말(네이버 재백필)에 달랐다.
표본 몇 개를 보는 것으로는 못 잡는다 — 190종목은 60종목 표본에 하나도 안
걸렸다. 그래서 전 종목을 본다 (로컬에서 2초).

검사 (오류 = 배포 중단):
  - 지수 차트·카드가 latest.json 기준일에 끝나는가
  - 종목·업종 차트의 날짜가 거래일 달력과 한 칸도 어긋나지 않는가
    (첫 봉 이후 빠진 날·없는 날·기준일과 다른 마지막 날)
  - 봉이 성립하는가 (값 > 0, 저가 ≤ 시가·종가 ≤ 고가)
  - 같은 값이 파일마다 같은가 (latest.json 종가·등락률·스파크라인, 미니 차트)
경고 (배포는 진행):
  - 하루 ±30% 초과 변동 — 가격제한폭 밖이라 수정주가 누락일 수 있다
    (신규상장 첫날·정리매매는 정상적으로 걸린다)

사용: python -m batch.audit [산출 디렉터리]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from batch import config

LIMIT_PCT = 30.0


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _check_series(name: str, d: dict, cal: list[str], cal_pos: dict[str, int],
                  latest: str, errors: list[str], warns: list[str]) -> None:
    dates = d["dates"]
    if not dates:
        errors.append(f"{name}: 봉 없음")
        return
    if dates[-1] != latest:
        errors.append(f"{name}: 마지막 봉 {dates[-1]} ≠ 기준일 {latest}")
    start = cal_pos.get(dates[0])
    if start is None:
        # 차트 첫 봉이 달력보다 앞서면 달력 시작점부터 비교한다
        if dates[0] < cal[0]:
            dates = [x for x in dates if x >= cal[0]]
            start = 0
        else:
            errors.append(f"{name}: 거래일이 아닌 날 {dates[0]}")
            return
    expect = cal[start:start + len(dates)]
    if dates != expect:
        have = set(dates)
        miss = [x for x in cal[start:] if x <= latest and x not in have]
        extra = [x for x in dates if x not in cal_pos]
        errors.append(f"{name}: 빠진 날 {len(miss)}개 {miss[:3]} / 없는 날 {extra[:3]}")
        return
    o, h, lo, c = d["open"], d["high"], d["low"], d["close"]
    bad = [dates[i] for i in range(len(c))
           if min(o[i], h[i], lo[i], c[i]) <= 0 or lo[i] > min(o[i], c[i]) or h[i] < max(o[i], c[i])]
    if bad:
        errors.append(f"{name}: 성립하지 않는 봉 {len(bad)}개 {bad[:3]}")
    for i in range(1, len(c)):
        if c[i - 1] > 0 and abs(c[i] / c[i - 1] - 1) * 100 > LIMIT_PCT + 0.5:
            warns.append(f"{name}: {dates[i]} {c[i - 1]}→{c[i]} ({(c[i] / c[i - 1] - 1) * 100:+.0f}%)")


def audit(out_dir: Path) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warns: list[str] = []
    latest_json = _load(out_dir / "signals" / "latest.json")
    latest = latest_json["date"]
    chart_dir = out_dir / "chart"

    # 거래일 달력 = 코스피 지수 봉 날짜 (종목과 출처가 달라 교차 검증이 된다)
    ks = _load(chart_dir / "KS11.json")["tf"]["d"]
    cal = [x for x in ks["dates"] if x <= latest]
    cal_pos = {x: i for i, x in enumerate(cal)}
    for sym in ("KS11", "KQ11"):
        d = _load(chart_dir / f"{sym}.json")["tf"]["d"]
        if d["dates"][-1] != latest:
            errors.append(f"지수 {sym}: 마지막 봉 {d['dates'][-1]} ≠ 기준일 {latest}")
    cards = {i["code"]: i for i in latest_json.get("indices", [])}
    for sym in ("KS11", "KQ11"):
        card = cards.get(sym)
        if not card:
            errors.append(f"지수 카드 {sym} 없음")
        elif card.get("date") != latest:
            errors.append(f"지수 카드 {sym}: {card.get('date')} ≠ 기준일 {latest}")

    stocks = latest_json["stocks"]
    for s in stocks:
        code = s["code"]
        p = chart_dir / f"{code}.json"
        if not p.exists():
            errors.append(f"{code}: 차트 파일 없음")
            continue
        d = _load(p)["tf"]["d"]
        name = f"{code} {s.get('name', '')}"
        _check_series(name, d, cal, cal_pos, latest, errors, warns)
        c = d["close"]
        if s.get("close") != c[-1]:
            errors.append(f"{name}: latest 종가 {s.get('close')} ≠ 차트 {c[-1]}")
        if len(c) >= 2 and s.get("change_pct") is not None:
            if abs(s["change_pct"] - (c[-1] / c[-2] - 1) * 100) > 0.01:
                errors.append(f"{name}: 등락률 {s['change_pct']} ≠ 차트 기준")
        if s.get("m") and s["m"] != c[-len(s["m"]):]:
            errors.append(f"{name}: 스파크라인이 차트와 다름")
        mp = chart_dir / "mini" / f"{code}.json"
        if mp.exists():
            mc = _load(mp)["c"]
            if mc != c[-len(mc):]:
                errors.append(f"{name}: 미니 차트가 차트와 다름")
        else:
            errors.append(f"{name}: 미니 차트 없음")

    for p in sorted((chart_dir / "sector").glob("*.json")):
        _check_series(f"업종 {p.stem}", _load(p)["tf"]["d"], cal, cal_pos, latest, errors, warns)

    stats = {"date": latest, "stocks": len(stocks), "calendar_days": len(cal),
             "errors": len(errors), "warnings": len(warns)}
    return errors, warns, stats


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else config.OUTPUT_DIR
    errors, warns, stats = audit(out_dir)
    print(f"산출물 검사: {stats}")
    for e in errors[:50]:
        print("  [오류]", e)
    for w in warns[:20]:
        print("  [경고]", w)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### 산출물 검사 {stats['date']}\n\n"
                    f"- 종목 {stats['stocks']} · 거래일 {stats['calendar_days']}\n"
                    f"- 오류 {stats['errors']} · 경고 {stats['warnings']}\n\n")
            for e in errors[:50]:
                f.write(f"- ❌ {e}\n")
            for w in warns[:20]:
                f.write(f"- ⚠️ {w}\n")
    if errors:
        raise SystemExit(f"산출물 검사 실패 — 오류 {len(errors)}건, 배포하지 않는다")


if __name__ == "__main__":
    main()
