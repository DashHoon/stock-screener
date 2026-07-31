import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "문의 — 오류 제보와 기능 제안",
  description:
    "kscreener 이용 중 발견한 오류, 기능 제안, 제휴·광고 문의를 받는 곳입니다. 이메일로 연락 주시면 확인 후 답신드립니다.",
};

export default function ContactPage() {
  return (
    <div className="prose">
      <h1>문의</h1>
      <p>
        아래 이메일로 연락 주시면 확인 후 답신드립니다. 개인이 운영하는
        서비스라 답신까지 며칠 걸릴 수 있는 점 양해 부탁드립니다.
      </p>

      <h2>이메일</h2>
      <p>
        <a href="mailto:sehoon0224@gmail.com">sehoon0224@gmail.com</a>
      </p>

      <h2>이런 문의를 받습니다</h2>
      <ul>
        <li>
          <strong>오류 제보</strong> — 지표 값이나 패턴 판정이 이상한 경우.
          어느 종목의 어느 날짜인지 알려주시면 훨씬 빠르게 확인할 수 있습니다.
          계산이 틀렸다면 고치고 반영합니다.
        </li>
        <li>
          <strong>기능 제안</strong> — 추가되면 좋을 조건이나 지표, 불편한 화면
          등을 알려주세요.
        </li>
        <li>
          <strong>검증 요청</strong> — &ldquo;이 조건으로 백테스트하면 어떤가&rdquo;
          같은 요청을 받습니다. 계산 가능한 조건이면 확인해 결과를 알려드리거나
          블로그에 정리합니다.
        </li>
        <li>
          <strong>제휴·광고 문의</strong> — 광고 게재나 제휴 제안도 이 주소로
          받습니다.
        </li>
      </ul>

      <h2>답변드리기 어려운 것</h2>
      <p>
        <strong>개별 종목의 매수·매도 상담은 하지 않습니다.</strong> 본 서비스는
        조건에 해당하는 종목을 보여주는 정보 제공 서비스이며, 투자 자문업이나
        유사투자자문업에 해당하지 않습니다. &ldquo;이 종목 어떤가요&rdquo;,
        &ldquo;지금 사도 되나요&rdquo; 같은 질문에는 답변드릴 수 없습니다.
        자세한 내용은 <Link href="/disclaimer">면책조항</Link>을 확인해 주세요.
      </p>

      <h2>데이터 관련 안내</h2>
      <p>
        시세는 공공데이터포털(금융위원회 주식시세정보)의 공개 데이터를 사용하며
        <strong> 하루 이상 지연된 종가 기준</strong>입니다. 실시간 시세와 다른
        것은 오류가 아니라 서비스 설계상 정상입니다. 서비스 전반에 대한 설명은{" "}
        <Link href="/about">소개 페이지</Link>에 있습니다.
      </p>

      <p className="notice">
        수집한 이메일 주소는 문의 답신 목적으로만 사용하며, 그 밖의 용도로
        이용하지 않습니다. 자세한 내용은{" "}
        <Link href="/privacy">개인정보처리방침</Link>을 확인해 주세요.
      </p>
    </div>
  );
}
