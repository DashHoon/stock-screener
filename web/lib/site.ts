// 도메인 구매 후 NEXT_PUBLIC_SITE_URL 환경변수로 교체하면 된다 (Vercel 설정)
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  "https://stock-screener-flame-omega.vercel.app";
