/** 광고 자리 예약 컴포넌트. Phase 4에서 애드핏/CPA 코드로 교체한다. */
export default function AdSlot({ id }: { id: string }) {
  return (
    <div className="ad-slot" data-ad-slot={id}>
      광고 영역
    </div>
  );
}
