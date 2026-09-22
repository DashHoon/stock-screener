"""Local review: synthetic asymmetric cups, early handles and exclusions."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import batch.patterns.cup as cup
from types import SimpleNamespace
from batch.patterns import detect_all_patterns
from batch.tests.test_cup import _df, _cup_shape, _asymmetric_cup

old = dict(cup.__dict__)
exec(compile(subprocess.check_output(['git', 'show', '71a253d9a:batch/patterns/cup.py'], cwd=ROOT, text=True), '<baseline>', 'exec'), old)

old["config"] = SimpleNamespace(**vars(cup.config))
old["config"].CUP_BOTTOM_ZONE = (.30, .70)
old["config"].CUP_FLAT_FRAC = .25

def chart(df, detector, title, tail=100):
    hits = [h for h in detector(df) if h.kind == 'pat_cup_handle']
    start = max(0, len(df) - tail)
    hits = [h for h in hits if h.structure_span[0] >= start]
    lo, hi = df.low.iloc[start:].min(), df.high.iloc[start:].max()
    padding = (hi-lo)*.15
    lo, hi = lo-padding, hi+padding
    x = lambda i: 65 + (i-start)*850/max(1,len(df)-start-1)
    y = lambda v: 310-(v-lo)*270/(hi-lo)
    svg = ['<svg viewBox="0 0 960 360" role="img" aria-label="일봉 및 컵앤핸들 탐지 결과">']
    for i in range(start, len(df)):
        r=df.iloc[i];color='#f1767e' if r.close>=r.open else '#6badff'
        svg.append(f'<path d="M{x(i)} {y(r.high)}V{y(r.low)}" stroke="{color}"/><rect x="{x(i)-2}" y="{y(max(r.open,r.close))}" width="4" height="{max(1,y(min(r.open,r.close))-y(max(r.open,r.close)))}" fill="{color}"/>')
        if (i-start)%max(1,(len(df)-start)//5)==0:
            svg.append(f'<text x="{x(i)}" y="345" fill="#aabbd0" font-size="12">{str(r.date)[5:10]}</text>')
    notes=[]
    for h in hits:
        for points in zip(h.points, h.points[1:]):
            (a,av),(b,bv)=points
            svg.append(f'<path d="M{x(a)} {y(av)}L{x(b)} {y(bv)}" stroke="#f6d26a" stroke-width="2" fill="none"/>')
        for i,v in h.points:
            svg.append(f'<circle cx="{x(i)}" cy="{y(v)}" r="4" fill="#0e1520" stroke="#f6d26a"/>')
        state='형성 중' if h.forming else '돌파 완료 · '+str(df.date.iloc[h.completed_at])[:10]
        notes.append(state+' · 접점 '+str(len(h.points))+'개')
        if h.completed_at is not None:
            svg.append(f'<path d="M{x(h.completed_at)} 25V315" stroke="#70e4bb" stroke-dasharray="4 4"/>')
    return '<section><h2>'+title+'</h2>'+''.join(svg)+'</svg><p>'+(' / '.join(notes) or '탐지 없음')+'</p></section>'

html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>컵앤핸들 확인</title><style>body{background:#0e1520;color:#e1eaf5;font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 24px}section{border:1px solid #304258;border-radius:12px;padding:18px;margin:20px 0}svg{width:100%}p{color:#b3c4d9}h2{font-size:20px}</style><h1>컵앤핸들 · 변경 전후</h1><p>모든 차트는 조건별 동작을 확인하기 위한 합성 예시입니다. 실제 종목 사례가 아닙니다.<br>노란 선은 좌림·바닥·우림·핸들 연결이며, 초록 점선은 돌파일입니다. 운영 사이트에는 미반영입니다.</p>'
for title,seq in [('비대칭 U자 컵',_asymmetric_cup()), ('초기 핸들 3봉',_cup_shape()[:74]), ('핸들 형성 중',_asymmetric_cup(breakout=False)), ('V자 반등 · 제외',_cup_shape(v_shape=True)), ('깊은 핸들 · 제외',_cup_shape(handle_dip_pct=15))]:
    df=_df(seq)
    html+=chart(df,old['detect_cup_handle'],title+' · 변경 전')
    html+=chart(df,detect_all_patterns,title+' · 변경 후')
out=ROOT/'_workspace/cup-handle-review.html';out.write_text(html+'</html>',encoding='utf-8');print(out)
