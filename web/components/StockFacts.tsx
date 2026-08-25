import Link from "next/link";
import { FLAG_BY_KEY } from "@/lib/flags";
import type { ChartData, FlagKey, TimeframeData } from "@/lib/types";

/** 종목 페이지의 지표 요약 표.
 *
 *  차트가 <canvas>라 지표 값이 전부 픽셀로만 존재했다. 사람은 보지만 검색엔진과
 *  화면 읽기 프로그램은 못 읽는다 — 종목 페이지의 텍스트가 543자뿐이었고
 *  (대부분 메뉴·버튼 이름) 애드센스가 '가치가 별로 없는 콘텐츠'로 반려했다
 *  (2026-08-13).
 *
 *  새로 계산하는 값은 없다. 이미 chart/{code}.json에 있는 값을 HTML로 꺼낸다.
 *  모바일에서 차트를 확대하지 않고 현재 값을 확인하는 용도로도 쓰인다.
 */

const nf = (v: number, digits = 0) =>
  v.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });

/** 마지막 유효값 (지표는 워밍업 구간이 null이라 끝에서부터 찾는다) */
function lastOf(xs: (number | null)[]): number | null {
  for (let i = xs.length - 1; i >= 0; i--) {
    if (xs[i] != null) return xs[i] as number;
  }
  return null;
}

function rsiState(v: number): string {
  if (v >= 70) return "과매수 구간";
  if (v <= 30) return "과매도 구간";
  if (v >= 60) return "중립~강세";
  if (v <= 40) return "중립~약세";
  return "중립";
}

/** %B — 밴드 안에서 종가의 상대 위치. 0=하단, 1=상단 */
function pctB(close: number, lower: number, upper: number): number | null {
  const span = upper - lower;
  return span > 0 ? (close - lower) / span : null;
}

function bandState(b: number): string {
  if (b >= 1) return "상단 돌파";
  if (b >= 0.8) return "상단 부근";
  if (b <= 0) return "하단 이탈";
  if (b <= 0.2) return "하단 부근";
  return "밴드 중앙권";
}

export default function StockFacts({ data }: { data: ChartData }) {
  const d: TimeframeData = data.tf.d;
  const i = d.dates.length - 1;
  const date = d.dates[i];
  const close = d.close[i];
  const isIndex = /^[A-Za-z]/.test(data.code);
  const unit = isIndex ? "" : "원";

  const rsi = lastOf(d.rsi);
  const macd = lastOf(d.macd);
  const sig = lastOf(d.macd_signal);
  const hist = lastOf(d.macd_hist);
  const bbU = lastOf(d.bb_upper);
  const bbM = lastOf(d.bb_mid);
  const bbL = lastOf(d.bb_lower);
  const b = bbU != null && bbL != null ? pctB(close, bbL, bbU) : null;

  // 최근 20영업일 고저 — 지금 값이 그 안 어디쯤인지가 표에서 바로 읽힌다
  const win = d.close.slice(-20);
  const hi20 = Math.max(...d.high.slice(-20));
  const lo20 = Math.min(...d.low.slice(-20));
  const chg20 = win.length > 1 ? (close / win[0] - 1) * 100 : null;

  const divs = d.divergences.slice(-3).reverse();
  const pats = (d.patterns ?? [])
    .filter((p) => p.completed_date)
    .slice(-3)
    .reverse();
  const cdls = Object.entries(d.candles ?? {})
    .flatMap(([kind, dates]) => dates.map((dt) => ({ kind, date: dt })))
    .sort((a, b2) => (a.date < b2.date ? 1 : -1))
    .slice(0, 3);

  const label = (k: string) => FLAG_BY_KEY.get(k as FlagKey)?.label ?? k;

  return (
    <section className="facts">
      <h2>
        {data.name} 기술적 지표 요약{" "}
        <span className="facts-date">{date} 종가 기준</span>
      </h2>

      <table className="facts-table">
        <tbody>
          <tr>
            <th scope="row">종가</th>
            <td>
              {nf(close)}
              {unit}
            </td>
            <td className="facts-note">
              최근 20일 고가 {nf(hi20)}
              {unit} / 저가 {nf(lo20)}
              {unit}
              {chg20 != null && ` · 20일 등락 ${chg20 > 0 ? "+" : ""}${chg20.toFixed(1)}%`}
            </td>
          </tr>

          {rsi != null && (
            <tr>
              <th scope="row">RSI (14)</th>
              <td>{nf(rsi, 1)}</td>
              <td className="facts-note">
                {rsiState(rsi)} · 70 이상 과매수, 30 이하 과매도로 봅니다
              </td>
            </tr>
          )}

          {macd != null && sig != null && (
            <tr>
              <th scope="row">MACD (12·26·9)</th>
              <td>{nf(macd, 1)}</td>
              <td className="facts-note">
                시그널 {nf(sig, 1)} · 히스토그램 {hist != null ? nf(hist, 1) : "-"} ·{" "}
                {macd > sig ? "MACD가 시그널선 위" : "MACD가 시그널선 아래"}
                {macd > 0 ? ", 0선 위" : ", 0선 아래"}
              </td>
            </tr>
          )}

          {bbU != null && bbM != null && bbL != null && (
            <tr>
              <th scope="row">볼린저밴드 (20·2)</th>
              <td>
                {nf(bbM)}
                {unit}
              </td>
              <td className="facts-note">
                상단 {nf(bbU)}
                {unit} / 하단 {nf(bbL)}
                {unit}
                {b != null && ` · %B ${b.toFixed(2)} (${bandState(b)})`}
              </td>
            </tr>
          )}

          {divs.length > 0 && (
            <tr>
              <th scope="row">최근 다이버전스</th>
              <td>{divs.length}건</td>
              <td className="facts-note">
                {divs
                  .map((x) => `${label(x.kind)} (${x.date_from} → ${x.date_to})`)
                  .join(" · ")}
              </td>
            </tr>
          )}

          {pats.length > 0 && (
            <tr>
              <th scope="row">최근 차트 패턴</th>
              <td>{pats.length}건</td>
              <td className="facts-note">
                {pats
                  .map((p) => `${label(p.kind)} ${p.completed_date} 완성`)
                  .join(" · ")}
              </td>
            </tr>
          )}

          {cdls.length > 0 && (
            <tr>
              <th scope="row">최근 캔들 패턴</th>
              <td>{cdls.length}건</td>
              <td className="facts-note">
                {cdls.map((c) => `${label(c.kind)} ${c.date}`).join(" · ")}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <p className="facts-foot">
        위 값은 {date} 종가로 계산한 것입니다. 지표 계산식과 해석은{" "}
        <Link href="/guide">지표 가이드</Link>에, 차트 패턴은{" "}
        <Link href="/guide/chart-patterns">차트 패턴 가이드</Link>에 정리해 두었습니다.
        하루 지연된 공개 데이터를 자동 계산한 참고 정보이며 투자 조언이 아닙니다.
      </p>
    </section>
  );
}
