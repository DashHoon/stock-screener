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
  | "bb_squeeze";

export interface StockSignal {
  code: string;
  name: string;
  close: number;
  change_pct: number | null;
  flags: Record<FlagKey, boolean>;
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

export interface ChartData {
  code: string;
  name: string;
  dates: string[];
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
