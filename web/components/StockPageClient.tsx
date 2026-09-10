"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";
import StockActions from "@/components/StockActions";
import StockChart from "@/components/StockChart";
import StockFacts from "@/components/StockFacts";
import StockNews from "@/components/StockNews";
import StockProfile from "@/components/StockProfile";
import type { ChartData } from "@/lib/types";

export default function StockPageClient({ code }: { code: string }) {
  const [data, setData] = useState<ChartData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setData(null);
    setFailed(false);
    fetch(`/data/chart/${encodeURIComponent(code)}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((value: ChartData) => {
        if (alive && value?.tf?.d) setData(value);
        else if (alive) setFailed(true);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [code]);

  if (failed) {
    return (
      <div className="prose">
        <h1>차트 데이터가 없습니다</h1>
        <p>종목 코드가 올바른지 확인해 주세요.</p>
        <p><Link href="/">스크리너로 돌아가기</Link></p>
      </div>
    );
  }
  if (!data) return <p className="notice">차트 불러오는 중…</p>;

  const daily = data.tf.d;
  const last = daily.dates.length - 1;
  const close = daily.close[last];
  const prev = last > 0 ? daily.close[last - 1] : close;
  const changePct = prev ? ((close / prev - 1) * 100).toFixed(2) : null;
  const up = close >= prev;
  const isIndex = /^[A-Za-z]/.test(data.code);

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
      <StockProfile data={data} />
      <StockFacts data={data} />
      <AdSlot id="stock-mid" variant="rect" />
      <StockNews name={data.name} />
      <AdSlot id="stock-bottom" variant="banner" />
    </>
  );
}
