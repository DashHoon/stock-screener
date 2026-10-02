"""Generate a local before/after review from the Sunic regression fixture."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from batch.patterns import detect_all_patterns
import batch.patterns.trend as trend
from batch.tests.test_ascending_triangle_real import candles, append_candle
from batch.patterns.swing import build_ctx


def panel(df, hits, title):
    start = next(i for i, date in enumerate(df.date) if date >= '2026-07-20')
    hits = [h for h in hits if h.kind == 'pat_tri_asc' and h.structure_span[0] >= start]
    x = lambda i: 65 + (i-start)*830/(len(df)-start-1)
    y = lambda value: 320-(value-42000)*270/42000
    svg = ['<svg viewBox="0 0 1000 365" role="img" aria-label="선익시스템 일봉과 상승 삼각형">']
    for price in (50000, 60000, 70000, 80000):
        svg.append(f'<path d="M55 {y(price)}H905" stroke="#263648"/><text x="915" y="{y(price)+5}" fill="#aebdcd">{price:,}</text>')
    for i in range(start, len(df)):
        r = df.iloc[i]
        color = '#f1767e' if r.close >= r.open else '#6badff'
        svg.append(f'<path d="M{x(i)} {y(r.high)}V{y(r.low)}" stroke="{color}"/><rect x="{x(i)-3}" y="{y(max(r.open,r.close))}" width="6" height="{max(1,y(min(r.open,r.close))-y(max(r.open,r.close)))}" fill="{color}"/>')
        if (i-start) % 10 == 0:
            svg.append(f'<text x="{x(i)-15}" y="350" fill="#aebdcd">{r.date[5:]}</text>')
    notes = []
    for h in hits:
        for points in (h.points, h.points2):
            (a, av), (b, bv) = points
            svg.append(f'<path d="M{x(a)} {y(av)}L{x(b)} {y(bv)}" stroke="#f6d26a" stroke-width="2"/>')
        for i, value in h.touch_points:
            svg.append(f'<circle cx="{x(i)}" cy="{y(value)}" r="4" fill="#111923" stroke="#f6d26a"/>')
        state = '형성 중' if h.forming else '돌파 확정'
        notes.append(f'{state} · 저항 {h.neckline:,.0f}원 · 최초 인식 {df.date.iloc[h.confirmed_at]} · 접점 {len(h.touch_points)}개')
    return f'<section><h2>{title}</h2>'+''.join(svg)+'</svg><p>'+(' / '.join(notes) or '상승 삼각형 탐지 없음')+'</p></section>'


def main():
    df = candles()
    baseline = dict(trend.__dict__)
    source = subprocess.check_output(['git', 'show', '6e85d304e:batch/patterns/trend.py'], cwd=ROOT, text=True)
    exec(compile(source, '<baseline>', 'exec'), baseline)
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>선익시스템 상승 삼각형 개선</title><style>body{background:#10151e;color:#e1eaf5;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 24px}section{border:1px solid #304258;border-radius:12px;padding:18px;margin:20px 0}svg{width:100%}p{color:#b3c4d9;line-height:1.7}h2{font-size:20px}strong{color:#f6d26a}</style><h1>선익시스템 · 상승 삼각형 누락 개선</h1><p>실제 일봉: 2026-09-30까지 · 마지막 종가 69,700원<br>노란 선과 원은 탐지한 경계와 접점입니다. 현재는 저항선 아래이므로 <strong>형성 중</strong>입니다.<br>로컬 검토용이며 운영 배포 전입니다.</p>'''
    html += panel(df, baseline['detect_trendline_patterns'](df), '변경 전 · 실제 데이터')
    html += panel(df, detect_all_patterns(df), '변경 후 · 실제 데이터')
    atr = build_ctx(df).atr[-1]
    tail = append_candle(df, 74200 + .8*atr)
    tail = append_candle(tail, 74200 + .8*atr)
    tail.loc[len(tail)-2:, 'date'] = ['2026-10-01', '2026-10-02']
    html += panel(tail, detect_all_patterns(tail), '확인용 가상 예시 · 이후 두 종가가 저항선을 넘으면 돌파 확정')
    html += '<p>마지막 예시의 추가 2개 봉은 실제 시세나 예측이 아닌 테스트 데이터입니다. 기존 선을 고정한 채 돌파 여부만 확인합니다.</p></html>'
    out = ROOT/'_workspace/sunic-triangle-review.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
