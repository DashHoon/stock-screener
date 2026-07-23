import type { Metadata } from "next";
import { notFound } from "next/navigation";
import AdSlot from "@/components/AdSlot";
import StockChart from "@/components/StockChart";
import { listChartCodes, loadChart } from "@/lib/data";
import { FLAG_BY_KEY } from "@/lib/flags";
import type { FlagKey } from "@/lib/types";

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

  const recentDivs = daily.divergences.slice(-3).reverse();
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
      </div>

      <div className="mobile-top-ad">
        <AdSlot id="stock-mobile-top" />
      </div>

      <StockChart data={data} />

      {recentDivs.length > 0 && (
        <p className="notice">
          최근 다이버전스:{" "}
          {recentDivs
            .map(
              (d) =>
                `${FLAG_BY_KEY.get(d.kind as FlagKey)?.label ?? d.kind} (${d.date_from} → ${d.date_to})`,
            )
            .join(" · ")}
        </p>
      )}

      <AdSlot id="stock-bottom" />
    </>
  );
}
