"""차트 패턴 탐지 집합.

모든 패턴 객체는 공통 인터페이스를 가진다:
kind, completed_at(None=미완성), forming, neckline, points[(idx, price)...]
"""

import pandas as pd

from batch.patterns.cup import detect_cup_handle
from batch.patterns.double import detect_double_patterns

PATTERN_KINDS = ("pat_double_bottom", "pat_double_top", "pat_cup_handle")


def detect_all_patterns(ohlcv: pd.DataFrame) -> list:
    pats = list(detect_double_patterns(ohlcv)) + list(detect_cup_handle(ohlcv))
    pats.sort(key=lambda p: p.completed_at if p.completed_at is not None else len(ohlcv))
    return pats
