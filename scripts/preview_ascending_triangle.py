"""Local review: real NAVER candles and explicit synthetic state transitions."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import batch.patterns.trend as trend
from batch.patterns import detect_all_patterns
from batch.tests.test_ascending_triangle import triangle
from batch.tests.test_patterns_more import _df

old = dict(trend.__dict__)
exec(compile(subprocess.check_output(['git', 'show', '71a253d9a:batch/patterns/trend.py'], cwd=ROOT, text=True), '<baseline>', 'exec'), old)

def chart(df, detector, title, tail=100):
    hits = [h for h in detector(df) if h.kind == 'pat_tri_asc']
    start = max(0, len(df) - tail)
    hits = [h for h in hits if h.structure_span[0] >= start]
    lo, hi = df.low.iloc[start:].min(), df.high.iloc[start:].max()
    padding = (hi-lo)*.15
    lo, hi = lo-padding, hi+padding
    x = lambda i: 65 + (i-start)*850/max(1,len(df)-start-1)
    y = lambda v: 310-(v-lo)*270/(hi-lo)
    svg = ['<svg viewBox="0 0 960 360" role="img" aria-label="일봉 및 상승 삼각형 탐지 결과">']
    for i in range(start, len(df)):
        r=df.iloc[i];color='#f1767e' if r.close>=r.open else '#6badff'
        svg.append(f'<path d="M{x(i)} {y(r.high)}V{y(r.low)}" stroke="{color}"/><rect x="{x(i)-2}" y="{y(max(r.open,r.close))}" width="4" height="{max(1,y(min(r.open,r.close))-y(max(r.open,r.close)))}" fill="{color}"/>')
        if (i-start)%max(1,(len(df)-start)//5)==0:
            svg.append(f'<text x="{x(i)}" y="345" fill="#aabbd0" font-size="12">{str(r.date)[5:10]}</text>')
    notes=[]
    for h in hits:
        for points in (h.points,h.points2):
            (a,av),(b,bv)=points
            svg.append(f'<path d="M{x(a)} {y(av)}L{x(b)} {y(bv)}" stroke="#f6d26a" stroke-width="2" fill="none"/>')
        for i,v in h.touch_points:
            svg.append(f'<circle cx="{x(i)}" cy="{y(v)}" r="4" fill="#0e1520" stroke="#f6d26a"/>')
        state='형성 중' if h.forming else '돌파 완료 · '+str(df.date.iloc[h.completed_at])[:10]
        notes.append(state+' · 접점 '+str(len(h.touch_points))+'개')
        if h.completed_at is not None:
            svg.append(f'<path d="M{x(h.completed_at)} 25V315" stroke="#70e4bb" stroke-dasharray="4 4"/>')
    return '<section><h2>'+title+'</h2>'+''.join(svg)+'</svg><p>'+(' / '.join(notes) or '탐지 없음')+'</p></section>'

naver=pd.read_parquet(ROOT/'batch/data/cache/ohlcv/035420.parquet').tail(300).reset_index(drop=True)
seq=triangle()
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>상승 삼각형 확인</title><style>body{background:#0e1520;color:#e1eaf5;font:16px system-ui;max-width:1100px;margin:30px auto;padding:0 24px}section{border:1px solid #304258;border-radius:12px;padding:18px;margin:20px 0}svg{width:100%}p{color:#b3c4d9;line-height:1.6}h2{font-size:20px}</style><h1>상승 삼각형 · 형성과 돌파</h1><p>노란 선: 확정된 저항·지지선 / 원: 접점 / 초록 점선: 돌파 확정일<br>로컬 검토용이며 운영 사이트에는 반영하지 않았습니다.</p>'''
html+=chart(naver,old['detect_trendline_patterns'],'NAVER 실제 저장 일봉 · 변경 전')
html+=chart(naver,trend.detect_trendline_patterns,'NAVER 실제 저장 일봉 · 변경 후 (기준일 '+str(naver.date.iloc[-1])[:10]+')')
for title,tail in [('형성 중',[]),('첫 돌파 · 아직 형성 중',[101.5]),('돌파 확정',[101.5,102.]),('하단 이탈 · 제외',[98.,85.,84.])]:
    html+=chart(_df(seq+tail),detect_all_patterns,'합성 예시 · '+title)
out=ROOT/'_workspace/ascending-triangle-review.html';out.write_text(html+'</html>',encoding='utf-8');print(out)
