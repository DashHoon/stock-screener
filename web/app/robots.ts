import type { MetadataRoute } from "next";
import { BLOG_ENABLED, SITE_URL } from "@/lib/site";

/** 2026-08-22: 스크리너 본체를 비밀번호로 잠갔다(middleware.ts).
 *  잠긴 경로는 크롤러가 와도 401을 받으므로 아예 오지 말라고 적는다 —
 *  안 그러면 서치콘솔에 크롤 오류가 쌓인다.
 *  공개로 남긴 것: /blog(수익·앱 홍보), /guide(콘텐츠), 정책 페이지,
 *  /s(종목 요약 — 검색 유입과 앱 홍보용).
 *
 *  /stock 은 계속 막는다. 차트가 캔버스라 본문이 543자뿐이고, 2026-08-08에
 *  5,017개를 사이트맵으로 내밀었다가 1,654개가 '발견됨 · 색인 안 됨'으로
 *  쌓였다. 같은 내용을 /s 가 텍스트로 다시 낸다. */
const LOCKED = ["/screen", "/stock/", "/map", "/stats"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: [...LOCKED, "/screen?"] },
      // 애드센스 크롤러 — 광고 게재 시 필수 (블로그·가이드가 대상)
      { userAgent: "Mediapartners-Google", allow: "/", disallow: LOCKED },
      // 네이버
      { userAgent: "Yeti", allow: "/", disallow: LOCKED },
    ],
    // 블로그(/blog)는 별도 배포지만 크롤러는 도메인 루트의 robots.txt만 읽으므로
    // 블로그 사이트맵도 여기서 함께 알린다. 아직 배선되지 않았으면 알리지 않는다.
    sitemap: [
      `${SITE_URL}/sitemap.xml`,
      ...(BLOG_ENABLED ? [`${SITE_URL}/blog/sitemap-index.xml`] : []),
    ],
  };
}
