import type { MetadataRoute } from "next";
import { listChartCodes, loadLatest } from "@/lib/data";
import { PRESETS } from "@/lib/presets";
import { SITE_URL } from "@/lib/site";
import { ALL_SLUGS } from "@/lib/sectors";

/** 사이트맵에 싣는 종목 페이지 수 (시가총액 상위).
 *
 *  2026-08-08 축소. 전 종목 5,017개를 내밀었더니 서치콘솔에 '발견됨 - 현재 색인이
 *  생성되지 않음'이 1,654개 쌓였다. 구글이 주소는 받아두고 크롤조차 하지 않는
 *  상태다 — 종목 페이지는 차트가 캔버스라 텍스트가 543자뿐이고, 그런 페이지
 *  5천 개를 사이트맵으로 내밀면 크롤 예산만 소모하고 정작 블로그·가이드가 뒤로
 *  밀린다.
 *
 *  사이트맵에서 빼도 페이지는 그대로 살아 있고 내부 링크로 접근된다. 구글이
 *  '이건 꼭 봐라'라고 내미는 목록에서 빠질 뿐이다. 종목 페이지에 실질 텍스트를
 *  넣고 나면(TODO B-3 지표 표) 다시 늘린다. */
const SITEMAP_STOCKS = 300;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const codes = await listChartCodes();
  // 시가총액 상위부터. latest.json을 못 읽으면 전량을 싣던 예전 동작으로 돌아가지
  // 않도록, 코드 순으로라도 잘라서 개수를 지킨다.
  let ranked: string[];
  try {
    const latest = await loadLatest();
    const have = new Set(codes);
    ranked = latest.stocks
      .filter((s) => have.has(s.code))
      .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
      .slice(0, SITEMAP_STOCKS)
      .map((s) => s.code);
  } catch {
    ranked = codes.slice(0, SITEMAP_STOCKS);
  }
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
    { url: `${SITE_URL}/about`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/contact`, changeFrequency: "yearly", priority: 0.4 },
    { url: `${SITE_URL}/disclaimer`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/privacy`, changeFrequency: "yearly", priority: 0.2 },
    ...PRESETS.map((p) => ({
      url: `${SITE_URL}/screen/${p.slug}`,
      changeFrequency: "daily" as const,
      priority: 0.8,
    })),
    ...ranked.map((code) => ({
      url: `${SITE_URL}/stock/${code}`,
      changeFrequency: "daily" as const,
      priority: 0.4,
    })),
  ];
}
