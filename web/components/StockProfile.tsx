import Link from "next/link";
import { sectorSlug } from "@/lib/sectors";
import type { ChartData } from "@/lib/types";

/** 종목 개요 — '이 회사가 뭘 하는 회사인가'.
 *
 *  전부 KRX 상장법인 공시 정보다 (주요제품·상장일·대표자·홈페이지·소재지).
 *  배치가 업종을 받을 때 같은 응답에 들어 있어 따로 받아올 필요가 없었다.
 *
 *  회사 소개를 문장으로 지어내지 않는다 — 사실만 표에 놓고, 판단은 읽는 사람이
 *  한다. 자동 생성 문장 5,000개는 그 자체로 저품질이기도 하다.
 */
/** 은/는 — 받침이 있으면 '은'. 한글 음절은 유니코드 AC00부터 28자씩 한 초성이라
 *  (코드 - 0xAC00) % 28 이 종성 인덱스다 (0이면 받침 없음).
 *  이름이 영문·숫자로 끝나면(예: NAVER, POSCO홀딩스는 한글) '은'으로 둔다. */
function eunNeun(word: string): string {
  const c = word.trim().slice(-1).charCodeAt(0);
  if (c >= 0xac00 && c <= 0xd7a3) return (c - 0xac00) % 28 === 0 ? "는" : "은";
  return "은";
}

export default function StockProfile({ data }: { data: ChartData }) {
  const p = data.profile;
  if (!p) return null;

  const rows: [string, React.ReactNode][] = [];
  if (p.products) rows.push(["주요 제품·사업", p.products]);
  if (p.industry) {
    rows.push([
      "업종",
      p.sector ? (
        <>
          {p.industry} · 섹터{" "}
          <Link href={`/map/${sectorSlug(p.sector)}`}>{p.sector}</Link>
        </>
      ) : (
        p.industry
      ),
    ]);
  }
  const listing: string[] = [];
  if (p.market) listing.push(p.market);
  if (p.listed) listing.push(`${p.listed} 상장`);
  if (typeof p.cap === "number" && p.cap > 0) {
    listing.push(
      p.cap >= 10000
        ? `시가총액 ${(p.cap / 10000).toFixed(1)}조원`
        : `시가총액 ${p.cap.toLocaleString("ko-KR")}억원`,
    );
  }
  if (listing.length) rows.push(["상장", listing.join(" · ")]);

  const etc: string[] = [];
  if (p.ceo) etc.push(`대표 ${p.ceo}`);
  if (p.region) etc.push(p.region);
  if (etc.length) rows.push(["회사", etc.join(" · ")]);
  if (p.homepage) {
    rows.push([
      "홈페이지",
      <a key="hp" href={p.homepage} target="_blank" rel="noopener noreferrer nofollow">
        {p.homepage.replace(/^https?:\/\//, "").replace(/\/$/, "")} ↗
      </a>,
    ]);
  }
  if (!rows.length) return null;

  return (
    <section className="profile">
      <h2>
        {data.name}
        {eunNeun(data.name)} 어떤 회사인가
      </h2>
      <table className="profile-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th scope="row">{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="profile-foot">
        KRX 상장법인 공시 정보입니다. 회사가 제출한 내용을 그대로 옮겼으며 본
        서비스의 평가가 아닙니다.
      </p>
    </section>
  );
}
