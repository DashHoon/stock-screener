import type { Metadata } from "next";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import SectorMap from "@/components/SectorMap";
import { loadLatest } from "@/lib/data";
import { SECTOR_ORDER, sectorSlug } from "@/lib/sectors";

export const metadata: Metadata = {
  title: "업종별 시황 맵",
  description:
    "국내 상장 전 종목을 업종별로 묶어 시가총액 크기와 등락률 색으로 한눈에 보는 시황 맵. 업종을 누르면 해당 업종의 종목별 맵으로 들어갑니다.",
  alternates: { canonical: "/map" },
};

export default async function MapPage() {
  const data = await loadLatest();
  return (
    <>
      <h1 className="page-title">업종별 시황 맵</h1>
      <p className="notice">
        칸의 <strong>크기는 시가총액</strong>, <strong>색은 등락률</strong>입니다 (빨강 상승 ·
        파랑 하락). 한 종목이 화면을 다 덮지 않도록 크기는 제곱근으로 압축했습니다.
        업종을 누르면 그 업종의 종목별 맵으로 들어갑니다. 전일({data.date}) 기준.
      </p>

      <SectorMap data={data} />

      <nav className="sector-links">
        {SECTOR_ORDER.map((s) => (
          <Link key={s} href={`/map/${sectorSlug(s)}`}>
            {s}
          </Link>
        ))}
      </nav>

      <AdSlot id="map-bottom" variant="rect" />
    </>
  );
}
