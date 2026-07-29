import type { FlagKey } from "./types";

export interface FlagMeta {
  key: FlagKey;
  label: string;
  short: string; // 테이블 배지용
  bullish: boolean | null; // true=상승, false=하락, null=중립
  desc: string; // 지표설명 팝오버용 (한 문장)
}

export interface FlagGroup {
  name: string;
  flags: FlagMeta[];
}

const FORMING_DESC =
  "패턴이 아직 완성(돌파/이탈) 전으로 형성 중인 상태입니다. 확정 신호가 아니라 진행 여부를 지켜봐야 합니다.";

export const FLAG_GROUPS: FlagGroup[] = [
  {
    name: "RSI",
    flags: [
      { key: "rsi_oversold", label: "과매도 (RSI ≤ 30)", short: "과매도", bullish: true, desc: "RSI가 30 이하로 과도한 매도 상태. 기술적 반등이 나오기 쉬운 구간." },
      { key: "rsi_overbought", label: "과매수 (RSI ≥ 70)", short: "과매수", bullish: false, desc: "RSI가 70 이상으로 과도한 매수 상태. 단기 조정 가능성이 커지는 구간." },
    ],
  },
  {
    name: "RSI 다이버전스",
    flags: [
      { key: "div_reg_bull", label: "상승 다이버전스 (regular)", short: "상승 다이버", bullish: true, desc: "가격은 저점을 낮췄는데 RSI 저점은 높아진 상태. 하락 힘이 약해지는 반등 전환 신호." },
      { key: "div_reg_bear", label: "하락 다이버전스 (regular)", short: "하락 다이버", bullish: false, desc: "가격은 고점을 높였는데 RSI 고점은 낮아진 상태. 상승 힘이 약해지는 하락 전환 신호." },
      { key: "div_hid_bull", label: "히든 상승 다이버전스", short: "히든 상승", bullish: true, desc: "상승 추세 눌림목에서 가격 저점은 높은데 RSI 저점은 낮은 상태. 상승 추세 지속 신호." },
      { key: "div_hid_bear", label: "히든 하락 다이버전스", short: "히든 하락", bullish: false, desc: "하락 추세 반등에서 가격 고점은 낮은데 RSI 고점은 높은 상태. 하락 추세 지속 신호." },
    ],
  },
  {
    // 같은 종류의 다이버전스가 피벗을 공유하며 연달아 이어진 상태.
    // 한 번 어긋난 것보다 추세 소진이 뚜렷해 신뢰도가 높다고 본다.
    name: "연속 다이버전스 (3회 이상)",
    flags: [
      { key: "div_reg_bull_x3", label: "상승 다이버전스 연속", short: "상승다이버×3", bullish: true, desc: "가격 저점이 계속 낮아지는데 RSI 저점은 계속 높아지는 상태가 3개 이상의 저점에 걸쳐 이어짐. 하락 동력이 반복적으로 약해지고 있다는 신호로, 한 번 나온 것보다 강하게 봅니다." },
      { key: "div_reg_bear_x3", label: "하락 다이버전스 연속", short: "하락다이버×3", bullish: false, desc: "가격 고점이 계속 높아지는데 RSI 고점은 계속 낮아지는 상태가 3개 이상의 고점에 걸쳐 이어짐. 상승 동력이 반복적으로 꺼지고 있다는 신호로, 한 번 나온 것보다 강하게 봅니다." },
      { key: "div_hid_bull_x3", label: "히든 상승 연속", short: "히든상승×3", bullish: true, desc: "상승 추세 눌림목에서 히든 상승 다이버전스가 3개 이상의 저점에 걸쳐 반복됨. 상승 추세가 계속 유지되고 있다는 신호." },
      { key: "div_hid_bear_x3", label: "히든 하락 연속", short: "히든하락×3", bullish: false, desc: "하락 추세 반등에서 히든 하락 다이버전스가 3개 이상의 고점에 걸쳐 반복됨. 하락 추세가 계속 유지되고 있다는 신호." },
    ],
  },
  {
    name: "MACD",
    flags: [
      { key: "macd_golden", label: "골든크로스 (MACD↗시그널)", short: "골든", bullish: true, desc: "MACD선이 시그널선을 아래에서 위로 돌파. 단기 상승 모멘텀 전환 신호." },
      { key: "macd_dead", label: "데드크로스 (MACD↘시그널)", short: "데드", bullish: false, desc: "MACD선이 시그널선을 위에서 아래로 돌파. 단기 하락 모멘텀 전환 신호." },
      { key: "macd_zero_up", label: "0선 상향 돌파", short: "0선↑", bullish: true, desc: "MACD가 0선을 위로 돌파. 중기 추세가 상승으로 전환되는 신호." },
    ],
  },
  {
    name: "볼린저밴드",
    flags: [
      { key: "bb_lower_touch", label: "하단 밴드 터치", short: "BB하단", bullish: true, desc: "종가가 볼린저 하단선에 닿음. 단기 과매도·반등 가능 구간." },
      { key: "bb_upper_touch", label: "상단 밴드 터치", short: "BB상단", bullish: false, desc: "종가가 볼린저 상단선에 닿음. 단기 과매수·조정 가능 구간." },
      { key: "bb_squeeze", label: "스퀴즈 (밴드폭 최저)", short: "스퀴즈", bullish: null, desc: "밴드폭이 최근 최저 수준으로 좁아짐. 변동성 확대(큰 움직임)가 임박했다는 신호." },
    ],
  },
  {
    name: "상승 패턴 (완성)",
    flags: [
      { key: "pat_double_bottom", label: "쌍바닥 돌파", short: "쌍바닥", bullish: true, desc: "비슷한 높이의 두 저점(W자) 뒤 목선을 위로 돌파. 바닥 반등 신호." },
      { key: "pat_triple_bottom", label: "3중바닥 돌파", short: "3중바닥", bullish: true, desc: "비슷한 세 저점 뒤 목선 상향 돌파. 강한 바닥 확인 신호." },
      { key: "pat_hs_inv", label: "역헤드앤숄더 돌파", short: "역H&S", bullish: true, desc: "가운데 저점이 가장 낮은 역머리어깨형 완성 후 목선 돌파. 추세 상승 전환." },
      { key: "pat_cup_handle", label: "컵앤핸들 돌파", short: "컵핸들", bullish: true, desc: "완만한 U자(컵) 뒤 짧은 눌림(핸들)을 거쳐 상단 돌파. 상승 지속 신호." },
      { key: "pat_round_bottom", label: "라운드 바텀 돌파", short: "라운드바텀", bullish: true, desc: "완만한 원형 바닥을 그린 뒤 상단 돌파. 장기 바닥 반등 신호." },
      { key: "pat_wedge_fall", label: "하락쐐기 상향 돌파", short: "하락쐐기", bullish: true, desc: "하락 쐐기(수렴) 상단을 위로 돌파. 하락 마무리·반등 신호." },
      { key: "pat_bwedge_fall", label: "하락 확대쐐기 돌파", short: "하락확대쐐기", bullish: true, desc: "고점·저점이 모두 낮아지되 폭이 벌어지는 확대 쐐기의 상단을 위로 돌파. 하락 마무리·반등 신호." },
      { key: "pat_tri_asc", label: "상승삼각형 돌파", short: "상승삼각", bullish: true, desc: "수평 저항 + 높아지는 저점의 상승삼각형 상단 돌파. 상승 지속 신호." },
      { key: "pat_tri_sym_up", label: "삼각수렴 상향 돌파", short: "수렴↑", bullish: true, desc: "대칭삼각 수렴을 위로 돌파. 상승 방향으로 확정되는 신호." },
      { key: "pat_flag_bull", label: "상승 플래그/페넌트 돌파", short: "상승플래그", bullish: true, desc: "급등 후 짧은 눌림(깃발) 뒤 재상승 돌파. 상승 지속 신호." },
    ],
  },
  {
    name: "하락 패턴 (완성)",
    flags: [
      { key: "pat_double_top", label: "더블탑 붕괴", short: "더블탑", bullish: false, desc: "비슷한 높이의 두 고점(M자) 뒤 목선 하향 이탈. 고점 붕괴 신호." },
      { key: "pat_triple_top", label: "트리플탑 붕괴", short: "트리플탑", bullish: false, desc: "비슷한 세 고점 뒤 목선 하향 이탈. 강한 천장 신호." },
      { key: "pat_hs_top", label: "헤드앤숄더 붕괴", short: "H&S", bullish: false, desc: "가운데 고점이 가장 높은 머리어깨형 후 목선 이탈. 추세 하락 전환." },
      { key: "pat_round_top", label: "라운드 탑 이탈", short: "라운드탑", bullish: false, desc: "완만한 원형 천장을 그린 뒤 하단 이탈. 장기 고점 붕괴 신호." },
      { key: "pat_wedge_rise", label: "상승쐐기 하향 이탈", short: "상승쐐기", bullish: false, desc: "상승 쐐기(수렴) 하단을 아래로 이탈. 상승 마무리·하락 신호." },
      { key: "pat_bwedge_rise", label: "상승 확대쐐기 이탈", short: "상승확대쐐기", bullish: false, desc: "고점·저점이 모두 높아지되 폭이 벌어지는 확대 쐐기의 하단(상승 지지선)을 아래로 이탈. 상승 마무리·하락 신호." },
      { key: "pat_tri_desc", label: "하락삼각형 이탈", short: "하락삼각", bullish: false, desc: "수평 지지 + 낮아지는 고점의 하락삼각형 하단 이탈. 하락 지속 신호." },
      { key: "pat_tri_sym_down", label: "삼각수렴 하향 이탈", short: "수렴↓", bullish: false, desc: "대칭삼각 수렴을 아래로 이탈. 하락 방향으로 확정되는 신호." },
      { key: "pat_flag_bear", label: "하락 플래그/페넌트 이탈", short: "하락플래그", bullish: false, desc: "급락 후 짧은 반등(깃발) 뒤 재하락 이탈. 하락 지속 신호." },
      { key: "pat_broadening", label: "브로드닝 이탈", short: "브로드닝", bullish: false, desc: "고점·저점이 점점 벌어지는 확산형에서 하단 이탈. 변동성 급증·하락 신호." },
      { key: "pat_diamond", label: "다이아몬드 탑 이탈", short: "다이아몬드", bullish: false, desc: "다이아몬드형 천장 하단 이탈. 고점 반전 하락 신호." },
    ],
  },
  {
    name: "캔들 패턴 (단기)",
    flags: [
      { key: "cdl_engulf_bull", label: "상승 장악형", short: "상승장악", bullish: true, desc: "직전 음봉을 완전히 감싸는 양봉. 하락 후 매수 전환 신호." },
      { key: "cdl_hammer", label: "망치형 (하락 후)", short: "망치", bullish: true, desc: "하락 뒤 아래꼬리가 긴 망치형 캔들. 저점 지지·반등 신호." },
      { key: "cdl_pierce", label: "관통형", short: "관통", bullish: true, desc: "음봉 종가 아래서 열려 몸통 절반 위로 마감한 양봉. 반등 신호." },
      { key: "cdl_morning", label: "샛별형 (3봉)", short: "샛별", bullish: true, desc: "음봉→짧은 봉→양봉 3봉 조합(샛별). 바닥 반전 신호." },
      { key: "cdl_engulf_bear", label: "하락 장악형", short: "하락장악", bullish: false, desc: "직전 양봉을 완전히 감싸는 음봉. 상승 후 매도 전환 신호." },
      { key: "cdl_shooting", label: "유성형 (상승 후)", short: "유성", bullish: false, desc: "상승 뒤 위꼬리가 긴 유성형 캔들. 고점 저항·하락 신호." },
      { key: "cdl_darkcloud", label: "흑운형", short: "흑운", bullish: false, desc: "양봉 고가 위서 열려 몸통 절반 아래로 마감한 음봉. 하락 신호." },
      { key: "cdl_evening", label: "저녁별형 (3봉)", short: "저녁별", bullish: false, desc: "양봉→짧은 봉→음봉 3봉 조합(저녁별). 천장 반전 신호." },
      { key: "cdl_doji", label: "도지 (변동폭 큰 날)", short: "도지", bullish: null, desc: "시가와 종가가 거의 같은 도지 캔들. 방향 결정 보류·추세 전환 경고." },
    ],
  },
  // 배치는 모든 패턴 종류에 대해 kind+"_form" 시그널을 쓴다 — 여기 빠지면
  // '차트에는 그려지는데 검색은 안 되는' 불일치가 생기므로 전 종류를 등록한다.
  // 완성 패턴과 같은 기준으로 상승/하락을 나눈다. bullish를 채워야 '시그널 방향'
  // 필터에서도 잡힌다 (전부 null이던 때는 방향을 고르면 형성 중 그룹이 통째로 사라졌다).
  {
    name: "상승 패턴 형성 중",
    flags: [
      { key: "pat_double_bottom_form", label: "쌍바닥 형성 중", short: "쌍바닥形", bullish: true, desc: FORMING_DESC },
      { key: "pat_triple_bottom_form", label: "3중바닥 형성 중", short: "3중바닥形", bullish: true, desc: FORMING_DESC },
      { key: "pat_hs_inv_form", label: "역H&S 형성 중", short: "역H&S形", bullish: true, desc: FORMING_DESC },
      { key: "pat_cup_handle_form", label: "컵앤핸들 형성 중", short: "컵핸들形", bullish: true, desc: FORMING_DESC },
      { key: "pat_round_bottom_form", label: "라운드바텀 형성 중", short: "라운드바텀形", bullish: true, desc: FORMING_DESC },
      { key: "pat_wedge_fall_form", label: "하락쐐기 형성 중", short: "하락쐐기形", bullish: true, desc: FORMING_DESC },
      { key: "pat_bwedge_fall_form", label: "하락 확대쐐기 형성 중", short: "하락확대쐐기形", bullish: true, desc: FORMING_DESC },
      { key: "pat_tri_asc_form", label: "상승삼각형 형성 중", short: "상승삼각形", bullish: true, desc: FORMING_DESC },
      { key: "pat_flag_bull_form", label: "상승 플래그 형성 중", short: "상승플래그形", bullish: true, desc: FORMING_DESC },
    ],
  },
  {
    name: "하락 패턴 형성 중",
    flags: [
      { key: "pat_double_top_form", label: "더블탑 형성 중", short: "더블탑形", bullish: false, desc: FORMING_DESC },
      { key: "pat_triple_top_form", label: "트리플탑 형성 중", short: "트리플탑形", bullish: false, desc: FORMING_DESC },
      { key: "pat_hs_top_form", label: "H&S 형성 중", short: "H&S形", bullish: false, desc: FORMING_DESC },
      { key: "pat_round_top_form", label: "라운드탑 형성 중", short: "라운드탑形", bullish: false, desc: FORMING_DESC },
      { key: "pat_wedge_rise_form", label: "상승쐐기 형성 중", short: "상승쐐기形", bullish: false, desc: FORMING_DESC },
      { key: "pat_bwedge_rise_form", label: "상승 확대쐐기 형성 중", short: "상승확대쐐기形", bullish: false, desc: FORMING_DESC },
      { key: "pat_tri_desc_form", label: "하락삼각형 형성 중", short: "하락삼각形", bullish: false, desc: FORMING_DESC },
      { key: "pat_flag_bear_form", label: "하락 플래그 형성 중", short: "하락플래그形", bullish: false, desc: FORMING_DESC },
      { key: "pat_broadening_form", label: "브로드닝 형성 중", short: "브로드닝形", bullish: false, desc: FORMING_DESC },
      { key: "pat_diamond_form", label: "다이아몬드 형성 중", short: "다이아몬드形", bullish: false, desc: FORMING_DESC },
    ],
  },
  {
    // 대칭삼각형은 완성돼야 방향이 정해진다 (위로 뚫으면 수렴↑, 아래로 이탈하면 수렴↓).
    // 형성 중에는 어느 쪽도 아니므로 상승·하락 어디에도 넣지 않는다.
    name: "형성 중 (방향 미정)",
    flags: [
      { key: "pat_tri_sym_form", label: "삼각수렴 형성 중", short: "수렴形", bullish: null, desc: "대칭삼각형이 수렴 중인 상태입니다. 위로 뚫릴지 아래로 이탈할지는 아직 정해지지 않았습니다." },
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
