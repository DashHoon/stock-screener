"use client";

import { useEffect, useRef, useState } from "react";

/** 광고 자리. variant로 크기를 구분한다 (banner=가로 배너, rect=중형 사각, inline=소형).
 *  애드핏 광고단위가 등록된 variant는 실제 광고를, 나머지는 자리표시자를 그린다. */
type AdVariant = "banner" | "rect" | "inline";

interface AdUnit {
  unit: string;
  width: number;
  height: number;
}

// 카카오 애드핏 광고단위. 단위를 새로 만들어 여기 추가하면 그 자리부터 실제 광고가 나간다.
// (등록 대기: banner → 320x100(모바일)·728x90(PC), 하단 고정 → 320x50)
const AD_UNITS: Partial<Record<AdVariant, AdUnit>> = {
  rect: { unit: "DAN-44QtS6vWPeIcgL5N", width: 300, height: 250 },
};

// 애드핏은 승인된 도메인에서만 광고를 내려준다. 로컬·프리뷰에서는 빈 칸이 되어
// 레이아웃을 확인할 수 없으므로 자리표시자를 그대로 보여준다.
const LIVE_HOSTS = new Set(["kscreener.com", "www.kscreener.com"]);

export default function AdSlot({
  id,
  variant = "rect",
}: {
  id: string;
  variant?: AdVariant;
}) {
  const ad = AD_UNITS[variant];
  const boxRef = useRef<HTMLDivElement>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    setLive(LIVE_HOSTS.has(window.location.hostname));
  }, []);

  useEffect(() => {
    const box = boxRef.current;
    if (!ad || !live || !box) return;
    // <ins>와 로더를 자리마다 직접 꽂는다. 애드핏 스크립트는 로드 시점에 한 번만
    // 훑고 지나가서, next/link로 페이지를 옮기면(SPA 이동) 새 <ins>를 보지 못한다.
    const ins = document.createElement("ins");
    ins.className = "kakao_ad_area";
    ins.style.display = "none";
    ins.setAttribute("data-ad-unit", ad.unit);
    ins.setAttribute("data-ad-width", String(ad.width));
    ins.setAttribute("data-ad-height", String(ad.height));

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "//t1.kakaocdn.net/kas/static/ba.min.js";
    script.async = true;

    box.appendChild(ins);
    box.appendChild(script);
    return () => {
      box.replaceChildren();
    };
  }, [ad, live]);

  if (!ad || !live) {
    return (
      <div className={`ad-slot ad-${variant}`} data-ad-slot={id} aria-hidden="true">
        <span>광고</span>
      </div>
    );
  }

  return (
    <div className={`ad-unit ad-${variant}`} data-ad-slot={id}>
      {/* 콘텐츠로 오인되지 않도록 광고임을 표시한다 */}
      <span className="ad-label">광고</span>
      <div className="ad-box" ref={boxRef} style={{ minHeight: ad.height }} />
    </div>
  );
}
