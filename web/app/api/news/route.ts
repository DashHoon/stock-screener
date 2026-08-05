import { NextResponse } from "next/server";

/** 종목 뉴스 — 구글 뉴스 RSS를 서버에서 받아 JSON으로 돌려준다.
 *
 *  왜 서버를 거치나: 구글 뉴스 RSS에 CORS 헤더가 없어 브라우저에서 직접 못 받는다.
 *  Vercel 서버리스 함수는 호출될 때만 도는 방식이라 상시 가동 서버가 아니고
 *  고정비도 0이다 (이 프로젝트의 '서버 없음' 원칙과 충돌하지 않는다).
 *
 *  본문은 싣지 않는다. 제목·출처·시각·링크까지만 두고 클릭하면 원문으로 보낸다
 *  (본문 복제는 저작권 문제가 된다).
 */

export const runtime = "edge";
// 정적 내보내기 대상이 아님을 명시 — 요청마다 실행된다
export const dynamic = "force-dynamic";

const MAX_ITEMS = 8;
const NAME_MAX = 40;

interface NewsItem {
  title: string;
  source: string;
  url: string;
  date: string; // ISO
}

/** RSS <item>에서 필요한 값만 뽑는다. 의존성을 늘리지 않으려고 정규식으로 처리한다
 *  (구글 뉴스 RSS는 형식이 고정돼 있어 파서를 들일 만큼의 이득이 없다). */
function parseItems(xml: string): NewsItem[] {
  const out: NewsItem[] = [];
  const blocks = xml.split("<item>").slice(1);
  for (const b of blocks.slice(0, MAX_ITEMS)) {
    const pick = (tag: string) => {
      const m = b.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
      if (!m) return "";
      return m[1]
        .replace(/^<!\[CDATA\[([\s\S]*?)\]\]>$/, "$1")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, "&")
        .trim();
    };
    const rawTitle = pick("title");
    if (!rawTitle) continue;
    const source = pick("source");
    // 구글은 제목 끝에 " - 매체명"을 붙인다. 출처를 따로 보여주므로 떼어낸다.
    const title = source && rawTitle.endsWith(` - ${source}`)
      ? rawTitle.slice(0, -(source.length + 3))
      : rawTitle;
    const pub = pick("pubDate");
    out.push({
      title,
      source,
      url: pick("link"),
      date: pub ? new Date(pub).toISOString() : "",
    });
  }
  return out;
}

export async function GET(req: Request) {
  const name = (new URL(req.url).searchParams.get("name") || "").trim();
  if (!name || name.length > NAME_MAX) {
    return NextResponse.json({ items: [] }, { status: 400 });
  }

  // 종목명만으로 찾으면 '대상'·'동원'처럼 흔한 낱말인 이름에서 엉뚱한 기사가 섞인다.
  // 증권 맥락 낱말을 함께 걸어 잡음을 줄인다 (완전히 없애지는 못한다 — 화면에
  // '직접 검색' 링크를 같이 두는 이유).
  const q = `"${name}" (주가 OR 실적 OR 공시 OR 증권)`;
  const url =
    "https://news.google.com/rss/search?q=" +
    encodeURIComponent(q) +
    "&hl=ko&gl=KR&ceid=KR:ko";

  try {
    const r = await fetch(url, {
      headers: { "user-agent": "Mozilla/5.0 (compatible; kscreener/1.0)" },
      // 같은 종목을 여러 사람이 봐도 30분에 한 번만 받아온다 (함수 호출·구글 부하 절감)
      next: { revalidate: 1800 },
    });
    if (!r.ok) throw new Error(`upstream ${r.status}`);
    const items = parseItems(await r.text());
    return NextResponse.json(
      { items },
      {
        headers: {
          // CDN에 30분 보관, 이후 1시간은 갱신하는 동안 옛 응답을 계속 내보낸다
          "cache-control": "public, s-maxage=1800, stale-while-revalidate=3600",
        },
      },
    );
  } catch {
    // 뉴스는 보조 정보다. 실패해도 종목 페이지가 깨지지 않도록 빈 목록을 돌려준다.
    return NextResponse.json({ items: [] }, { status: 200 });
  }
}
