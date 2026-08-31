import { AOS_URL, APP_NAME, APP_READY, IOS_URL } from "@/lib/app-links";

/** 앱 설치 유도. 스토어 등록 전에는 링크 대신 '준비 중'을 보인다 —
 *  없는 주소로 보내면 이탈이고, 링크를 아예 숨기면 앱의 존재를 모른다. */
export default function AppCta({ what }: { what?: string }) {
  return (
    <aside className="app-cta">
      <p className="app-cta-lead">
        {what ? `${what} 같은 조건으로 ` : "차트 모양으로 "}
        전 종목을 찾으려면 {APP_NAME} 앱에서 하세요.
      </p>
      <p className="app-cta-sub">
        81가지 시그널을 조합해 2,500여 종목에서 한 번에 걸러냅니다. 이 페이지는
        검색으로 들어온 분을 위한 요약이라 조건 검색과 차트는 앱에만 있습니다.
      </p>
      {APP_READY ? (
        <p className="app-cta-links">
          {IOS_URL && <a href={IOS_URL}>App Store</a>}
          {IOS_URL && AOS_URL && <span aria-hidden> · </span>}
          {AOS_URL && <a href={AOS_URL}>Google Play</a>}
        </p>
      ) : (
        <p className="app-cta-links muted">앱 출시 준비 중입니다.</p>
      )}
    </aside>
  );
}
