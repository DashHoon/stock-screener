import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import AdSlot from "@/components/AdSlot";
import StickyAd from "@/components/StickyAd";
import StockSearch from "@/components/StockSearch";
import { loadLatest } from "@/lib/data";

export const metadata: Metadata = {
  title: {
    default: "주식 시그널 스크리너 — RSI 다이버전스·MACD·볼린저밴드",
    template: "%s | 주식 시그널 스크리너",
  },
  description:
    "국내주식 전 종목의 RSI 다이버전스, MACD 크로스, 볼린저밴드 시그널을 매일 스크리닝합니다.",
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
      </body>
    </html>
  );
}
