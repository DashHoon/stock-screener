"""일봉 → 주봉/월봉 리샘플.

지표는 리샘플된 봉 위에서 다시 계산해야 한다 (일봉 지표의 리샘플이 아님).
마지막 미완성 주/월봉도 포함한다 (증권 앱 관행과 동일).
"""

import pandas as pd

FREQ = {"w": "W-FRI", "m": "ME"}


def resample_ohlcv(daily: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """일봉 DataFrame(date,open,high,low,close,volume) → 주봉('w')/월봉('m').

    돌려주는 형식은 일봉과 동일 (date는 해당 구간 마지막 거래일).
    """
    df = daily.copy()
    df["dt"] = pd.to_datetime(df["date"])
    df = df.set_index("dt")
    agg = df.resample(FREQ[timeframe]).agg(
        date=("date", "last"),   # 라벨이 아닌 실제 마지막 거래일 사용
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    agg = agg.dropna(subset=["date"])  # 거래 없는 주(연휴 등) 제거
    for c in ["open", "high", "low", "close", "volume"]:
        agg[c] = agg[c].astype("int64")
    return agg.reset_index(drop=True)
