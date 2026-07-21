import type { FlagKey } from "./types";

export interface Preset {
  slug: string;
  title: string;
  flags: FlagKey[];
  description: string; // 메타 설명 + 페이지 도입부 (SEO)
}

export const PRESETS: Preset[] = [
  {
    slug: "oversold-bb-lower",
    title: "과매도 + 볼린저 하단 터치",
    flags: ["rsi_oversold", "bb_lower_touch"],
    description:
      "RSI 30 이하로 과매도 상태이면서 볼린저밴드 하단까지 닿은 종목입니다. 단기 낙폭이 과대하다는 두 신호가 겹치는 구간으로, 기술적 반등 후보를 찾을 때 참고합니다.",
  },
  {
    slug: "bullish-divergence",
    title: "RSI 상승 다이버전스",
    flags: ["div_reg_bull"],
    description:
      "주가는 저점을 낮췄지만 RSI 저점은 높아진 종목입니다. 하락 추세의 힘이 약해지고 있다는 신호로 해석되는 대표적 반전 패턴입니다.",
  },
  {
    slug: "oversold-bullish-divergence",
    title: "과매도 + 상승 다이버전스",
    flags: ["rsi_oversold", "div_reg_bull"],
    description:
      "과매도 구간에서 상승 다이버전스까지 발생한 종목입니다. 반전 신호 두 개가 겹친 조합으로, 이 스크리너에서 가장 강한 반등 후보 필터입니다.",
  },
  {
    slug: "macd-golden-cross",
    title: "MACD 골든크로스",
    flags: ["macd_golden"],
    description:
      "MACD선이 시그널선을 상향 돌파한 종목입니다. 단기 모멘텀이 상승 전환되는 구간을 포착합니다.",
  },
  {
    slug: "macd-zero-breakout",
    title: "MACD 0선 상향 돌파",
    flags: ["macd_zero_up"],
    description:
      "MACD가 0선을 넘어선 종목입니다. 중기 추세가 하락에서 상승으로 넘어가는 구간으로 해석됩니다.",
  },
  {
    slug: "bb-squeeze",
    title: "볼린저밴드 스퀴즈",
    flags: ["bb_squeeze"],
    description:
      "밴드폭이 최근 반 년 내 최저 수준으로 좁혀진 종목입니다. 변동성 축소 뒤에는 큰 방향성 움직임이 나오는 경우가 많아 관찰 대상이 됩니다.",
  },
  {
    slug: "overbought-bb-upper",
    title: "과매수 + 볼린저 상단 터치",
    flags: ["rsi_overbought", "bb_upper_touch"],
    description:
      "RSI 70 이상 과매수 상태에서 볼린저밴드 상단까지 닿은 종목입니다. 단기 과열 신호가 겹친 구간으로, 추격 매수에 주의가 필요한 종목을 거릅니다.",
  },
  {
    slug: "bearish-divergence",
    title: "RSI 하락 다이버전스",
    flags: ["div_reg_bear"],
    description:
      "주가는 고점을 높였지만 RSI 고점은 낮아진 종목입니다. 상승 추세의 힘이 약해지고 있다는 경고 신호로 해석됩니다.",
  },
];

export const PRESET_BY_SLUG = new Map(PRESETS.map((p) => [p.slug, p]));
