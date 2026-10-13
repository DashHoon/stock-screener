"""배포 전 산출물 검사 — 앱에서 보였던 실제 결함을 잡는지."""

import json

import pytest

from batch import audit

CAL = ["2026-10-01", "2026-10-02", "2026-10-06", "2026-10-07", "2026-10-08"]


def _series(dates, closes=None):
    c = closes or [100 + i for i in range(len(dates))]
    return {"dates": dates, "open": c, "high": [x + 1 for x in c], "low": [x - 1 for x in c], "close": c}


def _write(root, stocks=None, ks_dates=CAL, card_date="2026-10-08"):
    chart = root / "chart"
    (chart / "mini").mkdir(parents=True)
    (root / "signals").mkdir()
    for sym in ("KS11", "KQ11"):
        (chart / f"{sym}.json").write_text(json.dumps({"tf": {"d": _series(ks_dates)}}))
    entries = []
    for code, d in (stocks or {"005930": _series(CAL)}).items():
        (chart / f"{code}.json").write_text(json.dumps({"tf": {"d": d}}))
        (chart / "mini" / f"{code}.json").write_text(json.dumps({"c": d["close"][-3:]}))
        c = d["close"]
        entries.append({"code": code, "name": code, "close": c[-1],
                        "change_pct": round((c[-1] / c[-2] - 1) * 100, 2), "m": c[-3:]})
    (root / "signals" / "latest.json").write_text(json.dumps({
        "date": "2026-10-08",
        "indices": [{"code": s, "date": card_date} for s in ("KS11", "KQ11")],
        "stocks": entries,
    }))
    return root


def test_clean_output_passes(tmp_path):
    errors, warns, _ = audit.audit(_write(tmp_path))
    assert errors == [] and warns == []


def test_halt_day_hole_is_an_error(tmp_path):
    """2026-10 실제 결함: 거래정지일이 빠져 차트에 구멍 (190종목)."""
    holed = _series(["2026-10-01", "2026-10-07", "2026-10-08"])
    errors, _, _ = audit.audit(_write(tmp_path, {"412540": holed}))
    assert any("빠진 날 2개" in e for e in errors)


def test_stalled_index_is_an_error(tmp_path):
    """2026-10 실제 결함: 지수가 9/17에 멈춰 있었다."""
    errors, _, _ = audit.audit(_write(tmp_path, card_date="2026-09-17"))
    assert any("지수 카드" in e for e in errors)


def test_sparkline_mismatch_is_an_error(tmp_path):
    root = _write(tmp_path)
    p = root / "signals" / "latest.json"
    j = json.loads(p.read_text())
    j["stocks"][0]["close"] += 5     # 평일/주말 출처가 달라 값이 엇갈리던 경우
    p.write_text(json.dumps(j))
    errors, _, _ = audit.audit(root)
    assert any("latest 종가" in e for e in errors)


def test_limit_breaking_jump_is_only_a_warning(tmp_path):
    d = _series(CAL, [100, 100, 100, 100, 40])   # 정리매매 등
    errors, warns, _ = audit.audit(_write(tmp_path, {"005110": d}))
    assert errors == []
    assert len(warns) == 1


def test_main_exits_nonzero_on_error(tmp_path, monkeypatch):
    holed = _series(["2026-10-01", "2026-10-08"])
    root = _write(tmp_path, {"412540": holed})
    monkeypatch.setattr("sys.argv", ["audit", str(root)])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with pytest.raises(SystemExit):
        audit.main()
