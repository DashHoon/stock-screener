import type { Metadata } from "next";
import Link from "next/link";
import AdSlot from "@/components/AdSlot";

export const metadata: Metadata = {
  title: "캔들 패턴 가이드 — 장악형·망치형·도지·샛별형",
  description:
    "상승/하락 장악형, 망치형, 유성형, 관통형, 흑운형, 샛별형, 저녁별형, 도지 등 단기 캔들(봉) 패턴의 모양과 반전 신호를 설명합니다.",
};

export default function CandlestickGuide() {
  return (
    <div className="prose">
      <h1>캔들 패턴 가이드</h1>
      <p>
        캔들(봉) 하나 또는 두세 개의 조합으로 단기 심리 변화를 읽는 방법입니다.
        반전형 캔들은 <strong>직전 추세</strong>가 있을 때 의미가 커서, 본
        서비스는 상승 반전형은 직전 하락, 하락 반전형은 직전 상승을 확인한 경우만
        신호로 잡습니다.
      </p>


      <h2>상승 반전형</h2>
      <ul>
        <li>
          <strong>상승 장악형</strong>: 직전 음봉을 완전히 감싸는 큰 양봉. 하락 후
          매수세 전환을 뜻합니다.
        </li>
        <li>
          <strong>망치형</strong>: 하락 뒤 아래꼬리가 몸통의 2배 이상인 캔들.
          저점에서 지지·반등을 시사합니다.
        </li>
        <li>
          <strong>관통형</strong>: 큰 음봉 다음 날 그 아래에서 출발해 몸통 절반
          위로 마감한 양봉.
        </li>
        <li>
          <strong>샛별형(3봉)</strong>: 큰 음봉 → 작은 몸통 → 큰 양봉의 조합으로
          바닥 반전을 나타냅니다.
        </li>
      </ul>

      <h2>하락 반전형</h2>
      <ul>
        <li>
          <strong>하락 장악형</strong>: 직전 양봉을 완전히 감싸는 큰 음봉. 상승 후
          매도세 전환입니다.
        </li>
        <li>
          <strong>유성형</strong>: 상승 뒤 위꼬리가 몸통의 2배 이상인 캔들. 고점
          저항·하락을 시사합니다.
        </li>
        <li>
          <strong>흑운형</strong>: 큰 양봉 다음 날 그 위에서 출발해 몸통 절반
          아래로 마감한 음봉.
        </li>
        <li>
          <strong>저녁별형(3봉)</strong>: 큰 양봉 → 작은 몸통 → 큰 음봉의 조합으로
          천장 반전을 나타냅니다.
        </li>
      </ul>

      <AdSlot id="cs-mid" variant="rect" />

      <h2>중립</h2>
      <ul>
        <li>
          <strong>도지</strong>: 시가와 종가가 거의 같아 몸통이 극히 작은 캔들.
          매수·매도의 힘이 팽팽해 방향 결정이 보류된 상태로, 추세 전환의 경고로
          참고합니다.
        </li>
      </ul>

      <p className="notice">
        캔들 패턴은 단기 신호라 신뢰도가 낮을 수 있으며, 추세·거래량·다른 지표와
        함께 확인해야 합니다. 본 내용은 정보 제공용이며 투자 조언이 아닙니다.
      </p>

      <p>
        ← <Link href="/guide">지표 가이드로 돌아가기</Link> ·{" "}
        <Link href="/guide/chart-patterns">차트 패턴 가이드</Link>
      </p>

      <AdSlot id="cs-bottom" variant="banner" />
    </div>
  );
}
