"use client";

import { useState } from "react";

// 모바일 하단 고정 광고(앵커). 닫기 버튼 제공 (Better Ads 기준 준수).
export default function StickyAd() {
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  return (
    <div className="sticky-ad" data-ad-slot="sticky-mobile" aria-hidden="true">
      <span>광고</span>
      <button
        type="button"
        className="sticky-ad-close"
        aria-label="광고 닫기"
        onClick={() => setClosed(true)}
      >
        ×
      </button>
    </div>
  );
}
