import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import SectorMap from "@/components/SectorMap";
import StockChart from "@/components/StockChart";
import { loadLatest, loadSectorChart } from "@/lib/data";
import { ALL_SLUGS, SECTOR_ORDER, sectorFromSlug, sectorSlug } from "@/lib/sectors";

export function generateStaticParams() {
  return ALL_SLUGS.map((sector) => ({ sector }));
}

export async function generateMetadata({
  params,
}: {
  params: { sector: string };
}): Promise<Metadata> {
  const name = sectorFromSlug(params.sector);
  if (!name) return {};
  return {
    title: `${name} 업종 시황 맵`,
    description: `${name} 업종 상장 종목을 시가총액 크기와 등락률 색으로 정리한 맵. 종목을 누르면 차트와 기술적 시그널을 볼 수 있습니다.`,
    alternates: { canonical: `/map/${params.sector}` },
  };
}

export default async function SectorMapPage({
  params,
}: {
  params: { sector: string };
}) {
  const name = sectorFromSlug(params.sector);
  if (!name) notFound();

  const data = await loadLatest();
  const index = await loadSectorChart(params.sector);
  const items = data.stocks.filter((s) => (s.sec || "기타") === name);
  const cap = items.reduce((a, b) => a + Math.max(b.cap ?? 0, 0), 0);

  // 업종(2단계) 구성 — 본문 텍스트가 있어야 검색 유입에 걸린다
  const byInd = new Map<string, number>();
  for (const s of items) {
    const k = s.ind || "기타";
    byInd.set(k, (byInd.get(k) ?? 0) + 1);
  }
  const topInd = [...byInd.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);

  return (
    <>
      <h1 className="page-title">{name} 업종 시황 맵</h1>
      <p className="notice">
        {name} 업종 <strong>{items.length}개 종목</strong> · 시가총액 합{" "}
        <strong>{(cap / 10000).toFixed(0)}조원</strong>. 맵에는 시총 상위 45종목을 그립니다.
        칸 크기는 시가총액(제곱근 압축), 색은 등락률입니다. 전일({data.date}) 기준.
      </p>

      <SectorMap data={data} sector={name} />

      {index?.tf?.d && (
        <section className="sector-index">
          <h2>{name} 업종 지수</h2>
          <p className="notice">
            이 업종 종목을 시가총액으로 가중해 만든 지수입니다. 첫 봉을 1,000으로
            두었습니다. 맵은 오늘 하루를 보여주지만, 지수는 이 업종이 몇 달째
            어느 방향으로 움직였는지를 보여줍니다.
          </p>
          <StockChart data={index} />
          <p className="notice sector-index-note">
            <strong>계산 방식과 한계</strong> · 현재 시가총액을 현재가로 나눠 주식 수를
            구한 뒤 과거 종가에 곱해 더했습니다. 그래서 과거의 증자·분할·자사주 소각이
            반영되지 않아 최근 구간이 가장 정확하고 과거로 갈수록 오차가 커집니다.
            지수의 고가·저가는 종목별 고가·저가를 같은 방식으로 합한 근사값이며,
            종목마다 고점 시각이 달라 실제 지수의 고가와는 다릅니다. 상장·상장폐지로
            종목이 드나들어도 계단이 생기지 않도록, 각 날짜에 데이터가 있는 종목만으로
            전일 대비 수익률을 계산해 이어 붙였습니다. 거래량은 지수에 개념이 없어
            비워 두었습니다. 참고용 지표이며 공식 지수가 아닙니다.
          </p>
        </section>
      )}

      {topInd.length > 0 && (
        <p className="notice">
          세부 업종: {topInd.map(([k, n]) => `${k}(${n})`).join(" · ")}
        </p>
      )}

      <AdSlot id={`map-${params.sector}`} variant="rect" />

      <nav className="sector-links">
        <Link href="/map">← 전체 업종 맵</Link>
        {SECTOR_ORDER.filter((s) => s !== name).map((s) => (
          <Link key={s} href={`/map/${sectorSlug(s)}`}>
            {s}
          </Link>
        ))}
      </nav>
    </>
  );
}
