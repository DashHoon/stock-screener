import type { MetadataRoute } from "next";
import { listChartCodes } from "@/lib/data";
import { PRESETS } from "@/lib/presets";
import { SITE_URL } from "@/lib/site";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const codes = await listChartCodes();
  return [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/guide`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/stats`, changeFrequency: "weekly", priority: 0.8 },
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
