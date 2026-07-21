import type { FlagKey } from "./types";

export interface FlagMeta {
  key: FlagKey;
  label: string;
  short: string; // 테이블 배지용
  bullish: boolean | null; // null = 중립
}

export interface FlagGroup {
  name: string;
  flags: FlagMeta[];
}

export const FLAG_GROUPS: FlagGroup[] = [
  {
    name: "RSI",
    flags: [
      { key: "rsi_oversold", label: "과매도 (RSI ≤ 30)", short: "과매도", bullish: true },
      { key: "rsi_overbought", label: "과매수 (RSI ≥ 70)", short: "과매수", bullish: false },
    ],
  },
  {
    name: "RSI 다이버전스",
    flags: [
      { key: "div_reg_bull", label: "상승 다이버전스 (regular)", short: "상승 다이버", bullish: true },
      { key: "div_reg_bear", label: "하락 다이버전스 (regular)", short: "하락 다이버", bullish: false },
      { key: "div_hid_bull", label: "히든 상승 다이버전스", short: "히든 상승", bullish: true },
      { key: "div_hid_bear", label: "히든 하락 다이버전스", short: "히든 하락", bullish: false },
    ],
  },
  {
    name: "MACD",
    flags: [
      { key: "macd_golden", label: "골든크로스 (MACD↗시그널)", short: "골든", bullish: true },
      { key: "macd_dead", label: "데드크로스 (MACD↘시그널)", short: "데드", bullish: false },
      { key: "macd_zero_up", label: "0선 상향 돌파", short: "0선↑", bullish: true },
    ],
  },
  {
    name: "볼린저밴드",
    flags: [
      { key: "bb_lower_touch", label: "하단 밴드 터치", short: "BB하단", bullish: true },
      { key: "bb_upper_touch", label: "상단 밴드 터치", short: "BB상단", bullish: false },
      { key: "bb_squeeze", label: "스퀴즈 (밴드폭 최저)", short: "스퀴즈", bullish: null },
    ],
  },
];

export const ALL_FLAGS: FlagMeta[] = FLAG_GROUPS.flatMap((g) => g.flags);
export const FLAG_BY_KEY = new Map(ALL_FLAGS.map((f) => [f.key, f]));

export function parseFlagsParam(param: string | null | undefined): FlagKey[] {
  if (!param) return [];
  return param
    .split(",")
    .filter((k): k is FlagKey => FLAG_BY_KEY.has(k as FlagKey));
}
