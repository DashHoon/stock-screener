import type { Metadata } from "next";
import Link from "next/link";
import { FLAG_BY_KEY } from "@/lib/flags";
import type { FlagKey } from "@/lib/types";
import { listReports, type PatternReport } from "@/lib/reports";
import { removeReport } from "./actions";
import DeleteButton from "./DeleteButton";

/** 앱에서 들어온 패턴 오류 제보 (주인 전용 — middleware의 SITE_PASSWORD 층). */

export const metadata: Metadata = {
  title: "패턴 오류 제보",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

function patternLabel(r: PatternReport): string {
  const get = (k: string) => FLAG_BY_KEY.get(k as FlagKey)?.label;
  // 형성 중 대칭삼각형은 kind가 pat_tri_sym이라 완성 키가 없다
  return (r.forming ? get(`${r.pattern}_form`) : undefined)
    ?? get(r.pattern)
    ?? get(`${r.pattern}_form`)
    ?? r.pattern;
}

function span(a: string | null, b: string | null): string {
  if (!a && !b) return "-";
  return `${a ?? "?"} ~ ${b ?? "?"}`;
}

function when(iso?: string): string {
  if (!iso) return "-";
  // 서버가 UTC로 돌아도 한국 시각으로 보인다
  return new Date(iso).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function ReportsPage() {
  let reports: PatternReport[] | null;
  let error: string | null = null;
  try {
    reports = await listReports();
  } catch (e) {
    reports = [];
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div className="prose reports-page">
      <h1>패턴 오류 제보</h1>
      {reports === null ? (
        <p>
          저장소가 설정되지 않았습니다. Vercel 프로젝트의 Storage에서 Upstash Redis를
          연결해 <code>KV_REST_API_URL</code>, <code>KV_REST_API_TOKEN</code>이 들어가게
          한 뒤 다시 배포해 주세요.
        </p>
      ) : error ? (
        <p>제보를 읽지 못했습니다: {error}</p>
      ) : reports.length === 0 ? (
        <p>아직 들어온 제보가 없습니다.</p>
      ) : (
        <>
          <p>
            최근 {reports.length}건 · 종목을 누르면 그 패턴을 강조한 차트가 열립니다. 처리를 마친
            제보는 맨 앞의 삭제로 지웁니다.
          </p>
          <div className="table-wrap">
            <table className="stock-table">
              <thead>
                <tr>
                  <th></th>
                  <th>접수</th>
                  <th>종목</th>
                  <th>유형</th>
                  <th>패턴</th>
                  <th>패턴 구간</th>
                  <th>고른 기간</th>
                  <th>메모</th>
                  <th>기준일 · 앱</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id ?? `${r.created_at}${r.code}`}>
                    <td>
                      {r.id != null && (
                        <DeleteButton
                          id={r.id}
                          label={`${r.name} ${patternLabel(r)}`}
                          action={removeReport}
                        />
                      )}
                    </td>
                    <td>{when(r.created_at)}</td>
                    <td className="name">
                      <Link href={`/stock/${r.code}?pat=${r.pattern}`}>{r.name}</Link>{" "}
                      <span className="code">{r.code}</span>
                    </td>
                    <td>{r.type === "missed" ? "못 찾음" : "오류"}</td>
                    <td>{patternLabel(r)}</td>
                    <td>
                      {r.type === "wrong"
                        ? `${span(r.pattern_start, r.pattern_end)}${
                            r.pattern_completed ? ` (완성 ${r.pattern_completed})` : ""
                          }`
                        : "-"}
                    </td>
                    <td>{span(r.period_from, r.period_to)}</td>
                    <td className="report-note">{r.note ?? ""}</td>
                    <td>
                      {r.data_date ?? "-"}
                      <br />
                      <span className="code">
                        {[r.platform, r.app_version].filter(Boolean).join(" ")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
