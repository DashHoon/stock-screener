// 도메인 구매 후 NEXT_PUBLIC_SITE_URL 환경변수로 교체하면 된다 (Vercel 설정)
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  "https://stock-screener-flame-omega.vercel.app";

// 블로그(/blog)는 별도 Vercel 프로젝트를 리라이트로 프록시한다 (next.config.mjs).
// 그 프로젝트가 아직 없는 상태에서 링크만 노출되면 404가 되므로, 오리진이 설정된
// 환경에서만 블로그 관련 UI와 사이트맵 항목을 켠다.
export const BLOG_ENABLED = Boolean(process.env.BLOG_ORIGIN);
