"""공공 API 하루치 수집(fetch_day) 검증."""

import requests

from batch.collector import daily


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


def _item(code, name, o, h, l, c, vol, vs=0):
    return {"srtnCd": code, "itmsNm": name, "basDt": "20260805",
            "mkp": str(o), "hipr": str(h), "lopr": str(l),
            "clpr": str(c), "vs": str(vs), "trqu": str(vol)}


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


def test_fetch_day_derives_base_price(monkeypatch):
    """기준가 = 종가 - 전일 대비. 수정주가 계산의 근거라 부호까지 맞아야 한다."""
    items = [_item("000660", "SK하이닉스", 1722000, 1759000, 1681000, 1681000, 3203231, vs=-42000)]
    monkeypatch.setenv("DATA_GO_KR_API_KEY", "dummy")
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: _FakeResp(items))
    assert daily.fetch_day("20261008")["base"].iloc[0] == 1723000


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
