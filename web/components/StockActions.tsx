"use client";

import { useEffect } from "react";
import { pushRecent, toggleWatch, useWatchlist } from "@/lib/storage";

// 종목 상세 헤더용: 관심종목 ★ 토글 + 방문 시 '최근 본 종목'에 기록.
export default function StockActions({ code, name }: { code: string; name: string }) {
  const watch = useWatchlist();
  const watched = watch.some((s) => s.code === code);

  useEffect(() => {
    pushRecent({ code, name });
  }, [code, name]);

  return (
    <button
      type="button"
      className={`watch-btn${watched ? " on" : ""}`}
      aria-pressed={watched}
      onClick={() => toggleWatch({ code, name })}
    >
      {watched ? "★" : "☆"} 관심종목
    </button>
  );
}
