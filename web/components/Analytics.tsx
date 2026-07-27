"use client";

import Script from "next/script";
import { useEffect, useState } from "react";

/**
 * Google Analytics 4 (gtag.js).
 *
 * 측정 ID는 모든 페이지 소스에 그대로 노출되는 공개 값이라 시크릿이 아니다 →
 * 코드에 직접 둔다 (Vercel 환경변수 관리 불필요). 필요하면 NEXT_PUBLIC_GA_ID로 덮어쓴다.
 *
 * 운영 도메인에서만 켠다. 로컬 개발·프리뷰 배포(*.vercel.app)의 내 테스트 방문이
 * 통계에 섞이면 방문자 수가 부풀려지기 때문. 환경변수를 환경별로 체크하는 방식보다
 * 호스트명으로 거르는 쪽이 확실하다 (프리뷰 체크 해제를 잊을 일이 없다).
 *
 * SPA 라우팅(next/link) 이동은 GA4 '향상된 측정'이 history 변경을 감지해 집계한다.
 */
const GA_ID = process.env.NEXT_PUBLIC_GA_ID || "G-WVWKG04TFE";
const LIVE_HOSTS = new Set(["kscreener.com", "www.kscreener.com"]);

export default function Analytics() {
  const [live, setLive] = useState(false);

  useEffect(() => {
    setLive(LIVE_HOSTS.has(window.location.hostname));
  }, []);

  if (!GA_ID || !live) return null;

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
        strategy="afterInteractive"
      />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer=window.dataLayer||[];
function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());
gtag('config','${GA_ID}');`}
      </Script>
    </>
  );
}
