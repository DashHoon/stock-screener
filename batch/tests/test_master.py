"""종목 마스터 수집 정규화 검증."""

import pandas as pd

from batch.collector import master


def test_master_keeps_rows_with_dash_prices(monkeypatch):
    """거래정지 종목의 '-' 가격이 전체 마스터 갱신을 실패시키지 않는다."""
    import FinanceDataReader as fdr

    listing = pd.DataFrame(
        [
            {
                "Code": "005930", "Name": "삼성전자", "MarketId": "STK",
                "Close": "70000", "ChagesRatio": "1.25", "Marcap": "400000000000000",
            },
            {
                "Code": "123450", "Name": "거래정지종목", "MarketId": "KSQ",
                "Close": "-", "ChagesRatio": "-", "Marcap": "-",
            },
        ]
    )
    desc = pd.DataFrame([
        {
            "Code": "005930", "Industry": "전자부품 제조업", "Products": "제품",
            "ListingDate": "2020-01-01", "Representative": "대표",
            "HomePage": "", "Region": "서울",
        },
        {
            "Code": "123450", "Industry": None, "Products": "제품",
            "ListingDate": "2020-01-01", "Representative": "대표",
            "HomePage": "", "Region": "서울",
        },
    ])
    monkeypatch.setattr(fdr, "StockListing", lambda kind: listing.copy())
    monkeypatch.setattr(master, "fetch_kind_desc", lambda: desc.copy())

    got = master.fetch_stock_master().set_index("code")

    assert got.loc["005930", "close"] == 70000
    assert got.loc["005930", "change_pct"] == 1.25
    assert got.loc["123450", "close"] == 0
    assert got.loc["123450", "change_pct"] == 0
    assert got.loc["123450", "marcap"] == -1
    assert got.loc["123450", "sector"]  # NaN 업종도 예외 없이 '기타'로 분류


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
    import FinanceDataReader as fdr

    from batch import config

    cache = tmp_path / "stocks.parquet"
    pd.DataFrame([{"code": "005930", "industry": "통신 및 방송 장비 제조업",
                   "products": "반도체", "listing_date": "1975-06-11", "ceo": "대표",
                   "homepage": "http://www.samsung.com", "region": "경기도"}]).to_parquet(cache)
    monkeypatch.setattr(config, "STOCKS_CACHE", cache)
    monkeypatch.setattr(fdr, "StockListing", lambda kind: pd.DataFrame([{
        "Code": "005930", "Name": "삼성전자", "MarketId": "STK",
        "Close": "70000", "ChagesRatio": "0", "Marcap": "1"}]))

    def boom():
        raise ValueError("404")

    monkeypatch.setattr(master, "fetch_kind_desc", boom)
    got = master.fetch_stock_master().set_index("code")
    assert got.loc["005930", "industry"] == "통신 및 방송 장비 제조업"
    assert got.loc["005930", "products"] == "반도체"
    assert got.loc["005930", "sector"] == "반도체"
