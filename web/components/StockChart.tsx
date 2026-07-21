"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { ChartData } from "@/lib/types";

const DIV_LABEL: Record<string, string> = {
  div_reg_bull: "상승 다이버전스",
  div_reg_bear: "하락 다이버전스",
  div_hid_bull: "히든 상승",
  div_hid_bear: "히든 하락",
};

function ts(date: string): UTCTimestamp {
  return (Date.parse(date) / 1000) as UTCTimestamp;
}

function lineData(dates: string[], values: (number | null)[]) {
  const out: { time: UTCTimestamp; value: number }[] = [];
  for (let i = 0; i < dates.length; i++) {
    const v = values[i];
    if (v != null) out.push({ time: ts(dates[i]), value: v });
  }
  return out;
}

export default function StockChart({ data }: { data: ChartData }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const css = getComputedStyle(document.documentElement);
    const color = {
      fg: css.getPropertyValue("--fg").trim(),
      muted: css.getPropertyValue("--muted").trim(),
      border: css.getPropertyValue("--border").trim(),
      up: css.getPropertyValue("--up").trim(),
      down: css.getPropertyValue("--down").trim(),
      accent: css.getPropertyValue("--accent").trim(),
    };

    const chart = createChart(el, {
      height: 620,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: color.muted,
        panes: { separatorColor: color.border, enableResize: false },
      },
      grid: {
        vertLines: { color: color.border, style: 1 },
        horzLines: { color: color.border, style: 1 },
      },
      rightPriceScale: { borderColor: color.border },
      timeScale: { borderColor: color.border },
      crosshair: { mode: 0 },
      autoSize: false,
    });

    // pane 0: 캔들 + 볼린저밴드
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: color.up,
      downColor: color.down,
      borderUpColor: color.up,
      borderDownColor: color.down,
      wickUpColor: color.up,
      wickDownColor: color.down,
    });
    candles.setData(
      data.dates.map((d, i) => ({
        time: ts(d),
        open: data.open[i],
        high: data.high[i],
        low: data.low[i],
        close: data.close[i],
      })),
    );

    const bbStyle = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false };
    chart
      .addSeries(LineSeries, { color: color.muted, ...bbStyle })
      .setData(lineData(data.dates, data.bb_upper));
    chart
      .addSeries(LineSeries, { color: color.border, ...bbStyle })
      .setData(lineData(data.dates, data.bb_mid));
    chart
      .addSeries(LineSeries, { color: color.muted, ...bbStyle })
      .setData(lineData(data.dates, data.bb_lower));

    // 다이버전스 마커 (두 번째 피벗 날짜에 표식)
    const markers: SeriesMarker<Time>[] = data.divergences.map((dv) => {
      const bull = dv.kind.endsWith("bull");
      return {
        time: ts(dv.date_to),
        position: bull ? "belowBar" : "aboveBar",
        color: bull ? color.up : color.down,
        shape: bull ? "arrowUp" : "arrowDown",
        text: DIV_LABEL[dv.kind],
      };
    });
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    createSeriesMarkers(candles, markers);

    // pane 1: 거래량
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      1,
    );
    volume.setData(
      data.dates.map((d, i) => ({
        time: ts(d),
        value: data.volume[i],
        color: data.close[i] >= data.open[i] ? color.up + "66" : color.down + "66",
      })),
    );

    // pane 2: RSI (30/70 기준선 포함)
    const rsiSeries = chart.addSeries(
      LineSeries,
      { color: color.accent, lineWidth: 2, priceLineVisible: false },
      2,
    );
    rsiSeries.setData(lineData(data.dates, data.rsi));
    for (const level of [30, 70]) {
      rsiSeries.createPriceLine({
        price: level,
        color: color.border,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: false,
        title: "",
      });
    }

    // pane 3: MACD
    const macdHist = chart.addSeries(
      HistogramSeries,
      { priceLineVisible: false, lastValueVisible: false },
      3,
    );
    macdHist.setData(
      lineData(data.dates, data.macd_hist).map((p) => ({
        ...p,
        color: p.value >= 0 ? color.up + "88" : color.down + "88",
      })),
    );
    chart
      .addSeries(LineSeries, { color: color.fg, lineWidth: 1, priceLineVisible: false }, 3)
      .setData(lineData(data.dates, data.macd));
    chart
      .addSeries(LineSeries, { color: color.accent, lineWidth: 1, priceLineVisible: false }, 3)
      .setData(lineData(data.dates, data.macd_signal));

    // pane 비율: 캔들 크게, 보조지표 작게
    const panes = chart.panes();
    if (panes.length >= 4) {
      panes[0].setStretchFactor(3);
      panes[1].setStretchFactor(0.8);
      panes[2].setStretchFactor(1);
      panes[3].setStretchFactor(1);
    }

    chart.timeScale().fitContent();

    const resize = () => chart.applyOptions({ width: el.clientWidth });
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [data]);

  return <div ref={ref} className="chart-wrap" />;
}
