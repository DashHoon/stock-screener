/** 20일 종가 스파크라인. **캔버스가 아니라 SVG로 그린다** — 캔버스는 크롤러에게
 *  빈 사각형이라, 예전 종목 페이지가 색인되지 못한 이유 중 하나였다. */
export default function Spark({ values, up }: { values: number[]; up: boolean }) {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${28 - ((v - lo) / span) * 26}`)
    .join(" ");
  return (
    <svg className="spark" viewBox="0 0 100 30" preserveAspectRatio="none"
         role="img" aria-label={`최근 ${values.length}거래일 종가 흐름`}>
      <polyline points={pts} fill="none" strokeWidth="1.8"
                stroke={up ? "var(--up)" : "var(--down)"}
                vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
