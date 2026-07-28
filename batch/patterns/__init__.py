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
from batch.patterns.shape import grade_shapes
from batch.patterns.swing import build_ctx
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


# 같은 종류가 이만큼(짧은 쪽 기준 비율) 겹치면 동일 패턴의 중복 검출로 본다.
DEDUP_OVERLAP = 0.6


def _span(p) -> tuple[int, int]:
    return p.points[0][0], p.points[-1][0]


def dedupe_patterns(pats: list) -> list:
    """같은 종류가 같은 구간에 중복 검출된 것을 대표 1개로 병합한다.

    피벗 조합이 조금씩 다르면 사실상 같은 그림이 여러 번 잡힌다 (실측: 코스닥
    라운드탑 7개가 모두 2025-09~2026-07 구간의 동일 패턴). 차트가 선으로 뒤덮이고
    시그널도 부풀려지므로, 구간이 DEDUP_OVERLAP 이상 겹치면 하나만 남긴다.
    대표는 '가장 길게 그려진 것'(패턴 형태가 가장 온전) → 동률이면 최근 완성분.
    """
    kept: list = []
    # 긴 것 → 최근 완성 순으로 보며 채택, 이미 채택된 것과 겹치면 버린다
    order = sorted(
        pats,
        key=lambda p: (
            -(_span(p)[1] - _span(p)[0]),
            -(p.completed_at if p.completed_at is not None else 1 << 30),
        ),
    )
    for p in order:
        s1, e1 = _span(p)
        dup = False
        for q in kept:
            if q.kind != p.kind:
                continue
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
    pats = dedupe_patterns(pats)
    grade_shapes(ohlcv, pats)  # 형태 신뢰도 등급 (차트·스크리너 공통)
    pats.sort(key=lambda p: p.completed_at if p.completed_at is not None else len(ohlcv))
    return pats
