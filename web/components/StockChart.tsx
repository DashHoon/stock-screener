"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type LogicalRange,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { FLAG_BY_KEY } from "@/lib/flags";
import type { FlagMeta } from "@/lib/flags";
import FlagInfoModal from "@/components/FlagInfoModal";
import { makeBandFill } from "@/components/bandFill";
import type { ChartData, FlagKey, TimeframeData, TimeframeKey } from "@/lib/types";

const DIV_LABEL: Record<string, string> = {
  div_reg_bull: "상승 다이버전스",
  div_reg_bear: "하락 다이버전스",
  div_hid_bull: "히든 상승",
  div_hid_bear: "히든 하락",
};

// 패턴 kind별 [완성 라벨, 형성중 라벨, 차트칩 짧은라벨]
const PATTERN_LABEL: Record<string, [string, string, string]> = {
  pat_double_bottom: ["쌍바닥 돌파", "쌍바닥 형성중", "쌍바닥"],
  pat_double_top: ["더블탑 붕괴", "더블탑 형성중", "더블탑"],
  pat_cup_handle: ["컵앤핸들 돌파", "컵앤핸들 형성중", "컵핸들"],
  pat_hs_top: ["헤드앤숄더 붕괴", "H&S 형성중", "H&S"],
  pat_hs_inv: ["역헤드앤숄더 돌파", "역H&S 형성중", "역H&S"],
  pat_triple_bottom: ["3중바닥 돌파", "3중바닥 형성중", "3중바닥"],
  pat_triple_top: ["트리플탑 붕괴", "트리플탑 형성중", "트리플탑"],
  pat_round_bottom: ["라운드바텀 돌파", "라운드바텀 형성중", "라운드바텀"],
  pat_round_top: ["라운드탑 이탈", "라운드탑 형성중", "라운드탑"],
  pat_tri_asc: ["상승삼각형 돌파", "상승삼각형 형성중", "상승삼각"],
  pat_tri_desc: ["하락삼각형 이탈", "하락삼각형 형성중", "하락삼각"],
  pat_tri_sym: ["삼각수렴", "삼각수렴 형성중", "삼각수렴"],
  pat_tri_sym_up: ["삼각수렴 상향 돌파", "삼각수렴 형성중", "수렴↑"],
  pat_tri_sym_down: ["삼각수렴 하향 이탈", "삼각수렴 형성중", "수렴↓"],
  pat_wedge_rise: ["상승쐐기 이탈", "상승쐐기 형성중", "상승쐐기"],
  pat_wedge_fall: ["하락쐐기 돌파", "하락쐐기 형성중", "하락쐐기"],
  pat_flag_bull: ["상승플래그 돌파", "상승플래그 형성중", "상승플래그"],
  pat_flag_bear: ["하락플래그 이탈", "하락플래그 형성중", "하락플래그"],
  pat_broadening: ["브로드닝 이탈", "브로드닝 형성중", "브로드닝"],
  pat_diamond: ["다이아몬드 이탈", "다이아몬드 형성중", "다이아몬드"],
};

const BULL_KINDS = new Set([
  "pat_double_bottom", "pat_cup_handle", "pat_hs_inv", "pat_triple_bottom",
  "pat_round_bottom", "pat_wedge_fall", "pat_tri_asc", "pat_tri_sym_up",
  "pat_tri_sym", "pat_flag_bull",
]);

// 캔들 패턴 표시 순서 (상승 → 하락 → 중립).
// 라벨·방향·설명 메타는 flags.ts를 캔들·차트패턴 공용으로 쓴다
const CDL_ORDER = [
  "cdl_engulf_bull", "cdl_hammer", "cdl_pierce", "cdl_morning",
  "cdl_engulf_bear", "cdl_shooting", "cdl_darkcloud", "cdl_evening",
  "cdl_doji",
];
function flagMeta(kind: string): FlagMeta | undefined {
  return FLAG_BY_KEY.get(kind as FlagKey);
}

// 이동평균선 기간·색 (봉 개수 기준 — 주봉이면 N주, 월봉이면 N개월 평균)
const MA_DEFS = [
  { period: 5, color: "#f59e0b" },
  { period: 20, color: "#10b981" },
  { period: 60, color: "#8b5cf6" },
  { period: 120, color: "#64748b" },
];

// 일봉 첫 진입 시 보여줄 봉 수 (최근 100거래일)
const INITIAL_DAILY_BARS = 100;

// 기본으로 켜둘 패턴 종류 수. 실측상 대부분 1~3종류라 그대로 보이고,
// 드물게 많이 잡힌 종목만 자동으로 접힌다 (칩을 눌러 언제든 켤 수 있음).
const DEFAULT_PATTERN_KINDS = 3;

const HEIGHTS = { md: 520, lg: 720, xl: 920 } as const;
type HeightKey = keyof typeof HEIGHTS;

const TF_LABEL: Record<TimeframeKey, string> = { d: "일봉", w: "주봉", m: "월봉" };

// 타임프레임별 기간 버튼 (days=null → 전체)
const TF_PERIODS: Record<TimeframeKey, { label: string; days: number | null }[]> = {
  d: [
    { label: "1주", days: 7 },
    { label: "1M", days: 31 },
    { label: "3M", days: 92 },
    { label: "6M", days: 183 },
    { label: "1Y", days: 366 },
    { label: "전체", days: null },
  ],
  w: [
    { label: "1Y", days: 366 },
    { label: "3Y", days: 1096 },
    { label: "5Y", days: 1827 },
    { label: "전체", days: null },
  ],
  m: [
    { label: "5Y", days: 1827 },
    { label: "전체", days: null },
  ],
};

interface Settings {
  height: HeightKey;
  chartType: "candle" | "line"; // 가격 표시 방식
  div: boolean;
  macdCross: boolean;
  ma: boolean;
  bb: boolean;
  pattern: boolean; // 차트 패턴 (쌍바닥/더블탑) 마킹
  candle: boolean; // 단기 캔들 패턴 (장악형 등) 마킹
}

// 첫 진입 기본값: 이평선만 켬. 나머지 표시는 사용자가 필요할 때 직접 켜도록 둔다
// (한꺼번에 다 켜져 있으면 캔들이 마커·선에 묻혀 차트가 읽히지 않는다).
// 한 번 바꾼 설정은 localStorage에 남아 다음 방문에도 유지된다.
const DEFAULT_SETTINGS: Settings = {
  height: "lg",
  chartType: "candle",
  div: false,
  macdCross: false,
  ma: true,
  bb: false,
  pattern: false,
  candle: false,
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
  data: TimeframeData,
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

interface PaneLabelSpec {
  text: string;
  infoKey?: string; // 있으면 라벨 옆 ⓘ 버튼 표시
}

// 지표 개념 설명 (패널 ⓘ 클릭 시)
const INDICATOR_INFO: Record<string, { title: string; desc: string }> = {
  rsi: {
    title: "RSI (상대강도지수, 14)",
    desc: "최근 14일간 오른 폭과 내린 폭을 비교해 0~100으로 나타낸 모멘텀 지표입니다. 70 이상이면 과매수(단기 과열), 30 이하면 과매도(단기 침체)로 봅니다. 가격은 신고점인데 RSI는 낮아지는 식으로 둘이 엇갈리는 '다이버전스'는 추세 반전 신호로 자주 쓰입니다.",
  },
  macd: {
    title: "MACD (이동평균수렴확산, 12·26·9)",
    desc: "단기(12일)·장기(26일) 지수이동평균의 차이가 MACD선, 그 9일 평균이 시그널선입니다. MACD선이 시그널선을 아래→위로 뚫으면 골든크로스(상승 전환), 위→아래로 뚫으면 데드크로스(하락 전환) 신호입니다. 막대(히스토그램)는 두 선의 간격이고, 0선 위/아래로 중기 추세 방향을 봅니다.",
  },
  divergence: {
    title: "다이버전스 (Divergence)",
    desc: "가격과 RSI의 고·저점 방향이 서로 엇갈리는 현상입니다. 가격은 저점을 더 낮췄는데 RSI 저점은 오히려 높아지면(상승 다이버전스) 하락 힘이 약해져 반등 가능성이 커집니다. 반대로 가격 고점은 높은데 RSI 고점이 낮아지면(하락 다이버전스) 상승 동력이 꺼지는 신호입니다. 추세 반전을 미리 포착하는 데 씁니다. 차트에는 발생 구간을 화살표로 표시합니다.",
  },
  bollinger: {
    title: "볼린저밴드 (Bollinger Band, 20·2)",
    desc: "20일 이동평균선(가운데)을 중심으로 표준편차의 2배만큼 위·아래에 그린 띠입니다. 가격의 약 95%가 이 띠 안에서 움직여, 상단 터치는 단기 과열, 하단 터치는 단기 침체로 봅니다. 띠 폭이 좁아지는 '스퀴즈'는 변동성이 줄었다가 곧 크게 움직일 신호이고, 폭이 벌어지면 추세가 강해지는 것으로 해석합니다.",
  },
  ma: {
    title: "이동평균선 (MA)",
    desc: "일정 기간 종가의 평균을 이은 선입니다. MA5(5일)·MA20(20일)·MA60(60일)·MA120(120일)을 함께 봅니다. 주가가 이평선 위에 있으면 상승 추세, 아래면 하락 추세로 보고, 이평선은 지지·저항 역할도 합니다. 단기선이 장기선을 아래→위로 뚫으면 골든크로스(상승), 위→아래로 뚫으면 데드크로스(하락) 신호입니다.",
  },
  volume: {
    title: "거래량 (Volume)",
    desc: "하루 동안 거래된 주식 수입니다. 가격 움직임에 거래량이 실리면(급등·급락 시 거래량 급증) 그 움직임의 신뢰도가 높다고 봅니다. 거래량 없는 상승은 힘이 약할 수 있고, 바닥에서 거래량이 크게 터지면 추세 전환 신호가 되기도 합니다. 막대의 빨강은 상승 마감일, 파랑은 하락 마감일의 거래량입니다.",
  },
};

// 툴바 토글(다이버전스·볼린저·이평선) → 설명 키
const TOGGLE_INFO: Partial<Record<keyof Settings, string>> = {
  div: "divergence",
  bb: "bollinger",
  ma: "ma",
};

/** 패널 좌상단에 라벨 오버레이 부착. pane DOM은 늦게 생성되므로 잠시 재시도한다. */
function attachPaneLabels(
  panes: { getHTMLElement(): HTMLElement | null }[],
  specs: PaneLabelSpec[],
  onInfo?: (key: string) => void,
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
    const span = document.createElement("span");
    span.textContent = specs[i].text;
    label.appendChild(span);
    const key = specs[i].infoKey;
    if (key && onInfo) {
      const info = document.createElement("button");
      info.type = "button";
      info.className = "pane-info";
      info.textContent = "ⓘ";
      info.setAttribute("aria-label", `${specs[i].text} 설명`);
      info.addEventListener("click", (e) => {
        e.stopPropagation();
        onInfo(key);
      });
      label.appendChild(info);
    }
    el.style.position = "relative";
    el.appendChild(label);
  });
  if (pending.length && tries > 0) {
    setTimeout(
      () =>
        attachPaneLabels(
          pending.map((i) => panes[i]),
          pending.map((i) => specs[i]),
          onInfo,
          tries - 1,
        ),
      50,
    );
  }
}

export default function StockChart({ data }: { data: ChartData }) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  // 토글/높이 변경으로 차트를 재생성할 때 확대 범위를 유지하기 위한 보관용.
  // 종목·타임프레임이 그대로일 때만 복원한다(바뀌면 시간축이 달라 무의미).
  const savedRangeRef = useRef<LogicalRange | null>(null);
  const prevViewRef = useRef<string | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [tfKey, setTfKey] = useState<TimeframeKey>("d");
  const [hiddenPat, setHiddenPat] = useState<Set<string>>(new Set());
  const [hiddenCdl, setHiddenCdl] = useState<Set<string>>(new Set());
  const [infoFlag, setInfoFlag] = useState<FlagMeta | null>(null); // ⓘ 설명 팝오버
  const [infoInd, setInfoInd] = useState<{ title: string; desc: string } | null>(null); // 지표 설명
  const [ready, setReady] = useState(false);
  const [showAmbiguous, setShowAmbiguous] = useState(false); // C등급(모호한 형태)까지 표시
  const [moreOpen, setMoreOpen] = useState(false); // 모바일 차트 설정 펼침 (데스크톱은 항상 펼침)
  const [themeTick, setThemeTick] = useState(0); // 테마 전환 시 차트 재생성용
  // 스크리너에서 패턴 조건으로 걸러 들어온 경우(?pat=...) 그 패턴은 무조건 보여준다
  // — 기본 패턴 OFF·C등급 숨김·최근 3종 제한을 모두 무시 (아니면 '검색엔 나오는데
  //   차트엔 안 보이는' 불일치가 생긴다). 세션 한정이며 localStorage엔 저장하지 않는다.
  const [highlightPats, setHighlightPats] = useState<Set<string>>(new Set());

  const current: TimeframeData = data.tf[tfKey] ?? data.tf.d;
  const availableTfs = (["d", "w", "m"] as TimeframeKey[]).filter((k) => data.tf[k]);
  // 현재 차트에 실제로 그려질 패턴 종류들 (겹침 정리용 개별 토글 대상).
  // C등급을 숨긴 상태면 칩도 함께 감춰야 '켜져 있는데 안 그려지는' 혼란이 없다.
  const patternKinds = [
    ...new Set(
      (current.patterns ?? [])
        .filter((p) => showAmbiguous || p.grade !== "C" || highlightPats.has(p.kind))
        .map((p) => p.kind),
    ),
  ];
  // 캔들 패턴 종류 (발생 있는 것만, 상승→하락→중립 순)
  const candleKinds = CDL_ORDER.filter((k) => current.candles?.[k]?.length);

  useEffect(() => {
    setSettings(loadSettings());
    setReady(true);
    // 차트는 CSS 변수 색을 캔버스에 굽기 때문에 테마가 바뀌면 다시 그려야 한다
    const onTheme = () => setThemeTick((v) => v + 1);
    window.addEventListener("themechange", onTheme);
    return () => window.removeEventListener("themechange", onTheme);
  }, []);

  // ?pat=pat_double_top,... 파싱 — 해당 패턴 강제 표시 + 패턴 토글 켜기(저장 안 함)
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("pat");
    if (!raw) return;
    const kinds = raw
      .split(",")
      .map((k) => k.replace(/_form$/, ""))
      .filter((k) => k.startsWith("pat_"));
    if (!kinds.length) return;
    setHighlightPats(new Set(kinds));
    setSettings((prev) => (prev.pattern ? prev : { ...prev, pattern: true }));
  }, []);

  // 종목·타임프레임이 바뀌면 '최근 것 위주'로 기본 표시를 다시 잡는다.
  // 형성 중 → 최근 완성 순으로 DEFAULT_PATTERN_KINDS 종류만 켜고 나머지는 접는다.
  useEffect(() => {
    const pats = (data.tf[tfKey] ?? data.tf.d).patterns ?? [];
    const recentFirst = [...pats].sort((a, b) =>
      (b.forming ? "9999-99-99" : (b.completed_date ?? "")).localeCompare(
        a.forming ? "9999-99-99" : (a.completed_date ?? ""),
      ),
    );
    const keep = new Set<string>(highlightPats); // 스크리너에서 걸러 온 패턴은 항상 표시
    for (const p of recentFirst) {
      if (keep.size >= DEFAULT_PATTERN_KINDS && !keep.has(p.kind)) break;
      keep.add(p.kind);
    }
    setHiddenPat(
      new Set(pats.map((p) => p.kind).filter((k) => !keep.has(k))),
    );
  }, [data, tfKey, highlightPats]);

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
    const last = current.dates[current.dates.length - 1];
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
      band: css.getPropertyValue("--band-fill").trim(),
    };

    // 좁은 화면에서는 축 글자를 줄인다. 가격축 폭은 라벨 텍스트 크기로 정해지는데,
    // 375px 화면에서 축이 86px(전체의 25%)을 가져가 캔들 영역이 254px밖에 안 됐다.
    const narrow = el.clientWidth < 420;

    const chart = createChart(el, {
      height: HEIGHTS[settings.height],
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: color.muted,
        fontSize: narrow ? 10 : 12,
        panes: { separatorColor: color.border, enableResize: false },
      },
      grid: {
        vertLines: { color: color.border, style: 1 },
        horzLines: { color: color.border, style: 1 },
      },
      rightPriceScale: { borderColor: color.border },
      timeScale: { borderColor: color.border },
      crosshair: { mode: 0 },
      handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true },
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

    // 가격축 라벨 포맷. 기본값은 "440000.00"처럼 소수점을 붙여, 모바일에서 가격축이
    // 화면 폭의 45%를 잡아먹었다 (375px 실측). 국내주가는 정수이므로 천단위 구분만 쓴다.
    // 지수(코스피 2,800.45)처럼 작은 값은 소수 2자리를 남긴다.
    const priceFormat = {
      type: "custom" as const,
      minMove: 0.01,
      formatter: (p: number) =>
        Math.abs(p) >= 1000
          ? Math.round(p).toLocaleString("ko-KR")
          : p.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    };

    // pane 0: 캔들 + BB + 이평선
    // 가격 시리즈 — 캔들 또는 라인(종가). 마커·넥라인·밴드 채움은 모두 이 시리즈에 붙는다.
    let candles;
    if (settings.chartType === "line") {
      candles = chart.addSeries(LineSeries, {
        color: color.accent,
        lineWidth: 2,
        priceLineVisible: true,
        priceFormat,
      });
      candles.setData(
        current.dates.map((d, i) => ({ time: ts(d), value: current.close[i] })),
      );
    } else {
      candles = chart.addSeries(CandlestickSeries, {
        priceFormat,
        upColor: color.up,
        downColor: color.down,
        borderUpColor: color.up,
        borderDownColor: color.down,
        wickUpColor: color.up,
        wickDownColor: color.down,
      });
      candles.setData(
        current.dates.map((d, i) => ({
          time: ts(d),
          open: current.open[i],
          high: current.high[i],
          low: current.low[i],
          close: current.close[i],
        })),
      );
    }

    const thin = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false };
    if (settings.bb) {
      // 밴드 내부를 옅은 노랑으로 채워 상·하단 범위를 한눈에 보이게 한다
      candles.attachPrimitive(
        makeBandFill(current.dates, current.bb_upper, current.bb_lower, ts, color.band || undefined),
      );
      chart.addSeries(LineSeries, { color: color.muted, ...thin })
        .setData(lineData(current.dates, current.bb_upper));
      chart.addSeries(LineSeries, { color: color.border, ...thin })
        .setData(lineData(current.dates, current.bb_mid));
      chart.addSeries(LineSeries, { color: color.muted, ...thin })
        .setData(lineData(current.dates, current.bb_lower));
    }
    if (settings.ma) {
      for (const { period, color: c } of MA_DEFS) {
        chart.addSeries(LineSeries, { color: c, ...thin })
          .setData(lineData(current.dates, sma(current.close, period)));
      }
    }

    // 차트 패턴 마킹 (꺾은선 + 넥라인). 종류별로 숨긴 것은 건너뛴다.
    if (settings.pattern && current.patterns?.length) {
      const lastDate = current.dates[current.dates.length - 1];
      for (const pat of current.patterns) {
        if (hiddenPat.has(pat.kind)) continue;
        // C등급 = 형태가 모호한 것. 기본은 숨기고 '모호한 형태도 보기'로 노출
        if (!showAmbiguous && pat.grade === "C" && !highlightPats.has(pat.kind)) continue;
        const bottom = BULL_KINDS.has(pat.kind);
        const c = bottom ? color.up : color.down;
        const zig = chart.addSeries(LineSeries, {
          color: c, lineWidth: 1, lineStyle: 0,
          priceLineVisible: false, lastValueVisible: false,
          pointMarkersVisible: true, pointMarkersRadius: 2,
        });
        zig.setData(pat.points.map(([d, v]) => ({ time: ts(d), value: v })));
        if (pat.points2?.length) {
          chart.addSeries(LineSeries, {
            color: c, lineWidth: 1, lineStyle: 0,
            priceLineVisible: false, lastValueVisible: false,
            pointMarkersVisible: true, pointMarkersRadius: 2,
          }).setData(pat.points2.map(([d, v]) => ({ time: ts(d), value: v })));
        }

        const neckEnd = pat.completed_date ?? lastDate;
        const neck = chart.addSeries(LineSeries, {
          color: c, lineWidth: 1, lineStyle: 2, // 점선 넥라인
          priceLineVisible: false, lastValueVisible: false,
        });
        neck.setData([
          { time: ts(pat.points[0][0]), value: pat.neckline },
          { time: ts(neckEnd), value: pat.neckline },
        ]);
        if (pat.completed_date) {
          createSeriesMarkers(neck, [
            {
              time: ts(pat.completed_date),
              position: bottom ? "belowBar" : "aboveBar",
              color: c,
              shape: bottom ? "arrowUp" : "arrowDown",
              text: `${PATTERN_LABEL[pat.kind]?.[0] ?? pat.kind}${pat.grade ? ` [${pat.grade}]` : ""}`,
            },
          ]);
        } else if (pat.forming) {
          createSeriesMarkers(neck, [
            {
              time: ts(pat.points[pat.points.length - 1][0]),
              position: bottom ? "belowBar" : "aboveBar",
              color: color.muted,
              shape: "circle",
              text: `${PATTERN_LABEL[pat.kind]?.[1] ?? pat.kind}${pat.grade ? ` [${pat.grade}]` : ""}`,
            },
          ]);
        }
      }
    }

    // 캔들 시리즈 위 마커: 다이버전스 + 캔들 패턴을 한 배열로 (시간 정렬 필수)
    const candleMarkers: SeriesMarker<Time>[] = [];
    if (settings.div) {
      for (const dv of current.divergences) {
        const bull = dv.kind.endsWith("bull");
        candleMarkers.push({
          time: ts(dv.date_to),
          position: bull ? "belowBar" : "aboveBar",
          color: bull ? color.up : color.down,
          shape: bull ? "arrowUp" : "arrowDown",
          text: DIV_LABEL[dv.kind],
        });
      }
    }
    if (settings.candle && current.candles) {
      for (const [kind, dates] of Object.entries(current.candles)) {
        if (hiddenCdl.has(kind)) continue;
        const meta = flagMeta(kind);
        const bull = meta?.bullish;
        for (const d of dates) {
          candleMarkers.push({
            time: ts(d),
            // 중립(도지)은 위쪽 원형, 상승은 아래 화살표, 하락은 위 화살표
            position: bull === true ? "belowBar" : "aboveBar",
            color: bull === true ? color.up : bull === false ? color.down : color.muted,
            shape: bull === true ? "arrowUp" : bull === false ? "arrowDown" : "circle",
            text: meta?.short ?? kind,
          });
        }
      }
    }
    if (candleMarkers.length) {
      candleMarkers.sort((a, b) => (a.time as number) - (b.time as number));
      createSeriesMarkers(candles, candleMarkers);
    }

    // pane 1: 거래량
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      1,
    );
    volume.setData(
      current.dates.map((d, i) => ({
        time: ts(d),
        value: current.volume[i],
        color: current.close[i] >= current.open[i] ? color.up + "66" : color.down + "66",
      })),
    );

    // pane 2: RSI + 30/70 기준선
    const rsiSeries = chart.addSeries(
      LineSeries,
      { color: color.accent, lineWidth: 2, priceLineVisible: false },
      2,
    );
    rsiSeries.setData(lineData(current.dates, current.rsi));
    for (const level of [30, 70]) {
      rsiSeries.createPriceLine({
        price: level,
        color: color.fg,
        lineWidth: 1,
        lineStyle: 0,
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
      lineData(current.dates, current.macd_hist).map((p) => ({
        ...p,
        color: p.value >= 0 ? color.up + "88" : color.down + "88",
      })),
    );
    const macdLine = chart.addSeries(
      LineSeries,
      { color: color.fg, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
      3,
    );
    macdLine.setData(lineData(current.dates, current.macd));
    chart.addSeries(
      LineSeries,
      { color: color.accent, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
      3,
    ).setData(lineData(current.dates, current.macd_signal));

    if (settings.macdCross) {
      createSeriesMarkers(macdLine, macdCrossMarkers(current, color.up, color.down));
    }

    const panes = chart.panes();
    if (panes.length >= 4) {
      panes[0].setStretchFactor(3);
      panes[1].setStretchFactor(0.8);
      panes[2].setStretchFactor(1);
      panes[3].setStretchFactor(1);
    }

    // 같은 종목·타임프레임에서 토글/높이만 바뀐 재생성이면 확대 범위를 복원한다.
    // 종목이나 일/주/월이 바뀌면 시간축이 달라지므로 전체 맞춤(fitContent).
    const viewKey = `${data.code}|${tfKey}`;
    const sameView = prevViewRef.current === viewKey;
    prevViewRef.current = viewKey;

    // 폭 0(숨김 탭 등)으로 만들어진 차트는 폭이 생기는 순간 다시 맞춘다
    let fitted = false;
    const resize = () => {
      const w = el.clientWidth;
      chart.applyOptions({ width: w });
      if (w > 0 && !fitted) {
        fitted = true;
        if (sameView && savedRangeRef.current) {
          chart.timeScale().setVisibleLogicalRange(savedRangeRef.current);
        } else if (tfKey === "d" && current.dates.length > INITIAL_DAILY_BARS) {
          // 일봉 첫 진입: 최근 100봉만 (전체는 너무 촘촘해 보기 불편)
          const n = current.dates.length;
          chart
            .timeScale()
            .setVisibleLogicalRange({ from: n - INITIAL_DAILY_BARS, to: n - 1 });
        } else {
          chart.timeScale().fitContent();
        }
        const ps = chart.panes();
        if (ps.length >= 4) {
          attachPaneLabels(
            [ps[1], ps[2], ps[3]],
            [
              { text: "거래량", infoKey: "volume" },
              { text: "RSI (14)", infoKey: "rsi" },
              { text: "MACD (12,26,9)", infoKey: "macd" },
            ],
            (key) => setInfoInd(INDICATOR_INFO[key] ?? null),
          );
        }
      }
    };
    resize();
    requestAnimationFrame(resize);
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    return () => {
      // 재생성 직전의 확대 범위를 저장 (다음 effect에서 복원 여부 판단)
      try {
        savedRangeRef.current = chart.timeScale().getVisibleLogicalRange();
      } catch {
        /* 이미 제거된 경우 */
      }
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, settings, ready, tfKey, hiddenPat, hiddenCdl, showAmbiguous, themeTick]);

  return (
    <div>
      <div className="chart-toolbar">
        <div className="toolbar-group">
          {availableTfs.map((k) => (
            <button
              key={k}
              type="button"
              className={tfKey === k ? "on" : ""}
              onClick={() => setTfKey(k)}
            >
              {TF_LABEL[k]}
            </button>
          ))}
        </div>
        <div className="toolbar-group">
          {(
            [
              ["candle", "캔들"],
              ["line", "라인"],
            ] as ["candle" | "line", string][]
          ).map(([t, label]) => (
            <button
              key={t}
              type="button"
              className={settings.chartType === t ? "on" : ""}
              onClick={() => update({ chartType: t })}
            >
              {label}
            </button>
          ))}
        </div>
        {/* 모바일에서는 아래 설정들을 접어둔다. 다 펼치면 툴바가 차트보다 먼저
            화면을 채운다 (375px 실측 234px). 봉 종류·차트 종류만 항상 보인다. */}
        <button
          type="button"
          className="toolbar-more-btn"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((o) => !o)}
        >
          차트 설정 {moreOpen ? "▲" : "▼"}
        </button>
        <div className={`toolbar-more${moreOpen ? " open" : ""}`}>
        <div className="toolbar-group">
          {TF_PERIODS[tfKey].map((p) => (
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
              ["pattern", "패턴"],
              ["candle", "캔들"],
            ] as [keyof Settings, string][]
          ).map(([key, label]) => (
            <span key={key} className="toggle-wrap">
              <label className={`toolbar-toggle${settings[key] ? " on" : ""}`}>
                <input
                  type="checkbox"
                  checked={settings[key] as boolean}
                  onChange={(e) => update({ [key]: e.target.checked })}
                />
                {label}
              </label>
              {TOGGLE_INFO[key] && (
                <button
                  type="button"
                  className="chip-info"
                  aria-label={`${label} 설명`}
                  onClick={() => setInfoInd(INDICATOR_INFO[TOGGLE_INFO[key]!] ?? null)}
                >
                  ⓘ
                </button>
              )}
            </span>
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
      </div>
      {settings.pattern && patternKinds.length > 0 && (
        <div className="pattern-chips-wrap">
          <div className="pattern-hint">
            {patternKinds.some((k) => hiddenPat.has(k)) &&
              "겹침을 줄이려고 최근 패턴 위주로 표시 중입니다 — 흐린 칩을 누르면 함께 볼 수 있어요. "}
            패턴 이름 옆 <b>[A/B/C]</b>는 형태가 얼마나 뚜렷한지를 나타냅니다.
            <button
              type="button"
              className="ambiguous-toggle"
              onClick={() => setShowAmbiguous((v) => !v)}
            >
              {showAmbiguous ? "모호한 형태(C) 숨기기" : "모호한 형태(C)도 보기"}
            </button>
          </div>
          {(
            [
              ["상승", "📈", patternKinds.filter((k) => BULL_KINDS.has(k))],
              ["하락", "📉", patternKinds.filter((k) => !BULL_KINDS.has(k))],
            ] as [string, string, string[]][]
          )
            .filter(([, , kinds]) => kinds.length > 0)
            .map(([name, icon, kinds]) => {
              const allShown = kinds.every((k) => !hiddenPat.has(k));
              return (
                <div className="pattern-chips" key={name}>
                  <button
                    type="button"
                    className="pattern-chips-label as-btn"
                    title={allShown ? "모두 끄기" : "모두 켜기"}
                    onClick={() =>
                      setHiddenPat((prev) => {
                        const next = new Set(prev);
                        // 하나라도 켜져 있으면 전부 끄고, 전부 꺼져 있으면 전부 켠다
                        if (allShown) kinds.forEach((k) => next.add(k));
                        else kinds.forEach((k) => next.delete(k));
                        return next;
                      })
                    }
                  >
                    {icon} {name} 패턴:
                  </button>
                  {kinds.map((kind) => {
                    const shown = !hiddenPat.has(kind);
                    const bull = BULL_KINDS.has(kind);
                    const meta = flagMeta(kind); // 패턴 설명 메타 (flags.ts 공용)
                    return (
                      <button
                        key={kind}
                        type="button"
                        className={`pattern-chip${shown ? ` on ${bull ? "bull" : "bear"}` : ""}`}
                        onClick={() =>
                          setHiddenPat((prev) => {
                            const next = new Set(prev);
                            if (next.has(kind)) next.delete(kind);
                            else next.add(kind);
                            return next;
                          })
                        }
                      >
                        {PATTERN_LABEL[kind]?.[2] ?? kind}
                        {meta && (
                          <span
                            role="button"
                            aria-label={`${meta.label} 설명`}
                            className="chip-info"
                            onClick={(e) => {
                              e.stopPropagation(); // 칩 토글과 분리
                              setInfoFlag(meta);
                            }}
                          >
                            ⓘ
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })}
        </div>
      )}
      {settings.candle && candleKinds.length > 0 && (
        <div className="pattern-chips">
          <button
            type="button"
            className="pattern-chips-label as-btn"
            title={candleKinds.every((k) => !hiddenCdl.has(k)) ? "모두 끄기" : "모두 켜기"}
            onClick={() =>
              setHiddenCdl((prev) => {
                const next = new Set(prev);
                const allShown = candleKinds.every((k) => !prev.has(k));
                if (allShown) candleKinds.forEach((k) => next.add(k));
                else candleKinds.forEach((k) => next.delete(k));
                return next;
              })
            }
          >
            🕯 캔들 패턴:
          </button>
          {candleKinds.map((kind) => {
            const meta = flagMeta(kind);
            const shown = !hiddenCdl.has(kind);
            const dirCls =
              meta?.bullish === true ? " bull" : meta?.bullish === false ? " bear" : "";
            return (
              <button
                key={kind}
                type="button"
                className={`pattern-chip${shown ? ` on${dirCls}` : ""}`}
                onClick={() =>
                  setHiddenCdl((prev) => {
                    const next = new Set(prev);
                    if (next.has(kind)) next.delete(kind);
                    else next.add(kind);
                    return next;
                  })
                }
              >
                {meta?.short ?? kind}
                <span
                  role="button"
                  aria-label={`${meta?.label ?? kind} 설명`}
                  className="chip-info"
                  onClick={(e) => {
                    e.stopPropagation(); // 칩 토글과 분리
                    if (meta) setInfoFlag(meta);
                  }}
                >
                  ⓘ
                </span>
              </button>
            );
          })}
        </div>
      )}
      {infoFlag && <FlagInfoModal flag={infoFlag} onClose={() => setInfoFlag(null)} />}
      {infoInd && (
        <div className="info-overlay" onClick={() => setInfoInd(null)}>
          <div className="info-pop" onClick={(e) => e.stopPropagation()}>
            <div className="info-pop-head">
              <strong>{infoInd.title}</strong>
              <button
                type="button"
                className="info-close"
                aria-label="닫기"
                onClick={() => setInfoInd(null)}
              >
                ×
              </button>
            </div>
            <p>{infoInd.desc}</p>
          </div>
        </div>
      )}
      <div ref={ref} className="chart-wrap" />
    </div>
  );
}
