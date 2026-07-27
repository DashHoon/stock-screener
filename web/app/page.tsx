import { Suspense } from "react";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import QuickAccess from "@/components/QuickAccess";
import Screener from "@/components/Screener";
import { PRESETS } from "@/lib/presets";

export default function Home() {
  return (
    <>
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
