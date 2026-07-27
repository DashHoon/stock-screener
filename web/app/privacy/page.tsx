import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "개인정보처리방침",
  description:
    "본 서비스는 회원가입 없이 이용되며 개인정보를 서버에 수집·저장하지 않습니다. 광고·분석을 위한 제3자 쿠키 사용에 대해 안내합니다.",
};

export default function PrivacyPage() {
  return (
    <div className="prose">
      <h1>개인정보처리방침</h1>
      <p>
        본 서비스는 이용자의 개인정보를 소중히 여기며, 아래와 같이 개인정보를
        처리합니다.
      </p>

      <h2>1. 수집하는 개인정보</h2>
      <p>
        본 서비스는 <strong>회원가입·로그인 절차가 없으며</strong>, 이름·연락처
        등 개인을 식별할 수 있는 정보를 서버에 직접 수집·저장하지 않습니다.
      </p>

      <h2>2. 브라우저 로컬 저장(localStorage)</h2>
      <p>
        관심종목, 최근 본 종목, 저장한 스크리닝 조건, 차트 설정(테마·표시 지표)
        등 편의 기능은 이용자{" "}
        <strong>브라우저(localStorage)에만 저장</strong>되며 서비스 서버로
        전송되지 않습니다. 브라우저 데이터를 삭제하면 함께 삭제됩니다.
      </p>

      <h2>3. 쿠키 및 제3자 광고</h2>
      <p>
        본 서비스는 광고 게재를 위해 Google AdSense 등 제3자 광고 사업자를 이용할
        수 있습니다. 이들 광고 사업자는 이용자의 관심사에 기반한 광고를 제공하기
        위해 쿠키를 사용할 수 있습니다.
      </p>
      <ul>
        <li>
          Google을 포함한 제3자 공급업체는 쿠키를 사용하여 이용자의 이전 방문
          기록을 바탕으로 광고를 게재합니다.
        </li>
        <li>
          이용자는{" "}
          <a
            href="https://www.google.com/settings/ads"
            target="_blank"
            rel="noopener noreferrer"
          >
            Google 광고 설정
          </a>
          에서 맞춤 광고를 해제할 수 있으며,{" "}
          <a
            href="https://optout.aboutads.info"
            target="_blank"
            rel="noopener noreferrer"
          >
            aboutads.info
          </a>
          에서 제3자 공급업체의 쿠키 사용을 거부할 수 있습니다.
        </li>
      </ul>

      <h2>4. 접속 로그 및 이용 통계(Google Analytics)</h2>
      <p>
        서비스 호스팅 및 안정적 운영을 위해 호스팅 사업자(예: Vercel)가 접속 IP,
        브라우저 종류, 방문 페이지 등 일반적인 로그를 자동으로 수집·처리할 수
        있습니다.
      </p>
      <p>
        또한 본 서비스는 방문자 수와 이용 패턴을 파악하기 위해{" "}
        <strong>Google Analytics</strong>를 사용합니다. Google Analytics는 쿠키를
        통해 방문 페이지, 체류 시간, 유입 경로, 기기·브라우저 종류 등의 정보를
        수집하며, 이 정보는 <strong>개인을 식별하지 않는 형태</strong>로 통계
        목적에만 사용됩니다.
      </p>
      <ul>
        <li>
          수집을 원하지 않으시면{" "}
          <a
            href="https://tools.google.com/dlpage/gaoptout"
            target="_blank"
            rel="noopener noreferrer"
          >
            Google Analytics 차단 브라우저 부가기능
          </a>
          을 설치하거나, 브라우저 설정에서 쿠키를 차단할 수 있습니다.
        </li>
        <li>
          Google의 데이터 처리 방식은{" "}
          <a
            href="https://policies.google.com/technologies/partner-sites"
            target="_blank"
            rel="noopener noreferrer"
          >
            Google 파트너 사이트 정책
          </a>
          에서 확인할 수 있습니다.
        </li>
      </ul>

      <h2>5. 개인정보의 제3자 제공</h2>
      <p>
        본 서비스는 법령에 근거하거나 이용자의 동의가 있는 경우를 제외하고
        개인정보를 제3자에게 제공하지 않습니다.
      </p>

      <h2>6. 변경 고지</h2>
      <p>
        본 방침은 관련 법령 및 서비스 정책에 따라 변경될 수 있으며, 변경 시 본
        페이지를 통해 고지합니다.
      </p>

    </div>
  );
}
