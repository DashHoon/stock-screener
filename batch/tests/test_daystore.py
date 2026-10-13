"""일자별 시세 저장소 — 수정주가 계산과 '빠진 날' 판정."""

import pandas as pd
import pytest

from batch import config
from batch.collector import daystore


def _rows(code, bars):
    """bars: [(date, close, base)] — 시·고·저는 종가와 같게."""
    return pd.DataFrame([
        {"code": code, "date": d, "open": c, "high": c, "low": c,
         "close": c, "volume": 1000, "base": b}
        for d, c, b in bars
    ])


CAL = {f"2026-05-{d:02d}": i for i, d in enumerate([4, 6, 7, 8, 11])}


def test_split_adjusts_prior_bars():
    """10:1 액면분할: 분할일 기준가가 전일 종가의 1/10 → 이전 봉 가격 ×0.1, 거래량 ×10."""
    g = _rows("001130", [("2026-05-04", 156000, 155000), ("2026-05-06", 156500, 156000),
                         ("2026-05-07", 15800, 15650), ("2026-05-08", 16000, 15800)])
    out = daystore.adjust(g, CAL)
    assert out["close"].tolist() == [15600, 15650, 15800, 16000]
    assert out["volume"].tolist() == [10000, 10000, 1000, 1000]
    assert "base" not in out


def test_two_events_compound():
    """병합 2:1 뒤 다시 분할 1:5 — 가장 오래된 봉엔 두 비율이 모두 곱해진다."""
    g = _rows("X", [("2026-05-04", 1000, 1000), ("2026-05-06", 2100, 2000),
                    ("2026-05-07", 420, 420), ("2026-05-08", 430, 420)])
    out = daystore.adjust(g, CAL)
    assert out["close"].tolist() == [400, 420, 420, 430]


def test_tick_rounding_is_not_an_event():
    """기준가가 호가 단위만큼만 다른 것(스팩 2302→2305)은 보정하지 않는다."""
    g = _rows("SPAC", [("2026-05-04", 2302, 2300), ("2026-05-06", 2305, 2305)])
    assert daystore.adjust(g, CAL)["close"].tolist() == [2302, 2305]


def test_no_adjustment_across_missing_row():
    """전일 행이 바로 앞 거래일이 아니면 비교 대상이 틀리므로 보정하지 않는다."""
    g = _rows("X", [("2026-05-04", 1000, 1000), ("2026-05-08", 500, 900)])
    assert daystore.adjust(g, CAL)["close"].tolist() == [1000, 500]


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(daystore, "DAY_DIR", tmp_path / "days")
    monkeypatch.setattr(daystore, "NO_TRADE_PATH", tmp_path / "no_trade.json")
    monkeypatch.setattr(config, "OHLCV_CACHE_DIR", tmp_path / "ohlcv")
    return tmp_path


def _fake_fetch(available):
    def fetch(bas_dt, *a, **k):
        d = f"{bas_dt[:4]}-{bas_dt[4:6]}-{bas_dt[6:]}"
        if d not in available:
            return pd.DataFrame()
        return _rows("005930", [(d, 100, 100)])
    return fetch


def test_sync_flags_missing_past_day_as_gap(store, monkeypatch):
    """지난 거래일이 공급처에 없으면 gap — 호출부가 배포를 막는다."""
    cal = ["2026-05-04", "2026-05-06", "2026-05-07", "2026-05-08"]
    monkeypatch.setattr(daystore, "market_calendar", lambda: cal)
    monkeypatch.setattr(daystore.daily, "fetch_day", _fake_fetch({"2026-05-04", "2026-05-07", "2026-05-08"}))
    res = daystore.sync(history_bars=4)
    assert res.latest == "2026-05-08"
    assert res.gaps == ["2026-05-06"]


def test_sync_treats_unpublished_tail_as_pending(store, monkeypatch):
    """아직 안 올라온 최근 날은 정상 대기 — 구멍이 아니다."""
    cal = ["2026-05-04", "2026-05-06", "2026-05-07", "2026-05-08"]
    monkeypatch.setattr(daystore, "market_calendar", lambda: cal)
    monkeypatch.setattr(daystore.daily, "fetch_day", _fake_fetch({"2026-05-04", "2026-05-06"}))
    res = daystore.sync(history_bars=4)
    assert res.latest == "2026-05-06"
    assert res.gaps == []
    assert res.pending == ["2026-05-07", "2026-05-08"]


def test_build_cache_writes_every_code_and_drops_vanished(store, monkeypatch):
    cal = ["2026-05-04", "2026-05-06"]
    monkeypatch.setattr(daystore, "market_calendar", lambda: cal)
    monkeypatch.setattr(daystore.daily, "fetch_day", _fake_fetch(set(cal)))
    daystore.sync(history_bars=2)
    (store / "ohlcv").mkdir()
    pd.DataFrame().to_parquet(store / "ohlcv" / "DELIST.parquet")
    assert daystore.build_cache() == 1
    assert sorted(p.stem for p in (store / "ohlcv").glob("*.parquet")) == ["005930"]
    got = pd.read_parquet(store / "ohlcv" / "005930.parquet")
    assert got["date"].tolist() == cal


def test_sync_reports_incomplete_when_portal_keeps_failing(store, monkeypatch):
    """연속 실패로 멈추면 complete=False — 앞쪽만 받은 데이터로 배포하지 않게."""
    cal = [f"2026-05-{d:02d}" for d in (4, 6, 7, 8, 11, 12)]
    monkeypatch.setattr(daystore, "market_calendar", lambda: cal)
    ok = _fake_fetch(set(cal))

    def flaky(bas_dt, *a, **k):
        if bas_dt >= "20260507":
            raise ConnectionError("portal down")
        return ok(bas_dt)

    monkeypatch.setattr(daystore.daily, "fetch_day", flaky)
    res = daystore.sync(history_bars=6)
    assert res.complete is False
    assert res.latest == "2026-05-06"
