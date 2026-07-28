import { Suspense } from "react";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import QuickAccess from "@/components/QuickAccess";
import Screener from "@/components/Screener";
import { PRESETS } from "@/lib/presets";

export default function Home() {
  return (
    <>
      {/* 모바일에서는 헤더 메뉴가 숨겨져 있어(폭 부족) 업종맵으로 갈 길이 여기뿐이다 */}
      <Link href="/map" className="home-map-entry">
        <span className="hme-title">업종별 시황 맵 →</span>
        <span className="hme-desc">
          전 종목을 업종별로 묶어 시가총액 크기·등락률 색으로 한눈에
        </span>
      </Link>
      <nav className="preset-links" style={{ marginTop: 20 }}>
        <span>인기 조합:</span>
        {PRESETS.map((p) => (
          <Link key={p.slug} href={`/screen/${p.slug}`}>
            {p.title}
          </Link>
        ))}
      </nav>
      <QuickAccess />
      <Suspense>
        <Screener />
      </Suspense>
      <AdSlot id="home-bottom" variant="banner" />
    </>
  );
}
