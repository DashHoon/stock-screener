import type { MetadataRoute } from "next";
import { listChartCodes } from "@/lib/data";
import { PRESETS } from "@/lib/presets";
import { SITE_URL } from "@/lib/site";
import { ALL_SLUGS } from "@/lib/sectors";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const codes = await listChartCodes();
  return [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/guide`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/guide/chart-patterns`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/guide/candlestick`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/stats`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/map`, changeFrequency: "daily", priority: 0.9 },
    ...ALL_SLUGS.map((s) => ({
      url: `${SITE_URL}/map/${s}`,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
    { url: `${SITE_URL}/disclaimer`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/privacy`, changeFrequency: "yearly", priority: 0.2 },
    ...PRESETS.map((p) => ({
      url: `${SITE_URL}/screen/${p.slug}`,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    ...codes.map((code) => ({
      url: `${SITE_URL}/stock/${code}`,
      changeFrequency: "daily" as const,
      priority: 0.4,
    })),
  ];
}
