// 볼린저밴드 상·하단 사이를 옅게 채우는 시리즈 프리미티브.
// lightweight-charts에는 두 선 사이를 칠하는 기능이 없어 캔버스에 직접 그린다.
// zOrder 'bottom' — 캔들·지표선 아래에 깔려 가독성을 해치지 않는다.
import type { Time } from "lightweight-charts";

export const BAND_FILL = "rgba(250, 204, 21, 0.13)"; // 옅은 노랑

/* eslint-disable @typescript-eslint/no-explicit-any */
export function makeBandFill(
  dates: string[],
  upper: (number | null)[],
  lower: (number | null)[],
  toTime: (d: string) => Time,
  color = BAND_FILL,
) {
  let series: any = null;
  let chart: any = null;
  return {
    attached(p: { series: any; chart: any }) {
      series = p.series;
      chart = p.chart;
    },
    detached() {
      series = null;
      chart = null;
    },
    updateAllViews() {},
    paneViews() {
      return [
        {
          zOrder: () => "bottom" as const,
          renderer: () => ({
            draw(target: any) {
              if (!series || !chart) return;
              target.useMediaCoordinateSpace((scope: any) => {
                const ctx = scope.context as CanvasRenderingContext2D;
                const tscale = chart.timeScale();
                // 상단은 왼→오른쪽, 하단은 오른→왼쪽으로 이어 하나의 닫힌 영역을 만든다.
                // null 구간(지표 워밍업 등)에서 끊어 별도 영역으로 칠한다.
                let top: { x: number; y: number }[] = [];
                let bot: { x: number; y: number }[] = [];
                const flush = () => {
                  if (top.length < 2) {
                    top = [];
                    bot = [];
                    return;
                  }
                  ctx.beginPath();
                  ctx.moveTo(top[0].x, top[0].y);
                  for (const p of top.slice(1)) ctx.lineTo(p.x, p.y);
                  for (const p of [...bot].reverse()) ctx.lineTo(p.x, p.y);
                  ctx.closePath();
                  ctx.fillStyle = color;
                  ctx.fill();
                  top = [];
                  bot = [];
                };
                for (let i = 0; i < dates.length; i++) {
                  const u = upper[i];
                  const l = lower[i];
                  if (u == null || l == null) {
                    flush();
                    continue;
                  }
                  const x = tscale.timeToCoordinate(toTime(dates[i]));
                  const yu = series.priceToCoordinate(u);
                  const yl = series.priceToCoordinate(l);
                  if (x == null || yu == null || yl == null) {
                    flush();
                    continue;
                  }
                  top.push({ x, y: yu });
                  bot.push({ x, y: yl });
                }
                flush();
              });
            },
          }),
        },
      ];
    },
  };
}
