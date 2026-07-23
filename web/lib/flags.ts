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
  {
    name: "상승 패턴 (완성)",
    flags: [
      { key: "pat_double_bottom", label: "쌍바닥 돌파", short: "쌍바닥", bullish: true },
      { key: "pat_triple_bottom", label: "3중바닥 돌파", short: "3중바닥", bullish: true },
      { key: "pat_hs_inv", label: "역헤드앤숄더 돌파", short: "역H&S", bullish: true },
      { key: "pat_cup_handle", label: "컵앤핸들 돌파", short: "컵핸들", bullish: true },
      { key: "pat_round_bottom", label: "라운드 바텀 돌파", short: "라운드바텀", bullish: true },
      { key: "pat_wedge_fall", label: "하락쐐기 상향 돌파", short: "하락쐐기", bullish: true },
      { key: "pat_tri_asc", label: "상승삼각형 돌파", short: "상승삼각", bullish: true },
      { key: "pat_tri_sym_up", label: "삼각수렴 상향 돌파", short: "수렴↑", bullish: true },
      { key: "pat_flag_bull", label: "상승 플래그/페넌트 돌파", short: "상승플래그", bullish: true },
    ],
  },
  {
    name: "하락 패턴 (완성)",
    flags: [
      { key: "pat_double_top", label: "더블탑 붕괴", short: "더블탑", bullish: false },
      { key: "pat_triple_top", label: "트리플탑 붕괴", short: "트리플탑", bullish: false },
      { key: "pat_hs_top", label: "헤드앤숄더 붕괴", short: "H&S", bullish: false },
      { key: "pat_round_top", label: "라운드 탑 이탈", short: "라운드탑", bullish: false },
      { key: "pat_wedge_rise", label: "상승쐐기 하향 이탈", short: "상승쐐기", bullish: false },
      { key: "pat_tri_desc", label: "하락삼각형 이탈", short: "하락삼각", bullish: false },
      { key: "pat_tri_sym_down", label: "삼각수렴 하향 이탈", short: "수렴↓", bullish: false },
      { key: "pat_flag_bear", label: "하락 플래그/페넌트 이탈", short: "하락플래그", bullish: false },
      { key: "pat_broadening", label: "브로드닝 이탈", short: "브로드닝", bullish: false },
      { key: "pat_diamond", label: "다이아몬드 탑 이탈", short: "다이아몬드", bullish: false },
    ],
  },
  {
    name: "캔들 패턴 (단기)",
    flags: [
      { key: "cdl_engulf_bull", label: "상승 장악형", short: "상승장악", bullish: true },
      { key: "cdl_hammer", label: "망치형 (하락 후)", short: "망치", bullish: true },
      { key: "cdl_pierce", label: "관통형", short: "관통", bullish: true },
      { key: "cdl_morning", label: "샛별형 (3봉)", short: "샛별", bullish: true },
      { key: "cdl_engulf_bear", label: "하락 장악형", short: "하락장악", bullish: false },
      { key: "cdl_shooting", label: "유성형 (상승 후)", short: "유성", bullish: false },
      { key: "cdl_darkcloud", label: "흑운형", short: "흑운", bullish: false },
      { key: "cdl_evening", label: "저녁별형 (3봉)", short: "저녁별", bullish: false },
      { key: "cdl_doji", label: "도지 (변동폭 큰 날)", short: "도지", bullish: null },
    ],
  },
  {
    name: "패턴 형성 중",
    flags: [
      { key: "pat_double_bottom_form", label: "쌍바닥 형성 중", short: "쌍바닥形", bullish: null },
      { key: "pat_double_top_form", label: "더블탑 형성 중", short: "더블탑形", bullish: null },
      { key: "pat_cup_handle_form", label: "컵앤핸들 형성 중", short: "컵핸들形", bullish: null },
      { key: "pat_hs_inv_form", label: "역H&S 형성 중", short: "역H&S形", bullish: null },
      { key: "pat_hs_top_form", label: "H&S 형성 중", short: "H&S形", bullish: null },
      { key: "pat_tri_sym_form", label: "삼각수렴 형성 중", short: "수렴形", bullish: null },
      { key: "pat_flag_bull_form", label: "상승 플래그 형성 중", short: "상승플래그形", bullish: null },
      { key: "pat_flag_bear_form", label: "하락 플래그 형성 중", short: "하락플래그形", bullish: null },
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
