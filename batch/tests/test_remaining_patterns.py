"""Directional symmetry and causal states for the remaining pattern review."""
import numpy as np
import pytest

from batch.patterns import detect_all_patterns
from batch.tests.test_ascending_triangle import triangle
from batch.tests.test_patterns_more import _df, _leg
from batch.tests.test_patterns import _w_shape


def reference_cases():
    cases = {}
    def pair(seq, up, down, label):
        cases[up] = (label+' · 상승', seq)
        cases[down] = (label+' · 하락', [220-v for v in seq])
    cases['pat_tri_desc'] = ('하락 삼각형', [200-v for v in triangle()+[101.5,102.,103.]])
    seq=[100.]*3
    for top,bot in [(112,88),(108,92)]:
        seq+=_leg(seq[-1],top,8)+_leg(top,bot,8)
    seq+=_leg(92,99,4)
    cases['pat_tri_sym_up']=('대칭 삼각형 · 상향',seq+[115.]*4)
    cases['pat_tri_sym_down']=('대칭 삼각형 · 하향',seq+[85.]*4)
    pair(_w_shape(), 'pat_double_bottom','pat_double_top','쌍바닥/쌍봉')
    seq=[105.]*3+_leg(105,90,8)+[89.5]+_leg(90,100,8)
    seq+=_leg(100,80,8)+[79.5]+_leg(80,101,8)+_leg(101,91,8)+[90.5]+_leg(91,108,10)+[108.]*10
    pair(seq,'pat_hs_inv','pat_hs_top','헤드앤숄더')
    seq=[120.]*3+_leg(120,100,6)
    for _ in range(3):seq+=[99.5]+_leg(100,110,6)+_leg(110,100.5,6)
    seq=seq[:-6]+_leg(110,115,6)+[115.]*10
    pair(seq,'pat_triple_bottom','pat_triple_top','삼중 바닥/천장')
    seq=[95.]*3+_leg(95,100,5)
    for i in range(1,120):
        t=i/120; p=.25
        side=(p-t)/p if t<=p else (t-p)/(1-p)
        seq.append(75+25*side**2)
    seq+=_leg(100,106,8)+[106.]*10
    pair(seq,'pat_round_bottom','pat_round_top','비대칭 라운드')
    seq=[100.]*3
    for top,bot in zip([112,108,104,100],[100,98,96,94]):
        seq+=_leg(seq[-1],top,5)+_leg(top,bot,5)
    seq+=_leg(seq[-1],106,4)+[106.]*8
    pair(seq,'pat_wedge_fall','pat_wedge_rise','수렴 쐐기')
    seq=[100.]*5+_leg(100,130,15)
    seq += [130-3*(i%4)/3-i*.3 for i in range(1,26)]
    seq+=_leg(seq[-1],133,3)+[133.]*8
    pair(seq,'pat_flag_bull','pat_flag_bear','플래그 · 기존 기준 유지')
    seq=[100.]*3
    for top,bot in zip((110,116,122),(90,84,78)):
        seq+=_leg(seq[-1],top,8)+_leg(top,bot,8)
    cases['pat_broadening']=('브로드닝 · 하단 이탈',seq+_leg(seq[-1],60,5)+[60.]*5)
    half=25
    seq=[100.]*5+[100+(2+18*(1-abs(i-half)/half))*np.cos((i-half)*np.pi/10) for i in range(2*half+1)]
    cases['pat_diamond']=('다이아몬드 탑',seq+[90.,85.,80.,80.])
    return cases


@pytest.mark.parametrize('kind', list(reference_cases()))
def test_reference_completion_is_available_on_its_date(kind):
    _,seq=reference_cases()[kind]
    df=_df(seq)
    hits=[h for h in detect_all_patterns(df) if h.kind==kind and h.completed_at is not None]
    assert hits, kind
    first=hits[0]
    prefix=[h for h in detect_all_patterns(df.iloc[:first.completed_at+1]) if h.kind==kind]
    assert any(h.completed_at==first.completed_at for h in prefix)
    forming_kind = 'pat_tri_sym' if kind.startswith('pat_tri_sym_') else kind
    assert any(h.forming and h.kind==forming_kind
               for h in detect_all_patterns(df.iloc[:first.completed_at]))


def test_descending_triangle_pending_and_opposite_failure():
    seq=triangle()
    def hits(tail):
        return [h for h in detect_all_patterns(_df([200-v for v in seq+tail])) if h.kind=='pat_tri_desc']
    assert hits([])[0].forming
    assert hits([101.5])[0].forming
    assert hits([101.5,102.])[0].completed_at is not None
    assert not hits([98.,85.,84.])


@pytest.mark.parametrize('kind,factor', [('pat_double_bottom',6), ('pat_double_top',6),
    ('pat_hs_inv',4.5), ('pat_hs_top',4.5), ('pat_triple_bottom',4), ('pat_triple_top',4)])
def test_long_minor_structures_are_not_lost_to_scale_caps(kind, factor):
    from batch.patterns.swing import build_ctx
    from batch.patterns.double import detect_double_patterns
    from batch.patterns.multi import detect_head_shoulders, detect_triple
    _, seq = reference_cases()[kind]
    grid = np.arange((len(seq)-1)*factor+1) / factor
    df = _df(np.interp(grid, np.arange(len(seq)), seq))
    ctx = build_ctx(df)
    ctx.major = []  # The minor structure itself must be searchable through 200 bars.
    detector = detect_double_patterns if 'double' in kind else detect_head_shoulders if 'hs_' in kind else detect_triple
    hits = [h for h in detector(df, ctx) if h.kind == kind and h.completed_at is not None]
    assert hits
    assert all(h.points[-1][0]-h.points[0][0]+1 <= 200 for h in hits)
