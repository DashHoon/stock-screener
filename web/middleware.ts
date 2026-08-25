import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** 세 층으로 나눈다: 공개 콘텐츠 · 앱 전용 · 주인 전용.
 *
 *  2026-08-22에 스크리너 본체를 앱으로 옮기고 사이트는 혼자 쓰기로 했다.
 *  2026-08-25에 데이터까지 잠근다 — 브라우저로 주소를 치면 전 종목 시그널이
 *  통째로 내려받아지던 상태였다.
 *
 *   1. 공개 — 블로그·가이드·ads.txt. 애드센스 심사자가 봐야 하고 수익원이다
 *   2. 앱 전용 — /data, /api/news. x-app-key 머리말이 맞아야 한다
 *   3. 주인 전용 — 나머지 전부. SITE_PASSWORD로 Basic 인증
 *
 *  주인은 앱 전용 경로도 볼 수 있어야 하므로(브라우저에서 데이터 확인),
 *  2층은 '앱 열쇠 또는 Basic 비밀번호'로 판정한다.
 *
 *  **앱 열쇠는 비밀이 아니다.** 배포된 앱 안의 문자열은 뜯어보면 나온다.
 *  주소를 쳐 보는 사람을 막는 빗장이지 작정한 사람을 막는 자물쇠가 아니다.
 *  진짜로 막으려면 사용자별 인증과 짧은 수명의 토큰이 필요하다.
 *
 *  두 값 모두 Vercel 환경변수다. 값이 없으면 그 층의 잠금이 꺼진다 —
 *  환경변수를 깜빡했을 때 아무도(앱 포함) 못 여는 상태로 배포되는 것보다,
 *  열려 있는 편이 되돌리기 쉽다.
 */

// 누구나 볼 수 있는 경로. 접두어로 판정한다.
const PUBLIC_PREFIXES = [
  "/blog",        // 블로그 (수익·앱 홍보. 별도 서비스로 프록시된다)
  "/guide",       // 지표 가이드 — 애드센스 심사가 보는 콘텐츠
  "/about",
  "/contact",
  "/privacy",
  "/disclaimer",
  "/_next",       // 빌드 산출물 (공개 페이지가 이걸 못 받으면 화면이 깨진다)
  "/favicon",
];

// 앱이 쓰는 경로. 앱 열쇠나 주인 비밀번호가 있어야 한다.
const APP_PREFIXES = ["/data", "/api/news"];

// 정확히 일치할 때만 여는 파일
const PUBLIC_FILES = new Set([
  "/ads.txt",      // 애드센스가 직접 읽는다
  "/robots.txt",
  "/sitemap.xml",
]);

function matches(prefixes: string[], pathname: string): boolean {
  return prefixes.some(
    (p) => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p + "."),
  );
}

function hasPassword(req: NextRequest, password: string): boolean {
  const header = req.headers.get("authorization") || "";
  if (!header.startsWith("Basic ")) return false;
  // atob은 edge 런타임에 있다 (Buffer는 없다)
  const [, given] = atob(header.slice(6)).split(":");
  return given === password;
}

function deny(basic: boolean): NextResponse {
  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      // 앱 전용 경로에 Basic 창을 띄우면 브라우저가 로그인 팝업을 보여 준다.
      // 데이터는 사람이 볼 것이 아니므로 그 안내를 하지 않는다.
      // realm은 ASCII만 담을 수 있다. 한글을 넣으면 헤더를 만들다 500이 난다
      // (2026-08-25 로컬 검증에서 잡음 — 배포했으면 전 페이지가 죽었다).
      ...(basic
        ? { "WWW-Authenticate": 'Basic realm="chartcatch", charset="UTF-8"' }
        : {}),
      // 잠긴 경로는 검색에 남기지 않는다
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_FILES.has(pathname) || matches(PUBLIC_PREFIXES, pathname)) {
    return NextResponse.next();
  }

  const password = process.env.SITE_PASSWORD;
  const appKey = process.env.APP_DATA_KEY;

  if (matches(APP_PREFIXES, pathname)) {
    if (!appKey) return NextResponse.next();          // 미설정이면 잠금 없음
    if (req.headers.get("x-app-key") === appKey) return NextResponse.next();
    if (password && hasPassword(req, password)) return NextResponse.next();
    return deny(false);
  }

  if (!password) return NextResponse.next();          // 미설정이면 잠금 없음
  if (hasPassword(req, password)) return NextResponse.next();
  return deny(true);
}

export const config = {
  // 정적 자산까지 미들웨어를 태우면 요청 수가 크게 는다 (Vercel 무료 한도).
  // 위 isPublic이 최종 판정이고, 여기서는 명백한 정적 요청만 미리 걷어낸다.
  matcher: ["/((?!_next/static|_next/image).*)"],
};
