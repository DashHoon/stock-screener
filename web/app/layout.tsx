import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import AdSlot from "@/components/AdSlot";
import Analytics from "@/components/Analytics";
import StickyAd from "@/components/StickyAd";
import StockSearch from "@/components/StockSearch";
import ThemeToggle from "@/components/ThemeToggle";
import { loadLatest } from "@/lib/data";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL), // OG·canonical의 절대 URL 기준 (도메인 교체 시 env만 변경)
  title: {
    default: "주식 시그널 스크리너 — RSI 다이버전스·MACD·볼린저밴드",
    template: "%s | 주식 시그널 스크리너",
  },
  description:
    "국내주식 전 종목의 RSI 다이버전스, MACD 크로스, 볼린저밴드, 차트 패턴 시그널을 매일 스크리닝합니다. 종목별 10년 차트와 백테스트 통계 제공.",
  openGraph: {
    type: "website",
    siteName: "주식 시그널 스크리너",
    locale: "ko_KR",
  },
  robots: { index: true, follow: true },
  verification: {
    // 구글 서치 콘솔 소유 확인 — Vercel 환경변수로 넣는다 (ANALYTICS_GUIDE.md).
    // 값이 없으면 태그 자체가 렌더되지 않아 아무 영향이 없다.
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || undefined,
    other: {
      "naver-site-verification": "7225b845dcedf04f93882d87daefdb1b9be49597",
    },
  },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  let date = "";
  try {
    date = (await loadLatest()).date;
  } catch {
    /* 데이터 없으면 날짜 미표시 */
  }
  return (
    <html lang="ko">
      <head>
        {/* 첫 페인트 전에 저장된 테마를 적용 — 라이트로 그려졌다 다크로 바뀌는 깜빡임 방지 */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('theme')==='dark')document.documentElement.dataset.theme='dark'}catch(e){}",
          }}
        />
      </head>
      <body>
        <header className="site-header">
          <div className="container">
            <Link href="/" className="logo">
              시그널 스크리너
            </Link>
            <nav>
              <Link href="/">스크리너</Link>
              <Link href="/stats">백테스트</Link>
              <Link href="/guide">지표 가이드</Link>
            </nav>
            <StockSearch />
            <ThemeToggle />
            {date && <span className="data-date">전일({date}) 기준 데이터</span>}
          </div>
        </header>
        <div className="container">
          <AdSlot id="global-top" variant="banner" />
        </div>
        <main className="container">{children}</main>
        <footer className="site-footer">
          <div className="container">
            <p className="footer-disclaimer">
              <strong>투자 유의 안내</strong> · 본 서비스가 제공하는 모든 정보는
              하루 이상 지연된 시세를 바탕으로 자동 계산된 <strong>참고용
              정보</strong>이며, 특정 종목의 매수·매도를 권유하는 투자 조언이
              아닙니다. 데이터는 지연·오류·누락이 있을 수 있으며 정확성을 보증하지
              않습니다. 모든 투자 판단과 그 결과에 대한 책임은 투자자 본인에게
              있습니다.
            </p>
            <p>데이터 출처: 공공데이터포털(금융위원회 주식시세정보), KRX, 네이버 금융.</p>
            <nav className="footer-links">
              <Link href="/guide">지표 가이드</Link>
              <Link href="/disclaimer">면책조항</Link>
              <Link href="/privacy">개인정보처리방침</Link>
            </nav>
          </div>
        </footer>
        <StickyAd />
        <Analytics />
      </body>
    </html>
  );
}
