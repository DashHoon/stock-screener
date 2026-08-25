export type FlagKey =
  | "rsi_overbought"
  | "rsi_oversold"
  | "div_reg_bull"
  | "div_reg_bear"
  | "div_hid_bull"
  | "div_hid_bear"
  | "div_reg_bull_x3"
  | "div_reg_bear_x3"
  | "div_hid_bull_x3"
  | "div_hid_bear_x3"
  | "macd_golden"
  | "macd_dead"
  | "macd_zero_up"
  | "bb_upper_touch"
  | "bb_lower_touch"
  | "bb_squeeze"
  // 이격도 과열/침체 (배치 config.DISPARITY_BANDS)
  | "disp20_high"
  | "disp20_low"
  | "disp60_high"
  | "disp60_low"
  // 그물망(GMMA) 정배열·역배열
  | "gmma_above"
  | "gmma_below"
  | "pat_double_bottom"
  | "pat_double_bottom_form"
  | "pat_double_top"
  | "pat_double_top_form"
  | "pat_cup_handle"
  | "pat_cup_handle_form"
  | "pat_hs_top"
  | "pat_hs_top_form"
  | "pat_hs_inv"
  | "pat_hs_inv_form"
  | "pat_triple_bottom"
  | "pat_triple_bottom_form"
  | "pat_triple_top"
  | "pat_triple_top_form"
  | "pat_round_bottom"
  | "pat_round_bottom_form"
  | "pat_round_top"
  | "pat_round_top_form"
  | "pat_tri_asc"
  | "pat_tri_asc_form"
  | "pat_tri_desc"
  | "pat_tri_desc_form"
  | "pat_tri_sym_up"
  | "pat_tri_sym_down"
  | "pat_tri_sym_form"
  | "pat_wedge_rise"
  | "pat_wedge_rise_form"
  | "pat_wedge_fall"
  | "pat_wedge_fall_form"
  | "pat_bwedge_rise"
  | "pat_bwedge_rise_form"
  | "pat_bwedge_fall"
  | "pat_bwedge_fall_form"
  | "pat_flag_bull"
  | "pat_flag_bull_form"
  | "pat_flag_bear"
  | "pat_flag_bear_form"
  | "pat_broadening"
  | "pat_broadening_form"
  | "pat_diamond"
  | "pat_diamond_form"
  | "cdl_engulf_bull"
  | "cdl_engulf_bear"
  | "cdl_hammer"
  | "cdl_shooting"
  | "cdl_doji"
  | "cdl_hanging"
  | "cdl_inv_hammer"
  | "cdl_harami_bull"
  | "cdl_harami_bear"
  | "cdl_3soldiers"
  | "cdl_3crows"
  | "cdl_tweezer_bottom"
  | "cdl_tweezer_top"
  | "cdl_wick_top"
  | "cdl_pierce"
  | "cdl_darkcloud"
  | "cdl_morning"
  | "cdl_evening";

/** 일봉 10년 아카이브 (chart/{code}.arc.json).
 *  최근분 이전 구간. 용량 때문에 가격·거래량·RSI만 담고 BB·MACD는 뺐다. */
export interface ChartArchive {
  dates: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
  rsi: (number | null)[];
}

export interface StockSignal {
  code: string;
  name: string;
  close: number;
  change_pct: number | null;
  /** 시가총액 (억원, -1=알 수 없음) */
  cap: number;
  /** 시장 구분 ('KOSPI' | 'KOSDAQ' | '') */
  mkt?: string;
  /** 통계청 업종명 (업종맵 2단계) */
  ind?: string;
  /** 섹터 대분류 (업종맵 1단계). batch/sectors.py의 SECTOR_ORDER 값 */
  sec?: string;
  /** 시그널별 마지막 발생이 몇 봉 전인지 (0=오늘). 63봉(~3개월) 초과는 생략 */
  sig: Partial<Record<FlagKey, number>>;
  rsi: number | null;
  /** 최근 20봉 종가 (스파크라인) */
  m?: number[];
}

export interface MarketIndex {
  code: string;
  name: string;
  close: number;
  change_pct: number | null;
  spark: number[];
}

export interface LatestSignals {
  date: string;
  indices?: MarketIndex[];
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
  /** 연속 다이버전스 사슬 길이(피벗 개수). 2=한 쌍, 3 이상=연속 */
  chain?: number;
}

export interface PatternMark {
  kind: string; // pat_* (완성 키 또는 형성 중이면 기본 키)
  points: [string, number][]; // [date, price] 꺾은선 좌표 (시간 오름차순)
  points2?: [string, number][]; // 보조선 (삼각형/쐐기의 아래 추세선 등)
  neckline: number;
  completed_date: string | null;
  forming: boolean;
  /** 형태 점수 0~100 (참고용). 통과선 미만은 배치에서 이미 걸러져 여기 오지 않는다 */
  shape?: number;
}

export interface TimeframeData {
  dates: string[];
  patterns?: PatternMark[];
  /** 캔들 패턴 발생일 {cdl_*: [date, ...]} (일봉만) */
  candles?: Record<string, string[]>;
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

/** 종목 개요 (KRX 상장법인 공시 정보). 배치가 chart/{code}.json에 함께 싣는다. */
export interface StockProfileData {
  products?: string;   // 주요 제품·사업
  industry?: string;   // 통계청 업종명
  sector?: string;     // 우리 섹터 대분류
  market?: string;     // KOSPI | KOSDAQ
  listed?: string;     // 상장일 YYYY-MM-DD
  ceo?: string;
  homepage?: string;
  region?: string;
  cap?: number;        // 시가총액(억원)
}

export interface ChartData {
  code: string;
  name: string;
  tf: Partial<Record<TimeframeKey, TimeframeData>> & { d: TimeframeData };
  profile?: StockProfileData;
}
