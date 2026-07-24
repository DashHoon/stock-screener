// 지표 설명창용 SVG 도해. 각 차트 패턴·캔들 패턴·다이버전스의 모양을 예시로 보여준다.
// 색: var(--up)=상승(빨강), var(--down)=하락(파랑) — 차트와 동일 컨벤션.
import type { ReactElement } from "react";

const UP = "var(--up)";
const DOWN = "var(--down)";
const LINE = "var(--fg)";
const MUTED = "var(--muted)";
const ACCENT = "var(--accent)";

// 꺾은선/곡선
function L({ d, c = LINE, w = 2, dash }: { d: string; c?: string; w?: number; dash?: string }) {
  return (
    <path
      d={d}
      fill="none"
      stroke={c}
      strokeWidth={w}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={dash}
    />
  );
}
function Dot({ x, y, c = LINE }: { x: number; y: number; c?: string }) {
  return <circle cx={x} cy={y} r={3} fill={c} />;
}
// 돌파 방향 삼각형 (apex 위치 = x,y)
function TriUp({ x, y, c = UP }: { x: number; y: number; c?: string }) {
  return <path d={`M${x} ${y} l6 11 h-12 z`} fill={c} />;
}
function TriDown({ x, y, c = DOWN }: { x: number; y: number; c?: string }) {
  return <path d={`M${x} ${y} l6 -11 h-12 z`} fill={c} />;
}
// 직전 추세 힌트 (좌상단 옅은 화살선)
function Trend({ dir }: { dir: "up" | "down" }) {
  const d = dir === "down" ? "M12 34 L64 74" : "M12 74 L64 34";
  return <g opacity={0.4}>{L({ d, c: MUTED, w: 1.5 })}</g>;
}
// 캔들 하나. o,c,hi,lo = Y픽셀(작을수록 고가). c<o면 상승(빨강)
function Candle({
  x, o, c, hi, lo, w = 13, faint,
}: { x: number; o: number; c: number; hi: number; lo: number; w?: number; faint?: boolean }) {
  const color = c < o ? UP : DOWN;
  const top = Math.min(o, c);
  const h = Math.max(Math.abs(c - o), 2);
  return (
    <g opacity={faint ? 0.35 : 1}>
      <line x1={x} x2={x} y1={hi} y2={lo} stroke={color} strokeWidth={1.5} />
      <rect x={x - w / 2} y={top} width={w} height={h} fill={color} rx={1} />
    </g>
  );
}
// 도지(십자) 캔들
function Doji({ x, mid, hi, lo }: { x: number; mid: number; hi: number; lo: number }) {
  return (
    <g>
      <line x1={x} x2={x} y1={hi} y2={lo} stroke={MUTED} strokeWidth={1.5} />
      <line x1={x - 7} x2={x + 7} y1={mid} y2={mid} stroke={MUTED} strokeWidth={2.5} />
    </g>
  );
}
function Label({ x, y, t }: { x: number; y: number; t: string }) {
  return (
    <text x={x} y={y} fontSize="10" fill={MUTED}>
      {t}
    </text>
  );
}

// 다이버전스 공통 프레임: 가격(위)/RSI(아래) 두 선 + 극점 연결 점선 + 방향 화살표
function Div({
  price, rsi, cp, cr, dir,
}: { price: string; rsi: string; cp: [number, number, number, number]; cr: [number, number, number, number]; dir: "up" | "down" }) {
  return (
    <>
      <Label x={6} y={22} t="가격" />
      <Label x={6} y={96} t="RSI" />
      <L d="M40 76 L220 76" c={MUTED} w={1} dash="2 4" />
      <L d={price} c={LINE} />
      <L d={rsi} c={ACCENT} />
      <L d={`M${cp[0]} ${cp[1]} L${cp[2]} ${cp[3]}`} c={MUTED} w={1.5} dash="3 3" />
      <L d={`M${cr[0]} ${cr[1]} L${cr[2]} ${cr[3]}`} c={MUTED} w={1.5} dash="3 3" />
      <Dot x={cp[0]} y={cp[1]} /><Dot x={cp[2]} y={cp[3]} />
      <Dot x={cr[0]} y={cr[1]} c={ACCENT} /><Dot x={cr[2]} y={cr[3]} c={ACCENT} />
      {dir === "up" ? <TriUp x={206} y={40} /> : <TriDown x={206} y={44} c={DOWN} />}
    </>
  );
}

const DIAGRAMS: Record<string, ReactElement> = {
  // ── RSI ─────────────────────────────
  rsi_oversold: (
    <>
      <L d="M20 42 L20 118 M20 100 L220 100" c={MUTED} w={1} dash="3 3" />
      <Label x={2} y={104} t="30" />
      <L d="M30 60 L70 82 L110 110 L150 96 L190 68" c={ACCENT} />
      <Dot x={110} y={110} c={ACCENT} />
    </>
  ),
  rsi_overbought: (
    <>
      <L d="M20 42 L220 42" c={MUTED} w={1} dash="3 3" />
      <Label x={2} y={46} t="70" />
      <L d="M30 82 L70 60 L110 30 L150 46 L190 66" c={ACCENT} />
      <Dot x={110} y={30} c={ACCENT} />
    </>
  ),
  // ── MACD ────────────────────────────
  macd_golden: (
    <>
      <L d="M20 82 L120 58 L210 32" c={ACCENT} />
      <L d="M20 56 L120 60 L210 62" c={MUTED} />
      <Dot x={120} y={59} />
      <TriUp x={150} y={44} />
      <Label x={150} y={30} t="MACD" />
    </>
  ),
  macd_dead: (
    <>
      <L d="M20 38 L120 60 L210 84" c={ACCENT} />
      <L d="M20 62 L120 60 L210 58" c={MUTED} />
      <Dot x={120} y={60} />
      <TriDown x={150} y={80} c={DOWN} />
    </>
  ),
  macd_zero_up: (
    <>
      <L d="M20 75 L220 75" c={MUTED} w={1.5} />
      <Label x={2} y={72} t="0" />
      <L d="M30 98 L110 80 L210 40" c={ACCENT} />
      <Dot x={120} y={75} />
      <TriUp x={150} y={58} />
    </>
  ),
  // ── 볼린저밴드 ─────────────────────────
  bb_lower_touch: (
    <>
      <L d="M20 38 Q120 32 220 40" c={MUTED} />
      <L d="M20 62 Q120 62 220 62" c={MUTED} w={1} dash="3 3" />
      <L d="M20 86 Q120 94 220 84" c={MUTED} />
      <L d="M25 58 L75 76 L110 90 L155 74 L205 56" c={LINE} />
      <Dot x={110} y={90} c={UP} />
    </>
  ),
  bb_upper_touch: (
    <>
      <L d="M20 38 Q120 30 220 40" c={MUTED} />
      <L d="M20 62 Q120 62 220 62" c={MUTED} w={1} dash="3 3" />
      <L d="M20 86 Q120 92 220 84" c={MUTED} />
      <L d="M25 66 L75 48 L110 34 L155 50 L205 66" c={LINE} />
      <Dot x={110} y={34} c={DOWN} />
    </>
  ),
  bb_squeeze: (
    <>
      <L d="M20 40 L110 58 L220 40" c={MUTED} />
      <L d="M20 86 L110 68 L220 86" c={MUTED} />
      <L d="M25 64 L70 60 L110 63 L150 60 L205 64" c={LINE} />
      <Label x={86} y={80} t="수축" />
    </>
  ),
  // ── 상승 패턴 ──────────────────────────
  pat_double_bottom: (
    <>
      <L d="M20 40 L55 92 L92 58 L130 92 L168 58 L210 28" />
      <L d="M40 58 L210 58" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={55} y={92} /><Dot x={130} y={92} />
      <TriUp x={186} y={44} />
    </>
  ),
  pat_triple_bottom: (
    <>
      <L d="M20 55 L50 92 L80 62 L110 92 L140 62 L170 92 L200 55 L216 30" />
      <L d="M40 62 L216 62" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={50} y={92} /><Dot x={110} y={92} /><Dot x={170} y={92} />
      <TriUp x={198} y={46} />
    </>
  ),
  pat_hs_inv: (
    <>
      <L d="M20 45 L50 74 L76 52 L108 96 L140 52 L166 74 L192 52 L212 30" />
      <L d="M40 52 L208 52" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={50} y={74} /><Dot x={108} y={96} c={UP} /><Dot x={166} y={74} />
      <TriUp x={190} y={40} />
    </>
  ),
  pat_cup_handle: (
    <>
      <L d="M22 46 Q78 112 132 48 L152 62 L168 53 L210 28" />
      <L d="M132 48 L210 48" c={MUTED} w={1.5} dash="4 4" />
      <TriUp x={190} y={42} />
    </>
  ),
  pat_round_bottom: (
    <>
      <L d="M22 44 Q120 128 200 50 L216 30" />
      <L d="M60 48 L216 48" c={MUTED} w={1.5} dash="4 4" />
      <TriUp x={196} y={44} />
    </>
  ),
  pat_wedge_fall: (
    <>
      <L d="M40 46 L196 78" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 88 L184 96" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 52 L72 86 L102 62 L130 94 L158 74 L184 90 L214 44" />
      <TriUp x={196} y={54} />
    </>
  ),
  pat_tri_asc: (
    <>
      <L d="M40 46 L200 46" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 96 L190 58" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 92 L72 48 L98 78 L124 48 L150 66 L176 48 L206 28" />
      <TriUp x={190} y={40} />
    </>
  ),
  pat_tri_sym_up: (
    <>
      <L d="M40 40 L188 68" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 96 L188 70" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 66 L70 88 L100 54 L128 82 L156 66 L184 62 L210 32" />
      <TriUp x={196} y={46} />
    </>
  ),
  pat_flag_bull: (
    <>
      <L d="M26 106 L66 30 L96 46 L134 58 L120 40 L158 52 L204 16" />
      <L d="M92 40 L150 54" c={MUTED} w={1.2} dash="3 3" />
      <L d="M100 54 L158 68" c={MUTED} w={1.2} dash="3 3" />
      <TriUp x={188} y={36} />
    </>
  ),
  // ── 하락 패턴 ──────────────────────────
  pat_double_top: (
    <>
      <L d="M20 92 L55 40 L92 74 L130 40 L168 74 L210 104" />
      <L d="M40 74 L210 74" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={55} y={40} /><Dot x={130} y={40} />
      <TriDown x={186} y={90} c={DOWN} />
    </>
  ),
  pat_triple_top: (
    <>
      <L d="M20 77 L50 40 L80 70 L110 40 L140 70 L170 40 L200 77 L216 102" />
      <L d="M40 70 L216 70" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={50} y={40} /><Dot x={110} y={40} /><Dot x={170} y={40} />
      <TriDown x={198} y={90} c={DOWN} />
    </>
  ),
  pat_hs_top: (
    <>
      <L d="M20 87 L50 58 L76 80 L108 36 L140 80 L166 58 L192 80 L212 102" />
      <L d="M40 80 L208 80" c={MUTED} w={1.5} dash="4 4" />
      <Dot x={50} y={58} /><Dot x={108} y={36} c={DOWN} /><Dot x={166} y={58} />
      <TriDown x={190} y={92} c={DOWN} />
    </>
  ),
  pat_round_top: (
    <>
      <L d="M22 88 Q120 4 200 82 L216 102" />
      <L d="M60 84 L216 84" c={MUTED} w={1.5} dash="4 4" />
      <TriDown x={196} y={96} c={DOWN} />
    </>
  ),
  pat_wedge_rise: (
    <>
      <L d="M40 40 L196 24" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 92 L196 46" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 86 L70 44 L100 68 L128 38 L156 58 L182 42 L212 92" />
      <TriDown x={196} y={84} c={DOWN} />
    </>
  ),
  pat_tri_desc: (
    <>
      <L d="M40 96 L200 96" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 44 L190 84" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 48 L70 90 L98 62 L124 90 L150 74 L176 90 L206 110" />
      <TriDown x={190} y={104} c={DOWN} />
    </>
  ),
  pat_tri_sym_down: (
    <>
      <L d="M40 40 L188 68" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 96 L188 70" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 66 L70 50 L100 82 L128 56 L156 74 L184 76 L210 106" />
      <TriDown x={196} y={98} c={DOWN} />
    </>
  ),
  pat_tri_sym: (
    <>
      <L d="M40 40 L192 66" c={MUTED} w={1.5} dash="4 4" />
      <L d="M40 96 L192 70" c={MUTED} w={1.5} dash="4 4" />
      <L d="M42 66 L72 88 L102 52 L132 84 L160 62 L192 68" />
      <Label x={150} y={104} t="수렴" />
    </>
  ),
  pat_flag_bear: (
    <>
      <L d="M26 30 L66 104 L96 88 L134 76 L120 94 L158 82 L204 118" />
      <L d="M92 82 L150 96" c={MUTED} w={1.2} dash="3 3" />
      <L d="M100 68 L158 82" c={MUTED} w={1.2} dash="3 3" />
      <TriDown x={188} y={104} c={DOWN} />
    </>
  ),
  pat_broadening: (
    <>
      <L d="M46 54 L204 24" c={MUTED} w={1.5} dash="4 4" />
      <L d="M46 72 L204 104" c={MUTED} w={1.5} dash="4 4" />
      <L d="M48 62 L80 46 L108 80 L134 36 L160 90 L188 30 L206 102" />
      <TriDown x={196} y={98} c={DOWN} />
    </>
  ),
  pat_diamond: (
    <>
      <L d="M30 65 L120 26 L210 65 L120 104 Z" c={MUTED} w={1.5} dash="4 4" />
      <L d="M32 64 L62 46 L92 84 L120 34 L150 88 L180 52 L206 96" />
      <TriDown x={196} y={92} c={DOWN} />
    </>
  ),
  // ── 캔들 패턴 ──────────────────────────
  cdl_engulf_bull: (
    <>
      <Trend dir="down" />
      <Candle x={95} o={92} c={104} hi={88} lo={108} faint />
      <Candle x={128} o={58} c={72} hi={54} lo={76} />
      <Candle x={162} o={78} c={50} hi={46} lo={82} w={16} />
    </>
  ),
  cdl_engulf_bear: (
    <>
      <Trend dir="up" />
      <Candle x={95} o={104} c={92} hi={88} lo={108} faint />
      <Candle x={128} o={72} c={58} hi={54} lo={76} />
      <Candle x={162} o={50} c={78} hi={46} lo={82} w={16} />
    </>
  ),
  cdl_hammer: (
    <>
      <Trend dir="down" />
      <Candle x={110} o={64} c={72} hi={60} lo={80} faint />
      <Candle x={150} o={50} c={44} hi={40} lo={92} />
      <Label x={128} y={106} t="긴 아래꼬리" />
    </>
  ),
  cdl_shooting: (
    <>
      <Trend dir="up" />
      <Candle x={110} o={72} c={64} hi={56} lo={76} faint />
      <Candle x={150} o={84} c={90} hi={40} lo={94} />
      <Label x={130} y={30} t="긴 위꼬리" />
    </>
  ),
  cdl_doji: (
    <>
      <Doji x={120} mid={66} hi={34} lo={98} />
      <Label x={104} y={116} t="시가≈종가" />
    </>
  ),
  cdl_pierce: (
    <>
      <Trend dir="down" />
      <Candle x={118} o={44} c={86} hi={40} lo={90} w={16} />
      <Candle x={152} o={90} c={60} hi={56} lo={94} w={16} />
      <L d="M108 65 L164 65" c={MUTED} w={1} dash="3 3" />
      <Label x={166} y={68} t="중간" />
    </>
  ),
  cdl_darkcloud: (
    <>
      <Trend dir="up" />
      <Candle x={118} o={86} c={44} hi={40} lo={90} w={16} />
      <Candle x={152} o={40} c={70} hi={36} lo={74} w={16} />
      <L d="M108 65 L164 65" c={MUTED} w={1} dash="3 3" />
      <Label x={166} y={68} t="중간" />
    </>
  ),
  cdl_morning: (
    <>
      <Trend dir="down" />
      <Candle x={96} o={44} c={80} hi={40} lo={83} w={15} />
      <Candle x={130} o={88} c={90} hi={84} lo={94} w={11} />
      <Candle x={166} o={80} c={48} hi={44} lo={83} w={15} />
    </>
  ),
  cdl_evening: (
    <>
      <Trend dir="up" />
      <Candle x={96} o={80} c={44} hi={40} lo={83} w={15} />
      <Candle x={130} o={40} c={38} hi={34} lo={44} w={11} />
      <Candle x={166} o={45} c={80} hi={42} lo={84} w={15} />
    </>
  ),
  // ── 다이버전스 ─────────────────────────
  div_reg_bull: (
    <Div
      price="M40 40 L72 56 L112 44 L150 66 L188 46"
      rsi="M40 100 L72 112 L112 100 L150 104 L188 94"
      cp={[72, 56, 150, 66]}
      cr={[72, 112, 150, 104]}
      dir="up"
    />
  ),
  div_reg_bear: (
    <Div
      price="M40 60 L72 44 L112 58 L150 34 L188 54"
      rsi="M40 108 L72 96 L112 106 L150 102 L188 112"
      cp={[72, 44, 150, 34]}
      cr={[72, 96, 150, 102]}
      dir="down"
    />
  ),
  div_hid_bull: (
    <Div
      price="M40 46 L72 58 L112 48 L150 52 L188 40"
      rsi="M40 96 L72 102 L112 98 L150 112 L188 100"
      cp={[72, 58, 150, 52]}
      cr={[72, 102, 150, 112]}
      dir="up"
    />
  ),
  div_hid_bear: (
    <Div
      price="M40 56 L72 42 L112 52 L150 50 L188 62"
      rsi="M40 112 L72 106 L112 104 L150 96 L188 108"
      cp={[72, 42, 150, 50]}
      cr={[72, 106, 150, 96]}
      dir="down"
    />
  ),
};

// 형성 중(_form) 키는 완성 패턴 도해를 재사용
const FORM_BASE: Record<string, string> = {
  pat_double_bottom_form: "pat_double_bottom",
  pat_double_top_form: "pat_double_top",
  pat_cup_handle_form: "pat_cup_handle",
  pat_hs_inv_form: "pat_hs_inv",
  pat_hs_top_form: "pat_hs_top",
  pat_tri_sym_form: "pat_tri_sym",
  pat_flag_bull_form: "pat_flag_bull",
  pat_flag_bear_form: "pat_flag_bear",
};

export function PatternDiagram({ flagKey }: { flagKey: string }) {
  const el = DIAGRAMS[FORM_BASE[flagKey] ?? flagKey];
  if (!el) return null;
  return (
    <svg className="flag-diagram" viewBox="0 0 240 130" role="img" aria-hidden="true">
      {el}
    </svg>
  );
}
