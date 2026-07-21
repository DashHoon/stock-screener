import { Suspense } from "react";
import AdSlot from "@/components/AdSlot";
import Screener from "@/components/Screener";

export default function Home() {
  return (
    <>
      <Suspense>
        <Screener />
      </Suspense>
      <AdSlot id="home-bottom" />
    </>
  );
}
