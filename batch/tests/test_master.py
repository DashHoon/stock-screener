"""종목 마스터 수집 정규화 검증."""

import pandas as pd

from batch.collector import master


def _day(rows):
    """daily.fetch_day 형식의 하루치 (code, name, market, close, base, mcap …)."""
    return pd.DataFrame([
        {"code": code, "date": "2026-10-12", "open": c, "high": c, "low": c, "close": c,
         "volume": 1, "base": b, "name": name, "market": mkt, "shares": 10, "mcap": mcap}
        for code, name, mkt, c, b, mcap in rows
    ])


DESC = pd.DataFrame([
    {"Code": "005930", "Industry": "통신 및 방송 장비 제조업", "Products": "반도체",
     "ListingDate": "1975-06-11", "Representative": "대표", "HomePage": None, "Region": "경기도"},
])


def test_master_from_public_day(monkeypatch):
    """목록·시장·시총·등락률이 같은 날 시세에서 나오고, 코넥스·스팩·우선주는 빠진다."""
    monkeypatch.setattr(master, "fetch_kind_desc", lambda: DESC.copy())
    monkeypatch.setattr(master, "_cached_desc", lambda: None)
    day = _day([
        ("005930", "삼성전자", "KOSPI", 250500, 262000, 1464492700000000),
        ("123450", "업종미상", "KOSDAQ", 1000, 1000, 0),
        ("005935", "삼성전자우", "KOSPI", 200000, 200000, 1),   # 우선주
        ("440790", "어떤스팩1호", "KOSDAQ", 2000, 2000, 1),       # 스팩
        ("217880", "코넥스종목", "KONEX", 3000, 3000, 1),
    ])
    got = master.fetch_stock_master(day).set_index("code")

    assert sorted(got.index) == ["005930", "123450"]
    assert got.loc["005930", "market"] == "KOSPI"
    assert got.loc["005930", "marcap"] == 14644927          # 억원, 그날 시총 그대로
    assert got.loc["005930", "change_pct"] == -4.39          # 기준가 대비
    assert got.loc["005930", "sector"] == "반도체"
    assert got.loc["123450", "marcap"] == -1                 # 시총 0 = 알 수 없음
    assert got.loc["123450", "sector"]                       # 업종 없음도 '기타'로 분류
    assert got.index[0] == "005930"                          # 시총 내림차순


def test_master_rejects_pre_migration_day_file(tmp_path, monkeypatch):
    """종목명이 없는 옛 일자별 파일로는 마스터를 만들지 않는다 (캐시 마스터로 폴백)."""
    import pytest

    from batch.collector import daystore

    monkeypatch.setattr(daystore, "DAY_DIR", tmp_path)
    _day([("005930", "x", "KOSPI", 1, 1, 1)]).drop(columns=["name"]).to_parquet(tmp_path / "2026-10-12.parquet")
    with pytest.raises(ValueError):
        master.fetch_stock_master()


KIND_HTML = """<html><head><meta charset="euc-kr"></head><body><table>
<tr><th>회사명</th><th>시장구분</th><th>종목코드</th><th>업종</th><th>주요제품</th>
<th>상장일</th><th>결산월</th><th>대표자명</th><th>홈페이지</th><th>지역</th></tr>
<tr><td>삼성전자</td><td>
   유가
</td><td style="mso-number-format:'@'">005930</td><td>통신 및 방송 장비 제조업</td>
<td>반도체, 휴대폰</td><td>1975-06-11</td><td>12월</td><td>전영현, 노태문</td>
<td>
   http://www.samsung.com/sec
</td><td>경기도</td></tr>
<tr><td>브릴스</td><td>코스닥</td><td>468670</td><td>특수 목적용 기계 제조업</td><td></td>
<td>2026-10-01</td><td>12월</td><td>전진</td><td></td><td>인천광역시</td></tr>
</table></body></html>"""


class _Resp:
    def __init__(self, body):
        self.content = body.encode("euc-kr")

    def raise_for_status(self):
        pass


def test_fetch_kind_desc_parses_table(monkeypatch):
    """KIND 표를 코드·업종·회사 개요로. 셀 안 공백·줄바꿈은 정리하고 빈 칸은 결측."""
    monkeypatch.setattr(master.requests, "get", lambda *a, **k: _Resp(KIND_HTML))
    monkeypatch.setattr(master, "KIND_MIN_ROWS", 1)
    got = master.fetch_kind_desc().set_index("Code")
    assert got.loc["005930", "HomePage"] == "http://www.samsung.com/sec"
    assert got.loc["005930", "Representative"] == "전영현, 노태문"
    assert got.loc["468670", "ListingDate"] == "2026-10-01"
    assert pd.isna(got.loc["468670", "Products"])


def test_fetch_kind_desc_rejects_changed_format(monkeypatch):
    """컬럼이 바뀌면 조용히 빈 값을 넣지 않고 실패한다 (호출부가 캐시로 폴백)."""
    import pytest

    changed = KIND_HTML.replace("<th>업종</th>", "<th>산업</th>")
    monkeypatch.setattr(master.requests, "get", lambda *a, **k: _Resp(changed))
    with pytest.raises(ValueError):
        master.fetch_kind_desc()


def test_master_falls_back_to_cached_desc(tmp_path, monkeypatch):
    """KIND가 실패하면 업종과 회사 개요를 마지막 캐시 값으로 채운다."""
    from batch import config

    cache = tmp_path / "stocks.parquet"
    pd.DataFrame([{"code": "005930", "industry": "통신 및 방송 장비 제조업",
                   "products": "반도체", "listing_date": "1975-06-11", "ceo": "대표",
                   "homepage": "http://www.samsung.com", "region": "경기도"}]).to_parquet(cache)
    monkeypatch.setattr(config, "STOCKS_CACHE", cache)

    def boom():
        raise ValueError("404")

    monkeypatch.setattr(master, "fetch_kind_desc", boom)
    got = master.fetch_stock_master(_day([("005930", "삼성전자", "KOSPI", 70000, 70000, 1)])).set_index("code")
    assert got.loc["005930", "industry"] == "통신 및 방송 장비 제조업"
    assert got.loc["005930", "products"] == "반도체"
    assert got.loc["005930", "sector"] == "반도체"
