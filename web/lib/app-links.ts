/** 앱 스토어 주소. 심사 통과 전에는 비워 둔다 — 값이 없으면 설치 유도가
 *  '준비 중'으로 바뀌고, 없는 주소로 보내지 않는다. */
export const APP_STORE_ID = process.env.NEXT_PUBLIC_APP_STORE_ID ?? "";
export const PLAY_PACKAGE = process.env.NEXT_PUBLIC_PLAY_PACKAGE ?? "";

export const APP_NAME = "차트캐치";
export const IOS_URL = APP_STORE_ID ? `https://apps.apple.com/kr/app/id${APP_STORE_ID}` : "";
export const AOS_URL = PLAY_PACKAGE ? `https://play.google.com/store/apps/details?id=${PLAY_PACKAGE}` : "";
export const APP_READY = Boolean(IOS_URL || AOS_URL);
