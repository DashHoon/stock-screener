import type { Metadata } from "next";
import StockPageClient from "@/components/StockPageClient";

// 검색 유입은 공개 `/s/[code]`가 담당한다. 주인 전용 상세 차트는 종목마다
// HTML/RSC를 복제하지 않고 공통 셸 하나가 정적 JSON을 받아 그린다.
export const metadata: Metadata = {
  title: "종목 차트·기술적 시그널",
  robots: { index: false, follow: false },
};

export default function StockPage({ params }: { params: { code: string } }) {
  return <StockPageClient code={params.code} />;
}
