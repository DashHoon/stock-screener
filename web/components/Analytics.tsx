import Script from "next/script";

/**
 * Google Analytics 4 (gtag.js).
 *
 * NEXT_PUBLIC_GA_ID(측정 ID, G-XXXXXXXXXX)가 비어 있으면 아무것도 렌더하지 않는다.
 * → 로컬 개발·프리뷰 배포에서는 자동으로 꺼지고, 내 테스트 방문이 통계를 오염시키지 않는다.
 * 켜려면 Vercel 프로젝트 환경변수에 값만 넣고 재배포하면 된다 (ANALYTICS_GUIDE.md 참고).
 *
 * SPA 라우팅(next/link) 페이지 이동은 GA4 '향상된 측정'이 브라우저 history 변경을
 * 감지해 자동 집계하므로 별도의 라우터 훅이 필요 없다.
 */
export default function Analytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  if (!gaId) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
        strategy="afterInteractive"
      />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer=window.dataLayer||[];
function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());
gtag('config','${gaId}');`}
      </Script>
    </>
  );
}
