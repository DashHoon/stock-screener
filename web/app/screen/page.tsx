import { Suspense } from "react";
import type { Metadata } from "next";
import AdSlot from "@/components/AdSlot";
import Screener from "@/components/Screener";
import { FLAG_BY_KEY, parseFlagsParam } from "@/lib/flags";

export function generateMetadata({
  searchParams,
}: {
  searchParams: { flags?: string };
}): Metadata {
  const flags = parseFlagsParam(searchParams.flags);
  const labels = flags.map((k) => FLAG_BY_KEY.get(k)!.label).join(" + ");
  return {
    title: labels ? `${labels} 종목 스크리닝` : "조건 스크리닝",
    description: labels
      ? `${labels} 조건을 만족하는 국내주식 종목 목록 (전일 기준).`
      : undefined,
  };
}

export default function ScreenPage({
  searchParams,
}: {
  searchParams: { flags?: string };
}) {
  const initialFlags = parseFlagsParam(searchParams.flags);
  return (
    <>
      <Suspense>
        <Screener initialFlags={initialFlags} />
      </Suspense>
      <AdSlot id="screen-bottom" />
    </>
  );
}
