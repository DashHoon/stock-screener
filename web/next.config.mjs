// 블로그(Astro, 별도 Vercel 프로젝트)의 오리진. Vercel 환경변수 BLOG_ORIGIN 으로 주입한다.
// 설정되지 않은 환경에서는 /blog 배선 전체가 꺼진다 — 블로그 프로젝트가 아직 없는데
// 리라이트와 링크만 배포되면 /blog 가 통째로 404가 되기 때문이다.
const BLOG_ORIGIN = process.env.BLOG_ORIGIN;

/** @type {import('next').NextConfig} */
const nextConfig = {
  // 블로그는 trailingSlash: 'always' 로 빌드된다. Next 기본값(후행 슬래시 제거 308)이
  // rewrite보다 먼저 적용되면 블로그 정규 URL이 전부 깨지므로 자동 정규화를 끈다.
  // 대신 본 서비스 경로의 슬래시 제거는 아래 redirects()에서 직접 처리한다.
  skipTrailingSlashRedirect: Boolean(BLOG_ORIGIN),

  // /blog/* 는 별도 배포된 Astro 블로그로 프록시한다.
  // 서브도메인이 아니라 서브디렉터리인 이유: 블로그가 쌓는 도메인 권위를 본 서비스에 전달하기 위함.
  // ':path*' 는 세그먼트 반복이라 후행 슬래시('about/')를 매칭하지 못하고,
  // '/blog/:path(.*)' 는 '/blog/' 자체를 놓친다. 슬래시까지 파라미터에 포함시켜
  // 경로를 통째로 넘긴다. '(?:/.*)?' 로 제한해 '/blogfoo' 같은 경로는 매칭하지 않는다.
  async rewrites() {
    if (!BLOG_ORIGIN) return [];
    return [
      { source: "/blog:path((?:/.*)?)", destination: `${BLOG_ORIGIN}/blog:path` },
    ];
  },

  async redirects() {
    return [
      // 후행 슬래시 자동 정규화를 껐을 때만(= 블로그 배선이 켜졌을 때만) 본 서비스 경로의
      // 슬래시를 직접 제거한다. /blog/* 는 슬래시 URL이 정규 주소이므로 제외한다.
      ...(BLOG_ORIGIN
        ? [
            {
              source: "/:path((?!blog(?:/|$)).+)/",
              destination: "/:path",
              permanent: true,
            },
          ]
        : []),
      {
        // 구 Vercel 기본 주소로 들어오면 정식 도메인으로 308 영구 이동 (중복 색인 방지).
        // 프리뷰 배포(해시 포함 다른 호스트)는 매칭되지 않아 그대로 동작한다.
        source: "/:path*",
        has: [
          { type: "host", value: "stock-screener-flame-omega.vercel.app" },
        ],
        destination: "https://kscreener.com/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
