"use client";

import Link from "next/link";
import { useRecent, useWatchlist } from "@/lib/storage";

// 홈 상단: 관심종목 + 최근 본 종목 (localStorage). 둘 다 비면 아무것도 안 보인다.
export default function QuickAccess() {
  const watch = useWatchlist();
  const recent = useRecent();
  if (watch.length === 0 && recent.length === 0) return null;

  return (
    <div className="quick-access">
      {watch.length > 0 && (
        <div className="qa-group">
          <span className="qa-label">★ 관심종목</span>
          <div className="qa-chips">
            {watch.map((s) => (
              <Link key={s.code} className="qa-chip star" href={`/stock/${s.code}`}>
                {s.name}
              </Link>
            ))}
          </div>
        </div>
      )}
      {recent.length > 0 && (
        <div className="qa-group">
          <span className="qa-label">최근 본 종목</span>
          <div className="qa-chips">
            {recent.map((s) => (
              <Link key={s.code} className="qa-chip" href={`/stock/${s.code}`}>
                {s.name}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
