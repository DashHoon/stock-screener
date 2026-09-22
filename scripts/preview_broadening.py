"""Render cached SK Hynix candles and before/after pattern overlays locally."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import batch.patterns.trend as trend

frame = pd.read_csv(ROOT / 'batch/tests/fixtures/000660_broadening.csv', parse_dates=['date']).set_index('date')
# Fixed pre-change baseline; no network or production data writes.
baseline = dict(trend.__dict__)
exec(compile(subprocess.check_output(['git', 'show', '6f82ab3be:batch/patterns/trend.py'], cwd=ROOT, text=True), '<baseline>', 'exec'), baseline)
start = int(frame.index.searchsorted('2026-04-01'))
low, high = 650000, 3700000
x = lambda i: 60 + (i - start) * 11
y = lambda value: 440 - (value - low) / (high - low) * 390
width = x(len(frame)) + 30

def chart(detector):
    hits = [h for h in detector(frame) if h.kind == 'pat_bwedge_rise' and h.structure_span[0] >= start]
    svg = [f'<svg viewBox="0 0 {width} 490" role="img" aria-label="SK하이닉스 일봉과 확대 쐐기 탐지 결과">']
    for price in range(1000000, 3500001, 500000):
        svg.append(f'<path d="M55 {y(price)}H{width}" stroke="#263343"/><text x="0" y="{y(price)}" fill="#9caec2" font-size="11">{price/10000:g}만</text>')
    for i in range(start, len(frame)):
        r = frame.iloc[i]; color = '#ef6670' if r.close >= r.open else '#62a8ff'
        svg.append(f'<path d="M{x(i)} {y(r.high)}V{y(r.low)}" stroke="{color}"/><rect x="{x(i)-3}" y="{y(max(r.open,r.close))}" width="6" height="{max(1,y(min(r.open,r.close))-y(max(r.open,r.close)))}" fill="{color}"/>')
        if i == start or frame.index[i].month != frame.index[i-1].month:
            svg.append(f'<text x="{x(i)}" y="470" fill="#9caec2" font-size="13">{frame.index[i]:%m-%d}</text>')
    descriptions = []
    for h in hits:
        for points in [h.points, h.points2]:
            (a, av), (b, bv) = points
            svg.append(f'<path d="M{x(a)} {y(av)}L{x(b)} {y(bv)}" fill="none" stroke="#f6cf65" stroke-width="2.5"/>')
        for i, value in h.touch_points:
            svg.append(f'<circle cx="{x(i)}" cy="{y(value)}" r="5" fill="#0d141e" stroke="#f6cf65" stroke-width="2"/>')
        if h.completed_at is not None:
            i = h.completed_at
            svg.append(f'<path d="M{x(i)} 35V445" stroke="#69e7c3" stroke-dasharray="5 5"/><text x="{x(i)-90}" y="25" fill="#69e7c3" font-size="14">{frame.index[i]:%m/%d} 하단 이탈 확정</text>')
        a,b=h.structure_span
        descriptions.append(f'구조 {frame.index[a]:%m/%d}–{frame.index[b]:%m/%d} · 접점 {len(h.touch_points)}개 · 인식 {frame.index[h.confirmed_at]:%m/%d}')
    return ''.join(svg) + '</svg><p>' + (' / '.join(descriptions) or '이 구간의 상승 확대 쐐기 탐지 없음') + '</p>'

out = ROOT / '_workspace/broadening-review.html'
out.parent.mkdir(exist_ok=True)
out.write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>확대 쐐기 변경 전후</title><style>body{background:#0d141e;color:#e4edf7;font:16px system-ui;max-width:1250px;margin:32px auto;padding:0 24px}section{border:1px solid #304052;border-radius:12px;padding:20px;margin:24px 0}svg{width:100%}p{color:#b8c8da;line-height:1.7}h2{font-size:20px}</style><h1>SK하이닉스 · 확대 쐐기 확인</h1><p>저장된 일봉 데이터 · 2026년 4–7월 · 노란 선: 추세선 / 원: 접점 / 초록 점선: 이탈 확정일<br>운영 사이트에 배포하지 않은 로컬 비교입니다. 선은 실제 탐지 결과이며 이탈 이후 다시 맞추지 않습니다.</p>'''
    + '<section><h2>변경 전</h2>' + chart(baseline['detect_trendline_patterns']) + '</section>'
    + '<section><h2>변경 후</h2>' + chart(trend.detect_trendline_patterns) + '</section></html>', encoding='utf-8')
print(out)
