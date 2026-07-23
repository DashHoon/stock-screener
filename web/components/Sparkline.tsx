"use client";

/** 경량 SVG 스파크라인. 무거운 차트 라이브러리 대신 polyline 하나. */
export default function Sparkline({
  data,
  width = 72,
  height = 24,
}: {
  data: number[] | undefined;
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) return <span className="spark-empty">-</span>;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const n = data.length;
  const pts = data
    .map((v, i) => {
      const x = (i / (n - 1)) * (width - 2) + 1;
      const y = height - 1 - ((v - min) / span) * (height - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = data[n - 1] >= data[0];
  const color = up ? "var(--up)" : "var(--down)";
  return (
    <svg
      className="spark"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden
    >
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.3"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
