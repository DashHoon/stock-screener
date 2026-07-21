import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import AdSlot from "@/components/AdSlot";
import Screener from "@/components/Screener";
import { PRESETS, PRESET_BY_SLUG } from "@/lib/presets";

export const dynamicParams = false;

export function generateStaticParams() {
  return PRESETS.map(({ slug }) => ({ slug }));
}

export function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Metadata {
  const preset = PRESET_BY_SLUG.get(params.slug);
  if (!preset) return {};
  return {
    title: `${preset.title} 종목 — 오늘의 스크리닝`,
    description: preset.description,
  };
}

export default function PresetPage({ params }: { params: { slug: string } }) {
  const preset = PRESET_BY_SLUG.get(params.slug);
  if (!preset) notFound();

  return (
    <div>
      <div className="prose" style={{ marginTop: 24 }}>
        <h1>{preset.title}</h1>
        <p>{preset.description}</p>
      </div>

      <Suspense>
        <Screener initialFlags={preset.flags} />
      </Suspense>

      <nav className="preset-links">
        <span>다른 조합:</span>
        {PRESETS.filter((p) => p.slug !== preset.slug).map((p) => (
          <Link key={p.slug} href={`/screen/${p.slug}`}>
            {p.title}
          </Link>
        ))}
      </nav>

      <AdSlot id={`preset-${preset.slug}`} />
    </div>
  );
}
