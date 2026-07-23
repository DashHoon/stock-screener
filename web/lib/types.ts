export type FlagKey =
  | "rsi_overbought"
  | "rsi_oversold"
  | "div_reg_bull"
  | "div_reg_bear"
  | "div_hid_bull"
  | "div_hid_bear"
  | "macd_golden"
  | "macd_dead"
  | "macd_zero_up"
  | "bb_upper_touch"
  | "bb_lower_touch"
  | "bb_squeeze"
  | "pat_double_bottom"
  | "pat_double_bottom_form"
  | "pat_double_top"
  | "pat_double_top_form"
  | "pat_cup_handle"
  | "pat_cup_handle_form";

export interface StockSignal {
  code: string;
  name: string;
  close: number;
  change_pct: number | null;
  /** 시그널별 마지막 발생이 몇 봉 전인지 (0=오늘). 63봉(~3개월) 초과는 생략 */
  sig: Partial<Record<FlagKey, number>>;
  rsi: number | null;
}

export interface LatestSignals {
  date: string;
  stocks: StockSignal[];
}

export interface DivergenceMark {
  kind: "div_reg_bull" | "div_reg_bear" | "div_hid_bull" | "div_hid_bear";
  date_from: string;
  date_to: string;
  price_from: number;
  price_to: number;
  rsi_from: number;
  rsi_to: number;
}

export interface PatternMark {
  kind: "pat_double_bottom" | "pat_double_top" | "pat_cup_handle";
  points: [string, number][]; // [date, price] 꺾은선 좌표
  neckline: number;
  completed_date: string | null;
  forming: boolean;
}

export interface TimeframeData {
  dates: string[];
  patterns?: PatternMark[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_hist: (number | null)[];
  bb_upper: (number | null)[];
  bb_mid: (number | null)[];
  bb_lower: (number | null)[];
  divergences: DivergenceMark[];
}

export type TimeframeKey = "d" | "w" | "m";

export interface ChartData {
  code: string;
  name: string;
  tf: Partial<Record<TimeframeKey, TimeframeData>> & { d: TimeframeData };
}
