import type { MetadataRoute } from "next";
import { BLOG_ENABLED, SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    // /screen?flags=... 쿼리 조합은 무한 중복이라 크롤 제외 (SEO용은 /screen/[slug] 정적 페이지)
    rules: [
      { userAgent: "*", allow: "/", disallow: "/screen?" },
      // 애드센스 크롤러 — 광고 게재 시 필수
      { userAgent: "Mediapartners-Google", allow: "/" },
      // 네이버
      { userAgent: "Yeti", allow: "/" },
    ],
    // 블로그(/blog)는 별도 배포지만 크롤러는 도메인 루트의 robots.txt만 읽으므로
    // 블로그 사이트맵도 여기서 함께 알린다. 아직 배선되지 않았으면 알리지 않는다.
    sitemap: [
      `${SITE_URL}/sitemap.xml`,
      ...(BLOG_ENABLED ? [`${SITE_URL}/blog/sitemap-index.xml`] : []),
    ],
  };
}
