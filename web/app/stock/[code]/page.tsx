import type { Metadata } from "next";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import StockActions from "@/components/StockActions";
import StockChart from "@/components/StockChart";
import StockFacts from "@/components/StockFacts";
import StockNews from "@/components/StockNews";
import StockProfile from "@/components/StockProfile";
import { listChartCodes, loadChart } from "@/lib/data";

export const dynamicParams = false;

export async function generateStaticParams() {
  const codes = await listChartCodes();
  return codes.map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: { code: string };
}): Promise<Metadata> {
  const data = await loadChart(params.code);
  if (!data) return {};
  return {
    title: `${data.name}(${data.code}) 차트·기술적 시그널`,
    description: `${data.name} 일봉 차트와 RSI 다이버전스, MACD, 볼린저밴드 시그널 (전일 기준).`,
  };
}

export default async function StockPage({
  params,
}: {
  params: { code: string };
}) {
  const data = await loadChart(params.code);
  if (!data?.tf?.d) notFound(); // 구버전(v1) 잔존 파일 방어 포함

  const daily = data.tf.d;
  const last = daily.dates.length - 1;
  const close = daily.close[last];
  const prev = last > 0 ? daily.close[last - 1] : close;
  const changePct = prev ? ((close / prev - 1) * 100).toFixed(2) : null;
  const up = close >= prev;

  const isIndex = /^[A-Za-z]/.test(data.code); // 지수(KS11/KQ11)는 코드가 문자로 시작

  return (
    <>
      <div className="stock-header">
        <h1>
          {data.name} <span className="code">{data.code}</span>
        </h1>
        <span className="price">
          {close.toLocaleString()}
          {isIndex ? "" : "원"}
        </span>
        {changePct && (
          <span className={up ? "pct-up" : "pct-down"}>
            {up ? "+" : ""}
            {changePct}%
          </span>
        )}
        <span className="notice">전일({daily.dates[last]}) 기준</span>
        <StockActions code={data.code} name={data.name} />
      </div>

      <StockChart data={data} />

      {/* 어떤 회사인가 — KRX 공시 정보 (주요제품·상장일·대표자 등) */}
      <StockProfile data={data} />

      {/* 차트는 캔버스라 값이 픽셀로만 남는다. 같은 값을 표로 한 벌 더 둔다 —
          검색엔진·화면 읽기 프로그램이 읽을 수 있고, 모바일에서 차트를 확대하지
          않고도 현재 값을 확인할 수 있다. */}
      <StockFacts data={data} />

      <AdSlot id="stock-mid" variant="rect" />

      <StockNews name={data.name} />

      <AdSlot id="stock-bottom" variant="banner" />
    </>
  );
}
