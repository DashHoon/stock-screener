"""일별 병합의 급변 감지(수정주가 의심) 로직 검증."""

import pandas as pd
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
