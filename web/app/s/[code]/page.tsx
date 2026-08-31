import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AppCta from "@/components/AppCta";
import Spark from "@/components/Spark";
import { FLAG_GROUPS } from "@/lib/flags";
import { loadLatest } from "@/lib/data";
import type { FlagKey, StockSignal } from "@/lib/types";

/** 검색으로 들어온 사람을 위한 종목 요약. 차트·조건검색은 앱에만 둔다.
 *
 *  왜 /stock 을 열지 않고 이걸 따로 만드나 — /stock 은 차트가 캔버스라
 *  본문 텍스트가 543자뿐이었고, 2026-08-08에 사이트맵으로 5,017개를 내밀었다가
 *  1,654개가 '발견됨 · 색인 안 됨'으로 쌓였다 (app/sitemap.ts 기록). 구글이
 *  주소만 받아두고 크롤조차 하지 않는 상태였다.
 *
 *  그래서 이 페이지는 반대로 만든다. 값과 문장으로 채우고, 스파크라인은
 *  캔버스가 아니라 SVG로 그린다. 종목마다 시그널·수치가 달라 본문이 실제로
 *  달라진다 — 같은 틀에 이름만 바꾼 페이지가 아니다.
 */

export const dynamicParams = false;

const META: Record<string, { label: string; desc: string; bullish: boolean | null }> =
  Object.fromEntries(
    FLAG_GROUPS.flatMap((g) => g.flags).map((f) => [
      f.key,
      { label: f.label, desc: f.desc, bullish: f.bullish },
    ]),
  );

/** 사이트맵·정적 생성 대상. 시총 상위부터 — 검색량이 몰리는 쪽이다. */
const PAGE_LIMIT = 600;

async function topStocks(): Promise<StockSignal[]> {
  const latest = await loadLatest();
  return [...latest.stocks]
    .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
    .slice(0, PAGE_LIMIT);
}

export async function generateStaticParams() {
  return (await topStocks()).map((s) => ({ code: s.code }));
}

async function find(code: string) {
  const latest = await loadLatest();
  const stock = latest.stocks.find((s) => s.code === code);
  return stock ? { stock, date: latest.date, all: latest.stocks } : null;
}

/** 오늘 기준 최근에 잡힌 시그널 (가까운 순). */
function recent(stock: StockSignal, within = 10) {
  return Object.entries(stock.sig ?? {})
    .filter(([key, ago]) => META[key] && (ago as number) <= within)
    .sort((a, b) => (a[1] as number) - (b[1] as number))
    .map(([key, ago]) => ({ key: key as FlagKey, ago: ago as number, ...META[key] }));
}

export async function generateMetadata({
  params,
}: {
  params: { code: string };
}): Promise<Metadata> {
  const found = await find(params.code);
  if (!found) return {};
  const { stock, date } = found;
  const hits = recent(stock).slice(0, 3).map((h) => h.label.split(" (")[0]);
  const tail = hits.length ? ` — ${hits.join(", ")}` : "";
  return {
    title: `${stock.name}(${stock.code}) 기술적 시그널${tail}`,
    description:
      `${date} 종가 기준 ${stock.name} 기술적 지표 요약. ` +
      `RSI ${stock.rsi ?? "-"}, 20일 이격도 ${stock.disp?.d20 ?? "-"}` +
      (hits.length ? `, 최근 잡힌 시그널: ${hits.join(", ")}.` : "."),
  };
}

export default async function StockSummary({
  params,
}: {
  params: { code: string };
}) {
  const found = await find(params.code);
  if (!found) notFound();
  const { stock, date, all } = found;
  const hits = recent(stock);
  const up = (stock.change_pct ?? 0) >= 0;
  const peers = all
    .filter((s) => s.sec === stock.sec && s.code !== stock.code)
    .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
    .slice(0, 8);

  return (
    <main className="summary">
      <nav className="crumb">
        <Link href="/guide">지표 가이드</Link> · {stock.sec ?? "기타"}
      </nav>

      <h1>
        {stock.name} <span className="code">{stock.code}</span>
      </h1>
      <p className="lead">
        {date} 종가 기준 {stock.name}({stock.code})의 기술적 지표 요약입니다.
        {stock.mkt === "KOSPI" ? " 코스피" : " 코스닥"} 상장이고 업종은{" "}
        {stock.sec ?? "기타"}입니다.
        {hits.length
          ? ` 최근 10거래일 안에 ${hits.length}가지 시그널이 잡혔습니다.`
          : " 최근 10거래일 안에 잡힌 시그널은 없습니다."}
      </p>

      <div className="quote">
        <strong>{stock.close?.toLocaleString()}원</strong>
        <span className={up ? "up" : "down"}>
          {up ? "+" : ""}
          {stock.change_pct?.toFixed(2)}%
        </span>
        {stock.m && <Spark values={stock.m} up={up} />}
      </div>

      <h2>지표 값</h2>
      <table className="facts">
        <tbody>
          <tr><th>RSI(14)</th><td>{stock.rsi ?? "-"}</td>
            <td className="note">{rsiNote(stock.rsi)}</td></tr>
          <tr><th>20일 이격도</th><td>{stock.disp?.d20 ?? "-"}</td>
            <td className="note">{dispNote(stock.disp?.d20)}</td></tr>
          <tr><th>60일 이격도</th><td>{stock.disp?.d60 ?? "-"}</td>
            <td className="note">{dispNote(stock.disp?.d60)}</td></tr>
          <tr><th>거래량</th><td>{stock.vol?.toLocaleString()}주</td>
            <td className="note">{volNote(stock.vr)}</td></tr>
          <tr><th>시가총액</th><td>{capText(stock.cap)}</td>
            <td className="note">{stock.ind ?? ""}</td></tr>
        </tbody>
      </table>

      {hits.length > 0 && (
        <>
          <h2>최근 잡힌 시그널</h2>
          <ul className="signals">
            {hits.map((h) => (
              <li key={h.key}>
                <b>{h.label}</b>{" "}
                <span className="ago">
                  {h.ago === 0 ? "당일" : `${h.ago}거래일 전`}
                </span>
                <p>{h.desc}</p>
              </li>
            ))}
          </ul>
        </>
      )}

      <AppCta what={hits[0]?.label.split(" (")[0]} />

      {peers.length > 0 && (
        <>
          <h2>같은 업종 ({stock.sec})</h2>
          <ul className="peers">
            {peers.map((p) => (
              <li key={p.code}>
                <Link href={`/s/${p.code}`}>{p.name}</Link>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="disclaimer">
        이 페이지는 공개된 시세를 기계적으로 계산한 정보이며 투자 자문이나 매매
        권유가 아닙니다. 모든 값은 {date} 종가 기준으로, 오늘 장중 가격은 반영되지
        않았습니다. 시그널은 형태를 기계가 판정한 것이라 틀릴 수 있습니다.
      </p>
    </main>
  );
}

function rsiNote(v?: number | null) {
  if (v == null) return "";
  if (v <= 30) return "30 이하 — 과매도 구간";
  if (v >= 70) return "70 이상 — 과매수 구간";
  return "30~70 사이 — 한쪽으로 치우치지 않은 구간";
}

function dispNote(v?: number) {
  if (v == null) return "";
  const gap = (v - 100).toFixed(1);
  return v >= 100 ? `이동평균보다 ${gap}% 위` : `이동평균보다 ${Math.abs(+gap)}% 아래`;
}

function volNote(vr?: number) {
  if (vr == null) return "";
  if (vr >= 2) return `20일 평균의 ${vr.toFixed(1)}배 — 크게 늘었다`;
  if (vr <= 0.5) return `20일 평균의 ${vr.toFixed(1)}배 — 크게 줄었다`;
  return `20일 평균의 ${vr.toFixed(1)}배`;
}

function capText(cap?: number) {
  if (cap == null || cap < 0) return "-";
  return cap >= 10000 ? `${(cap / 10000).toFixed(1)}조원` : `${cap.toLocaleString()}억원`;
}
