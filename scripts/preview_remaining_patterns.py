"""Local, dependency-free HTML review for the remaining pattern families."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from batch.patterns import detect_all_patterns
from batch.tests.test_remaining_patterns import reference_cases
from batch.tests.test_patterns_more import _df


def render(df, hit):
    levels=list(df.low)+list(df.high)
    for pts in (hit.points,getattr(hit,'points2',None) or []):
        levels += [v for _,v in pts]
    lo,hi=min(levels),max(levels); pad=max(1,(hi-lo)*.15);lo-=pad;hi+=pad
    x=lambda i:40+i*850/max(1,len(df)-1)
    y=lambda v:290-(v-lo)*250/(hi-lo)
    out=['<svg viewBox="0 0 940 330" role="img" aria-label="일봉과 탐지된 패턴">']
    for i,r in df.iterrows():
        color='#f17d88' if r.close>=r.open else '#72b5ff'
        out.append(f'<path d="M{x(i)} {y(r.high)}V{y(r.low)}" stroke="{color}"/><rect x="{x(i)-2}" y="{y(max(r.open,r.close))}" width="4" height="{max(1,y(min(r.open,r.close))-y(max(r.open,r.close)))}" fill="{color}"/>')
    for pts in (hit.points,getattr(hit,'points2',None) or []):
        if pts:
            path=' '.join(f'{x(i)},{y(v)}' for i,v in pts)
            out.append(f'<polyline points="{path}" fill="none" stroke="#f6d477" stroke-width="2"/>')
    if hit.completed_at is not None:
        xx=x(hit.completed_at)
        out.append(f'<path d="M{xx} 20V295" stroke="#72ebc9" stroke-dasharray="5 5"/>')
    return ''.join(out)+'</svg>'

sections=[]
for kind,(name,seq) in reference_cases().items():
    df=_df(seq)
    hit=next(h for h in detect_all_patterns(df) if h.kind==kind and h.completed_at is not None)
    before=df.iloc[:hit.completed_at]
    forming_kind='pat_tri_sym' if kind.startswith('pat_tri_sym_') else kind
    forming=next(h for h in detect_all_patterns(before) if h.kind==forming_kind and h.forming)
    sections.append(f'<details><summary>{name}</summary><h3>돌파 전 · 형성 중</h3>'+render(before,forming)+'<h3>돌파 완료</h3>'+render(df,hit)+f'<p>확정일: {df.date.iloc[hit.completed_at]} · 형상 점수: {hit.shape}</p></details>')
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>나머지 패턴 검토</title><style>body{background:#101722;color:#e2ebf5;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 24px}details{border:1px solid #35445a;border-radius:10px;padding:18px;margin:14px 0}summary{cursor:pointer;font-size:19px}svg{width:100%}p{color:#b8c7da;line-height:1.7}</style><h1>패턴별 형성 중 / 돌파 완료 확인</h1><p>항목을 하나씩 펼쳐 확인하세요. 모두 동작 검증을 위한 <strong>합성 예시</strong>이며, 실제 종목 탐지 정확도를 증명하는 자료는 아닙니다.<br>노란 선은 탐지된 구조, 초록 점선은 돌파 확정일입니다. 플래그는 기존 조건을 유지했습니다.<br>상승 삼각형·컵앤핸들·확대 쐐기는 앞서 만든 별도 비교 페이지에서 확인할 수 있습니다.</p>'''
out=ROOT/'_workspace/remaining-patterns-review.html'
out.write_text(html+''.join(sections)+'</html>',encoding='utf-8')
print(out)
