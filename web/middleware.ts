import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** 스크리너(도구)는 잠그고, 콘텐츠·데이터는 연다.
 *
 *  2026-08-22 결정. 스크리너 본체는 앱으로 옮기고 사이트는 혼자 쓴다.
 *  다만 통째로 잠그면 두 가지가 죽는다.
 *
 *   1. 앱 — 데이터를 이 사이트에서 받는다 (/data/*)
 *   2. 애드센스 — 심사자가 볼 콘텐츠와 ads.txt가 있어야 한다
 *
 *  그래서 '도구'만 잠그고 '읽을거리'는 공개로 둔다. 블로그는 수익과 앱 홍보를
 *  겸하므로 당연히 공개다.
 *
 *  비밀번호는 Vercel 환경변수 SITE_PASSWORD로 넣는다. 값이 없으면 잠금이
 *  통째로 꺼진다 — 환경변수를 깜빡했을 때 사이트가 아무도 못 여는 상태로
 *  배포되는 것보다, 열려 있는 편이 되돌리기 쉽다.
 */

// 잠그지 않는 경로. 접두어로 판정한다.
const PUBLIC_PREFIXES = [
  "/blog",        // 블로그 (수익·앱 홍보. 별도 서비스로 프록시된다)
  "/data",        // 앱이 읽는 JSON — 이게 막히면 앱이 첫날부터 안 돈다
  "/guide",       // 지표 가이드 — 애드센스 심사가 보는 콘텐츠
  "/about",
  "/contact",
  "/privacy",
  "/disclaimer",
  "/_next",       // 빌드 산출물 (공개 페이지가 이걸 못 받으면 화면이 깨진다)
  "/favicon",
];

// 정확히 일치할 때만 여는 파일
const PUBLIC_FILES = new Set([
  "/ads.txt",      // 애드센스가 직접 읽는다
  "/robots.txt",
  "/sitemap.xml",
]);

function isPublic(pathname: string): boolean {
  if (PUBLIC_FILES.has(pathname)) return true;
  return PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p + "."),
  );
}

export function middleware(req: NextRequest) {
  const password = process.env.SITE_PASSWORD;
  if (!password) return NextResponse.next();   // 미설정이면 잠금 없음

  const { pathname } = req.nextUrl;
  if (isPublic(pathname)) return NextResponse.next();

  const header = req.headers.get("authorization") || "";
  if (header.startsWith("Basic ")) {
    // atob은 edge 런타임에 있다 (Buffer는 없다)
    const [, given] = atob(header.slice(6)).split(":");
    if (given === password) return NextResponse.next();
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="kscreener", charset="UTF-8"',
      // 잠긴 페이지는 검색에 남기지 않는다
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}

export const config = {
  // 정적 자산까지 미들웨어를 태우면 요청 수가 크게 는다 (Vercel 무료 한도).
  // 위 isPublic이 최종 판정이고, 여기서는 명백한 정적 요청만 미리 걷어낸다.
  matcher: ["/((?!_next/static|_next/image).*)"],
};
