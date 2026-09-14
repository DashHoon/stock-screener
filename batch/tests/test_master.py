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
    desc = pd.DataFrame(
        [
            {
                "Code": code, "Industry": "전자부품 제조업", "Products": "제품",
                "ListingDate": "2020-01-01", "Representative": "대표",
                "HomePage": "", "Region": "서울",
            }
            for code in listing["Code"]
        ]
    )
    monkeypatch.setattr(
        fdr,
        "StockListing",
        lambda kind: listing.copy() if kind == "KRX" else desc.copy(),
    )

    got = master.fetch_stock_master().set_index("code")

    assert got.loc["005930", "close"] == 70000
    assert got.loc["005930", "change_pct"] == 1.25
    assert got.loc["123450", "close"] == 0
    assert got.loc["123450", "change_pct"] == 0
    assert got.loc["123450", "marcap"] == -1
