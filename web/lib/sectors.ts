/** 섹터 대분류 — batch/sectors.py의 SECTOR_ORDER와 같은 순서를 유지한다.
 *  (배치가 latest.json의 sec 필드에 이 이름들을 넣는다)
 *
 *  2026-08-13: 17 → 36개로 세분화. 큰 칸 몇 개가 맵을 먹어 안이 안 읽혔다.
 *  업종만으로 못 나누는 반도체장비·게임·디스플레이는 batch/sectors.py의
 *  OVERRIDE가 종목코드로 지정한다. */
export const SECTOR_ORDER = [
  "반도체",
  "반도체 장비",
  "전자부품",
  "디스플레이",
  "통신장비",
  "전기장비",
  "2차전지",
  "자동차·부품",
  "기계",
  "조선",
  "방산항공",
  "제약",
  "바이오",
  "의료기기",
  "소프트웨어",
  "인터넷",
  "게임",
  "기타금융·지주",
  "보험",
  "증권",
  "은행",
  "화학",
  "철강·금속",
  "시멘트",
  "제지",
  "건설",
  "부동산",
  "유통",
  "섬유·의류",
  "생활용품",
  "식음료",
  "통신서비스",
  "미디어",
  "에너지",
  "운송",
  "기타",
] as const;

export type Sector = (typeof SECTOR_ORDER)[number];

/** URL용 슬러그. 한글 URL은 인코딩되면 읽기 어려워 영문으로 고정한다. */
const SLUG: Record<string, string> = {
  반도체: "semiconductor",
  "반도체 장비": "semi-equipment",
  전자부품: "electronic-parts",
  디스플레이: "display",
  통신장비: "telecom-equipment",
  전기장비: "electrical",
  "2차전지": "battery",
  "자동차·부품": "auto",
  기계: "machinery",
  조선: "shipbuilding",
  "방산항공": "defense",
  제약: "pharma",
  바이오: "bio",
  의료기기: "medical-device",
  "소프트웨어": "software",
  "인터넷": "internet",
  게임: "game",
  "기타금융·지주": "holding",
  보험: "insurance",
  "증권": "securities",
  은행: "bank",
  화학: "chemical",
  "철강·금속": "steel",
  "시멘트": "cement",
  "제지": "paper",
  건설: "construction",
  부동산: "realestate",
  "유통": "retail",
  "섬유·의류": "textile",
  생활용품: "household",
  식음료: "food",
  통신서비스: "telecom",
  "미디어": "media",
  "에너지": "energy",
  "운송": "transport",
  기타: "etc",
};

const BY_SLUG = new Map(Object.entries(SLUG).map(([k, v]) => [v, k]));

export function sectorSlug(sector: string): string {
  return SLUG[sector] ?? "etc";
}

export function sectorFromSlug(slug: string): string | undefined {
  return BY_SLUG.get(slug);
}

export const ALL_SLUGS = Object.values(SLUG);
