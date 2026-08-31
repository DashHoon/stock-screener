import type { MetadataRoute } from "next";
import { loadLatest } from "@/lib/data";
import { SITE_URL } from "@/lib/site";

/** ⚠️ 2026-08-22: 스크리너 본체를 비밀번호로 잠갔다(middleware.ts). 잠긴 페이지를
 *  사이트맵에 남겨두면 구글에 "여기 와서 보라"고 해놓고 401을 돌려주는 셈이라,
 *  공개 페이지만 싣는다. 종목·스크리너·업종맵은 전부 빠진다.
 *
 *  잠금을 풀면 아래 기록을 참고해 되살린다 — 종목은 시총 상위 300개만 실었다.
 *
 *  (기록) 종목 사이트맵 축소 경위:
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

/** 종목 요약(/s) 중 사이트맵에 실을 개수.
 *
 *  전부 내밀지 않는다. 2026-08-08에 5,017개를 냈다가 1,654개가 '발견됨 ·
 *  색인 안 됨'으로 쌓인 전례가 있다 — 크롤 예산은 유한하고, 다 내밀면 정작
 *  블로그·가이드가 뒤로 밀린다. 시총 상위부터 300개만 내밀고, 색인률을 보고
 *  늘린다. 나머지는 같은 업종 링크로 이어져 있어 크롤러가 따라갈 수 있다. */
const SUMMARY_IN_SITEMAP = 300;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const latest = await loadLatest();
  const summaries = [...latest.stocks]
    .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
    .slice(0, SUMMARY_IN_SITEMAP)
    .map((s) => ({
      url: `${SITE_URL}/s/${s.code}`,
      changeFrequency: "daily" as const,
      priority: 0.6,
    }));

  // 공개된 것만 — 콘텐츠와 정책 페이지. 블로그는 자체 사이트맵을 따로 낸다
  // (blog/sitemap-index.xml, 서치콘솔에 별도 제출).
  return [
    ...summaries,
    { url: `${SITE_URL}/guide`, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/guide/chart-patterns`, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/guide/candlestick`, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/about`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/contact`, changeFrequency: "yearly", priority: 0.4 },
    { url: `${SITE_URL}/disclaimer`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/privacy`, changeFrequency: "yearly", priority: 0.2 },
  ];
}
