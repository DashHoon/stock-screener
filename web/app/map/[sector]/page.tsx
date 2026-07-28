import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import SectorMap from "@/components/SectorMap";
import { loadLatest } from "@/lib/data";
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
