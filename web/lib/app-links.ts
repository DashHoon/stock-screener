/** 앱 스토어 주소. 환경변수로 바꿀 수 있고, 없으면 출시된 앱 값을 쓴다.
 *  2026-10 출시 뒤에도 Vercel에 변수가 없어 /s 페이지 600개가 '준비 중'을
 *  보이고 있었다 — 그래서 기본값을 코드에 둔다. 값을 빈 문자열로 주면
 *  설치 유도가 '준비 중'으로 바뀌고, 없는 주소로 보내지 않는다. */
export const APP_STORE_ID = process.env.NEXT_PUBLIC_APP_STORE_ID ?? "6811464402";
export const PLAY_PACKAGE = process.env.NEXT_PUBLIC_PLAY_PACKAGE ?? "com.nbros.chartcatch";

export const APP_NAME = "차트캐치";
export const IOS_URL = APP_STORE_ID ? `https://apps.apple.com/kr/app/id${APP_STORE_ID}` : "";
export const AOS_URL = PLAY_PACKAGE ? `https://play.google.com/store/apps/details?id=${PLAY_PACKAGE}` : "";
export const APP_READY = Boolean(IOS_URL || AOS_URL);
