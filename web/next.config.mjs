/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
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
