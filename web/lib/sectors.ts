/** 섹터 대분류 — batch/sectors.py의 SECTOR_ORDER와 같은 순서를 유지한다.
 *  (배치가 latest.json의 sec 필드에 이 이름들을 넣는다) */
export const SECTOR_ORDER = [
  "반도체",
  "IT·전자",
  "금융",
  "바이오·헬스케어",
  "조선·기계·방산",
  "2차전지",
  "소프트웨어·인터넷",
  "화학·소재",
  "자동차·부품",
  "철강·금속",
  "유통·소비재",
  "통신·미디어·엔터",
  "건설·부동산",
  "식음료",
  "운송·물류",
  "에너지·유틸리티",
  "기타",
] as const;

export type Sector = (typeof SECTOR_ORDER)[number];

/** URL용 슬러그. 한글 URL은 인코딩되면 읽기 어려워 영문으로 고정한다. */
const SLUG: Record<string, string> = {
  반도체: "semiconductor",
  "IT·전자": "it-electronics",
  금융: "financial",
  "바이오·헬스케어": "healthcare",
  "조선·기계·방산": "industrial",
  "2차전지": "battery",
  "소프트웨어·인터넷": "software",
  "화학·소재": "chemical",
  "자동차·부품": "auto",
  "철강·금속": "steel",
  "유통·소비재": "consumer",
  "통신·미디어·엔터": "media",
  "건설·부동산": "construction",
  식음료: "food",
  "운송·물류": "transport",
  "에너지·유틸리티": "energy",
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
