// 차트 위 사용자 그리기: 가로선 / 추세선(빗금) / 박스. 종목·타임프레임별 localStorage 보관.
// 가로선은 series.createPriceLine으로, 추세선·박스는 시리즈 프리미티브(캔버스 draw)로 그린다.
import type { Time } from "lightweight-charts";

export type Drawing =
  | { id: string; type: "hline"; price: number }
  | { id: string; type: "trend"; t1: number; p1: number; t2: number; p2: number }
  | { id: string; type: "box"; t1: number; p1: number; t2: number; p2: number };

export type DrawTool = "none" | "hline" | "trend" | "box";

export const DRAW_COLOR = "#7c3aed"; // 보라 — 지표선과 확실히 구분

const keyOf = (code: string, tf: string) => `draw:${code}:${tf}`;

export function loadDrawings(code: string, tf: string): Drawing[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(keyOf(code, tf)) ?? "[]") as Drawing[];
  } catch {
    return [];
  }
}

export function saveDrawings(code: string, tf: string, d: Drawing[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(keyOf(code, tf), JSON.stringify(d));
}

/* eslint-disable @typescript-eslint/no-explicit-any */
// 추세선/박스 하나를 그리는 시리즈 프리미티브. (가로선은 createPriceLine이 담당)
export function makeDrawPrimitive(d: Drawing, color: string) {
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
          zOrder: () => "top" as const,
          renderer: () => ({
            draw(target: any) {
              if (d.type === "hline" || !series || !chart) return;
              target.useMediaCoordinateSpace((scope: any) => {
                const ctx = scope.context as CanvasRenderingContext2D;
                const tscale = chart.timeScale();
                const x1 = tscale.timeToCoordinate(d.t1 as unknown as Time);
                const x2 = tscale.timeToCoordinate(d.t2 as unknown as Time);
                const y1 = series.priceToCoordinate(d.p1);
                const y2 = series.priceToCoordinate(d.p2);
                if (x1 == null || x2 == null || y1 == null || y2 == null) return;
                ctx.save();
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.5;
                if (d.type === "trend") {
                  ctx.beginPath();
                  ctx.moveTo(x1, y1);
                  ctx.lineTo(x2, y2);
                  ctx.stroke();
                } else {
                  const x = Math.min(x1, x2);
                  const y = Math.min(y1, y2);
                  const w = Math.abs(x2 - x1);
                  const h = Math.abs(y2 - y1);
                  ctx.fillStyle = color + "1f";
                  ctx.fillRect(x, y, w, h);
                  ctx.strokeRect(x, y, w, h);
                }
                ctx.restore();
              });
            },
          }),
        },
      ];
    },
  };
}
