"""차트 패턴 탐지 집합.

모든 패턴 객체는 공통 인터페이스를 가진다:
kind, completed_at(None=미완성), forming, neckline, points[(idx, price)...]
"""

import pandas as pd

from batch.patterns.cup import detect_cup_handle
from batch.patterns.diamond import detect_diamond
from batch.patterns.double import detect_double_patterns
from batch.patterns.flag import detect_flags
from batch.patterns.multi import detect_head_shoulders, detect_triple
from batch.patterns.round import detect_round
from batch.patterns.trend import detect_trendline_patterns

# 완성(sig) 키 목록 — 백테스트 이벤트 등록에도 사용
PATTERN_KINDS = (
    "pat_double_bottom", "pat_double_top",
    "pat_cup_handle",
    "pat_hs_top", "pat_hs_inv",
    "pat_triple_bottom", "pat_triple_top",
    "pat_round_bottom", "pat_round_top",
    "pat_tri_asc", "pat_tri_desc", "pat_tri_sym_up", "pat_tri_sym_down",
    "pat_wedge_rise", "pat_wedge_fall",
    "pat_flag_bull", "pat_flag_bear",
    "pat_broadening", "pat_diamond",
)


def detect_all_patterns(ohlcv: pd.DataFrame) -> list:
    pats = (
        list(detect_double_patterns(ohlcv))
        + list(detect_cup_handle(ohlcv))
        + list(detect_head_shoulders(ohlcv))
        + list(detect_triple(ohlcv))
        + list(detect_round(ohlcv))
        + list(detect_trendline_patterns(ohlcv))
        + list(detect_flags(ohlcv))
        + list(detect_diamond(ohlcv))
    )
    pats.sort(key=lambda p: p.completed_at if p.completed_at is not None else len(ohlcv))
    return pats
