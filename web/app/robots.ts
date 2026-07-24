import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    // /screen?flags=... 쿼리 조합은 무한 중복이라 크롤 제외 (SEO용은 /screen/[slug] 정적 페이지)
    rules: { userAgent: "*", allow: "/", disallow: "/screen?" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
