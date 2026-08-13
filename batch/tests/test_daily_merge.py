"""일별 병합의 급변 감지(수정주가 의심) 로직 검증."""

import pandas as pd
import requests
import pytest

from batch import config
from batch.collector import backfill, daily


def test_is_discontinuous_threshold():
    # 임계치(25%) 미만의 정상 변동
    assert not daily.is_discontinuous(10000, 10500)   # +5%
    assert not daily.is_discontinuous(10000, 7600)    # -24%
    # 임계치 이상 = 기업행위 의심
    assert daily.is_discontinuous(10000, 7000)        # -30% (권리락 규모)
    assert daily.is_discontinuous(10000, 2000)        # -80% (액면분할 규모)
    assert daily.is_discontinuous(10000, 20000)       # +100% (병합 규모)
    # 방어: 이전 종가가 0 이하
    assert not daily.is_discontinuous(0, 10000)


def _make_cache(tmp_path, code, closes):
    df = pd.DataFrame(
        {
            "date": [f"2026-07-{d:02d}" for d in range(1, len(closes) + 1)],
            "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [1000] * len(closes),
        }
    )
    df.to_parquet(tmp_path / f"{code}.parquet", index=False)
    return df


def _day_row(code, close):
    return {
        "code": code, "date": "2026-07-20",
        "open": close, "high": close, "low": close,
        "close": close, "volume": 500,
    }


def test_merge_normal_and_rebuild_suspect(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OHLCV_CACHE_DIR", tmp_path)
    _make_cache(tmp_path, "AAA111", [100, 101, 102])   # 정상: 102 → 105
    _make_cache(tmp_path, "BBB222", [10000] * 3)       # 급변: 10000 → 6400 (-36%)

    rebuilt = []
    monkeypatch.setattr(backfill, "rebuild_one", lambda code: rebuilt.append(code) or 1)

    day = pd.DataFrame([_day_row("AAA111", 105), _day_row("BBB222", 6400)])
    updated = daily.merge_into_cache(day)

    # 정상 종목은 병합됨
    assert updated == 1
    merged = pd.read_parquet(tmp_path / "AAA111.parquet")
    assert merged["close"].iloc[-1] == 105 and len(merged) == 4

    # 급변 종목은 병합하지 않고 재구축 호출
    assert rebuilt == ["BBB222"]
    untouched = pd.read_parquet(tmp_path / "BBB222.parquet")
    assert len(untouched) == 3  # rebuild_one을 모킹했으므로 원본 그대로


def test_merge_skips_stale_date(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OHLCV_CACHE_DIR", tmp_path)
    df = _make_cache(tmp_path, "CCC333", [100, 101])
    # 캐시 마지막 날짜(07-02)보다 과거인 데이터는 무시
    day = pd.DataFrame([{**_day_row("CCC333", 999), "date": "2026-07-01"}])
    assert daily.merge_into_cache(day) == 0
    assert pd.read_parquet(tmp_path / "CCC333.parquet").equals(df)


def test_rebuild_one_preserves_cache_on_empty_fetch(tmp_path, monkeypatch):
    """수신 실패 시 기존 캐시를 지우지 않는다."""
    monkeypatch.setattr(config, "OHLCV_CACHE_DIR", tmp_path)
    df = _make_cache(tmp_path, "DDD444", [100, 101])

    import FinanceDataReader as fdr
    monkeypatch.setattr(fdr, "DataReader", lambda *a, **k: pd.DataFrame())

    assert backfill.rebuild_one("DDD444") == 0
    assert pd.read_parquet(tmp_path / "DDD444.parquet").equals(df)


class _FakeResp:
    def __init__(self, items):
        self._items = items

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "response": {
                "body": {
                    "totalCount": len(self._items),
                    "items": {"item": self._items},
                }
            }
        }


def _item(code, name, o, h, l, c, vol):
    return {"srtnCd": code, "itmsNm": name, "basDt": "20260805",
            "mkp": str(o), "hipr": str(h), "lopr": str(l),
            "clpr": str(c), "trqu": str(vol)}


def test_fetch_day_keeps_no_trade_rows(monkeypatch):
    """거래 없는 날(시·고·저가 0)도 종가로 채워 수집한다.

    공공 API는 그날 거래가 없으면 시/고/저를 0으로, 종가만 전일값으로 준다.
    예전에는 이 행을 통째로 버려 해당 종목이 갱신되지 않았다 — 2026-08-05 기준
    146종목(한화·드림어스컴퍼니 등)이 여기 걸렸고, fdr(네이버)이 뒤에서 메워
    드러나지 않다가 네이버 경로를 걷어내면서 표면화됐다.
    """
    items = [
        _item("005930", "삼성전자", 254000, 254500, 244000, 246000, 22577128),
        _item("000880", "한화", 0, 0, 0, 83800, 0),        # 거래 없음
        _item("999999", "상장폐지", 0, 0, 0, 0, 0),          # 종가까지 0 → 버린다
    ]
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "dummy")
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: _FakeResp(items))

    df = daily.fetch_day("20260805")
    got = {r["code"]: r for r in df.to_dict("records")}

    assert set(got) == {"005930", "000880"}, "종가까지 0인 행만 버려야 한다"
    hanwha = got["000880"]
    assert hanwha["open"] == hanwha["high"] == hanwha["low"] == 83800
    assert hanwha["volume"] == 0
    assert got["005930"]["open"] == 254000  # 정상 거래일은 그대로


def test_fetch_day_retries_on_connection_error(monkeypatch):
    """접속 실패는 물러서며 재시도한다.

    2026-08-13 #63·#64가 여기서 죽었다. 포털이 간헐적으로 접속을 안 받는데
    재시도가 없어 한 번 끊길 때마다 배치 전체가 exit 1로 끝났다.
    """
    calls = {"n": 0}
    items = [_item("005930", "삼성전자", 100, 110, 90, 105, 1000)]

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:               # 두 번 끊기고 세 번째에 성공
            raise requests.ConnectTimeout("timed out")
        return _FakeResp(items)

    monkeypatch.setenv("DATA_GO_KR_API_KEY", "dummy")
    monkeypatch.setattr(daily.requests, "get", flaky)
    monkeypatch.setattr(daily.time, "sleep", lambda s: None)   # 테스트에서 실제로 기다리지 않는다

    df = daily.fetch_day("20260812")
    assert calls["n"] == 3
    assert list(df["code"]) == ["005930"]


def test_collect_survives_api_outage(monkeypatch):
    """재시도를 다 써도 실패하면 수집만 포기하고 계산은 이어간다.

    예외가 올라가면 계산·산출까지 죽어 그날 배포가 통째로 없어진다.
    """
    from batch import run as run_mod

    monkeypatch.setattr(run_mod.daily, "api_key", lambda: "dummy")
    def boom(*a, **k):
        raise requests.ConnectTimeout("timed out")
    monkeypatch.setattr(run_mod.daily, "fetch_day", boom)

    run_mod.collect(["005930"])   # 예외가 새어 나오면 테스트 실패
