"use client";

import { useEffect, useRef, useState } from "react";
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

// 이동평균선 기간·색 (범례와 공유)
const MA_DEFS = [
  { period: 5, color: "#f59e0b" },
  { period: 20, color: "#10b981" },
  { period: 60, color: "#8b5cf6" },
  { period: 120, color: "#64748b" },
];

const HEIGHTS = { md: 520, lg: 720, xl: 920 } as const;
type HeightKey = keyof typeof HEIGHTS;

const PERIODS: { label: string; days: number | null }[] = [
  { label: "1주", days: 7 },
  { label: "1M", days: 31 },
  { label: "3M", days: 92 },
  { label: "6M", days: 183 },
  { label: "1Y", days: 366 },
  { label: "전체", days: null },
];

interface Settings {
  height: HeightKey;
  div: boolean; // 다이버전스 화살표
  macdCross: boolean; // MACD 골든/데드 화살표
  ma: boolean; // 이동평균선
  bb: boolean; // 볼린저밴드
}

const DEFAULT_SETTINGS: Settings = {
  height: "lg",
  div: true,
  macdCross: true,
  ma: true,
  bb: true,
};

function loadSettings(): Settings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem("chartSettings") ?? "{}") };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

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

function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

/** MACD선-시그널선 교차 마커 (골든 ▲ / 데드 ▼) */
function macdCrossMarkers(
  data: ChartData,
  upColor: string,
  downColor: string,
): SeriesMarker<Time>[] {
  const out: SeriesMarker<Time>[] = [];
  for (let i = 1; i < data.dates.length; i++) {
    const m0 = data.macd[i - 1], s0 = data.macd_signal[i - 1];
    const m1 = data.macd[i], s1 = data.macd_signal[i];
    if (m0 == null || s0 == null || m1 == null || s1 == null) continue;
    if (m0 <= s0 && m1 > s1)
      out.push({ time: ts(data.dates[i]), position: "belowBar", color: upColor, shape: "arrowUp", text: "골든" });
    else if (m0 >= s0 && m1 < s1)
      out.push({ time: ts(data.dates[i]), position: "aboveBar", color: downColor, shape: "arrowDown", text: "데드" });
  }
  return out;
}

/** 패널 좌상단에 라벨 오버레이 부착. pane DOM은 늦게 생성되므로 잠시 재시도한다. */
function attachPaneLabels(
  panes: { getHTMLElement(): HTMLElement | null }[],
  texts: string[],
  tries = 10,
) {
  const pending: number[] = [];
  panes.forEach((pane, i) => {
    let el: HTMLElement | null = null;
    try {
      el = pane.getHTMLElement();
    } catch {
      return; // 차트가 이미 제거된 경우 (React StrictMode 재마운트)
    }
    if (!el) {
      pending.push(i);
      return;
    }
    if (el.querySelector(".pane-label")) return;
    const label = document.createElement("div");
    label.className = "pane-label";
    label.textContent = texts[i];
    el.style.position = "relative";
    el.appendChild(label);
  });
  if (pending.length && tries > 0) {
    setTimeout(
      () => attachPaneLabels(pending.map((i) => panes[i]), pending.map((i) => texts[i]), tries - 1),
      50,
    );
  }
}

export default function StockChart({ data }: { data: ChartData }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
    setReady(true);
  }, []);

  function update(patch: Partial<Settings>) {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      localStorage.setItem("chartSettings", JSON.stringify(next));
      return next;
    });
  }

  function setPeriod(days: number | null) {
    const chart = chartRef.current;
    if (!chart) return;
    if (days == null) {
      chart.timeScale().fitContent();
      return;
    }
    const last = data.dates[data.dates.length - 1];
    const from = new Date(Date.parse(last) - days * 86400_000);
    chart.timeScale().setVisibleRange({
      from: (from.getTime() / 1000) as UTCTimestamp,
      to: ts(last),
    });
  }

  useEffect(() => {
    if (!ready) return;
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
      height: HEIGHTS[settings.height],
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
      // 모바일 핀치줌/드래그 명시 활성화
      handleScale: {
        pinch: true,
        mouseWheel: true,
        axisPressedMouseMove: true,
      },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false, // 세로 스와이프는 페이지 스크롤에 양보
        pressedMouseMove: true,
        mouseWheel: true,
      },
      autoSize: false,
    });
    chartRef.current = chart;
    if (process.env.NODE_ENV !== "production") {
      (window as unknown as Record<string, unknown>).__chart = chart;
    }

    // pane 0: 캔들 + BB + 이평선
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

    const thin = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false };
    if (settings.bb) {
      chart.addSeries(LineSeries, { color: color.muted, ...thin })
        .setData(lineData(data.dates, data.bb_upper));
      chart.addSeries(LineSeries, { color: color.border, ...thin })
        .setData(lineData(data.dates, data.bb_mid));
      chart.addSeries(LineSeries, { color: color.muted, ...thin })
        .setData(lineData(data.dates, data.bb_lower));
    }
    if (settings.ma) {
      for (const { period, color: c } of MA_DEFS) {
        chart.addSeries(LineSeries, { color: c, ...thin })
          .setData(lineData(data.dates, sma(data.close, period)));
      }
    }

    // 다이버전스 마커
    if (settings.div) {
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
    }

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

    // pane 2: RSI + 30/70 기준선 (진하게)
    const rsiSeries = chart.addSeries(
      LineSeries,
      { color: color.accent, lineWidth: 2, priceLineVisible: false },
      2,
    );
    rsiSeries.setData(lineData(data.dates, data.rsi));
    for (const level of [30, 70]) {
      rsiSeries.createPriceLine({
        price: level,
        color: color.fg,
        lineWidth: 1,
        lineStyle: 0, // 실선
        axisLabelVisible: true,
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
    const macdLine = chart.addSeries(
      LineSeries,
      { color: color.fg, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
      3,
    );
    macdLine.setData(lineData(data.dates, data.macd));
    chart.addSeries(
      LineSeries,
      { color: color.accent, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
      3,
    ).setData(lineData(data.dates, data.macd_signal));

    if (settings.macdCross) {
      createSeriesMarkers(macdLine, macdCrossMarkers(data, color.up, color.down));
    }

    // pane 비율
    const panes = chart.panes();
    if (panes.length >= 4) {
      panes[0].setStretchFactor(3);
      panes[1].setStretchFactor(0.8);
      panes[2].setStretchFactor(1);
      panes[3].setStretchFactor(1);
    }

    // 폭 0(숨김 탭·레이아웃 미확정)으로 만들어진 차트는 폭이 생기는 순간
    // 전체 구간을 다시 맞춰야 한다 → 폭이 0→양수로 바뀔 때 fitContent 재실행
    let fitted = false;
    const resize = () => {
      const w = el.clientWidth;
      chart.applyOptions({ width: w });
      if (w > 0 && !fitted) {
        fitted = true;
        chart.timeScale().fitContent();
        const ps = chart.panes();
        if (ps.length >= 4) {
          attachPaneLabels(
            [ps[1], ps[2], ps[3]],
            ["거래량", "RSI (14)", "MACD (12,26,9)"],
          );
        }
      }
    };
    resize();
    requestAnimationFrame(resize);
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, settings, ready]);

  return (
    <div>
      <div className="chart-toolbar">
        <div className="toolbar-group">
          {PERIODS.map((p) => (
            <button key={p.label} type="button" onClick={() => setPeriod(p.days)}>
              {p.label}
            </button>
          ))}
        </div>
        <div className="toolbar-group">
          <span className="toolbar-label">높이</span>
          {(["md", "lg", "xl"] as HeightKey[]).map((h) => (
            <button
              key={h}
              type="button"
              className={settings.height === h ? "on" : ""}
              onClick={() => update({ height: h })}
            >
              {h === "md" ? "보통" : h === "lg" ? "크게" : "최대"}
            </button>
          ))}
        </div>
        <div className="toolbar-group toggles">
          {(
            [
              ["div", "다이버전스"],
              ["macdCross", "MACD 크로스"],
              ["ma", "이평선"],
              ["bb", "볼린저"],
            ] as [keyof Settings, string][]
          ).map(([key, label]) => (
            <label key={key} className={`toolbar-toggle${settings[key] ? " on" : ""}`}>
              <input
                type="checkbox"
                checked={settings[key] as boolean}
                onChange={(e) => update({ [key]: e.target.checked })}
              />
              {label}
            </label>
          ))}
        </div>
        {settings.ma && (
          <div className="toolbar-group ma-legend">
            {MA_DEFS.map((m) => (
              <span key={m.period} style={{ color: m.color }}>
                MA{m.period}
              </span>
            ))}
          </div>
        )}
      </div>
      <div ref={ref} className="chart-wrap" />
    </div>
  );
}
