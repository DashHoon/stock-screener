/** 광고 자리 예약 컴포넌트. Phase 4 공개 시 애드핏/애드센스/CPA 코드로 교체한다.
 *  variant로 크기를 구분한다 (banner=가로 배너, rect=중형 사각, inline=소형). */
type AdVariant = "banner" | "rect" | "inline";

export default function AdSlot({
  id,
  variant = "rect",
}: {
  id: string;
  variant?: AdVariant;
}) {
  return (
    <div className={`ad-slot ad-${variant}`} data-ad-slot={id} aria-hidden="true">
      <span>광고</span>
    </div>
  );
}
