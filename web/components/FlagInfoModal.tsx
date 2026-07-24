import type { FlagMeta } from "@/lib/flags";
import { PatternDiagram } from "./PatternDiagram";

// 지표/패턴 설명 팝오버. 도해(SVG) + 라벨 + 한 줄 설명. 스크리너·차트에서 공용.
export default function FlagInfoModal({
  flag,
  onClose,
}: {
  flag: FlagMeta;
  onClose: () => void;
}) {
  return (
    <div className="info-overlay" onClick={onClose}>
      <div className="info-pop" onClick={(e) => e.stopPropagation()}>
        <div className="info-pop-head">
          <span
            className={`badge${
              flag.bullish === true ? " bull" : flag.bullish === false ? " bear" : ""
            }`}
          >
            {flag.short}
          </span>
          <strong>{flag.label}</strong>
          <button type="button" className="info-close" aria-label="닫기" onClick={onClose}>
            ×
          </button>
        </div>
        <PatternDiagram flagKey={flag.key} />
        <p>{flag.desc}</p>
      </div>
    </div>
  );
}
