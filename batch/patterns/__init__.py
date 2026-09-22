"""차트 패턴 탐지 집합.

모든 패턴 객체는 공통 인터페이스를 가진다:
kind, completed_at(None=미완성), forming, neckline, points[(idx, price)...]
"""

import pandas as pd

from batch import config
from batch.patterns.cup import detect_cup_handle
from batch.patterns.diamond import detect_diamond
from batch.patterns.double import detect_double_patterns
from batch.patterns.flag import detect_flags
from batch.patterns.multi import detect_head_shoulders, detect_triple
from batch.patterns.round import detect_round
from batch.patterns.shape import score_shapes
from batch.patterns.swing import build_ctx
from batch.patterns.trend import detect_trendline_patterns
from batch.patterns.util import structure_span, within_pattern_limits

# 완성(sig) 키 목록 — 백테스트 이벤트 등록에도 사용
PATTERN_KINDS = (
    "pat_double_bottom", "pat_double_top",
    "pat_cup_handle",
    "pat_hs_top", "pat_hs_inv",
    "pat_triple_bottom", "pat_triple_top",
    "pat_round_bottom", "pat_round_top",
    "pat_tri_asc", "pat_tri_desc", "pat_tri_sym_up", "pat_tri_sym_down",
    "pat_wedge_rise", "pat_wedge_fall",
    "pat_bwedge_rise", "pat_bwedge_fall",
    "pat_flag_bull", "pat_flag_bear",
    "pat_broadening", "pat_diamond",
)


# 같은 종류가 이만큼(짧은 쪽 기준 비율) 겹치면 동일 패턴의 중복 검출로 본다.
DEDUP_OVERLAP = 0.6


def _span(p) -> tuple[int, int]:
    return structure_span(p)


def dedupe_patterns(pats: list) -> list:
    """Keep earlier events stable; rank simultaneous/active alternatives by shape.

    A later, longer candidate must never erase a completed historical event.
    """
    kept: list = []
    order = sorted(
        pats,
        key=lambda p: (
            p.completed_at if p.completed_at is not None else 1 << 30,
            -p.shape,
            -getattr(p, "quality", 0.0),
            _span(p), p.kind,
        ),
    )
    for p in order:
        s1, e1 = _span(p)
        dup = False
        for q in kept:
            if q.kind != p.kind:
                continue
            if (q.completed_at is None) != (p.completed_at is None):
                continue  # 완성/형성 중은 서로를 가리지 않는다
            s2, e2 = _span(q)
            overlap = min(e1, e2) - max(s1, s2)
            if overlap <= 0:
                continue
            shorter = min(e1 - s1, e2 - s2)
            if shorter <= 0 or overlap / shorter >= DEDUP_OVERLAP:
                dup = True
                break
        if not dup:
            kept.append(p)
    return kept


def detect_all_patterns(ohlcv: pd.DataFrame) -> list:
    if len(ohlcv) < config.PATTERN_MIN_BARS:
        return []
    ctx = build_ctx(ohlcv)  # 스윙 구조는 한 번만 계산해 전 탐지기가 공유
    pats = (
        list(detect_double_patterns(ohlcv, ctx))
        + list(detect_cup_handle(ohlcv, ctx))
        + list(detect_head_shoulders(ohlcv, ctx))
        + list(detect_triple(ohlcv, ctx))
        + list(detect_round(ohlcv, ctx))
        + list(detect_trendline_patterns(ohlcv, ctx))
        + list(detect_flags(ohlcv))
        + list(detect_diamond(ohlcv, ctx))
    )
    # 걸러내기는 병합보다 먼저 — 병합은 겹치는 후보 중 대표 1개를 고르므로,
    # 탈락할 후보가 대표로 뽑히면 그 자리의 멀쩡한 형제까지 같이 사라진다.
    pats = [p for p in pats if within_pattern_limits(p, len(ohlcv))]
    pats = score_shapes(ohlcv, pats)   # 형태 통과선 (차트·스크리너 공통 집합)
    pats = dedupe_patterns(pats)
    pats.sort(key=lambda p: p.completed_at if p.completed_at is not None else len(ohlcv))
    return pats
