/** 앱에서 보낸 패턴 오류 제보.
 *
 *  저장은 Supabase(Postgres) REST로 한다. 상시 서버 없이 API 함수가 호출될 때만
 *  쓰고, 주인 페이지(/reports)가 읽는다. 테이블은 supabase/pattern_reports.sql.
 *
 *  환경변수 SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY (Vercel, 서버 전용).
 *  service_role 키는 RLS를 건너뛰므로 브라우저·앱으로 절대 내보내지 않는다 —
 *  이 파일은 서버(API 라우트·서버 컴포넌트)에서만 import한다.
 *
 *  로컬 개발에서 두 값이 없으면 web/.data/pattern-reports.json에 쌓는다
 *  (앱 → 사이트 → 목록을 끝까지 확인하려고). 운영에서 없으면 받지 않는다.
 */
import { promises as fs } from "fs";
import path from "path";

export type ReportType = "missed" | "wrong";

export interface PatternReport {
  id?: number;
  created_at?: string;
  code: string;
  name: string;
  type: ReportType;
  /** 차트 패턴 종류 (pat_double_bottom 등, 형성 중도 _form 없이) */
  pattern: string;
  /** 오류 제보일 때 그 패턴 하나를 찾아가는 좌표 */
  forming: boolean | null;
  pattern_start: string | null;
  pattern_end: string | null;
  pattern_completed: string | null;
  /** 사용자가 고른 기간 (선택) */
  period_from: string | null;
  period_to: string | null;
  note: string | null;
  /** 사용자가 본 데이터 기준일 */
  data_date: string | null;
  app_version: string | null;
  platform: string | null;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const CODE = /^[0-9A-Z]{6}$/;
const PATTERN = /^pat_[a-z0-9_]{2,40}$/;

function str(v: unknown, max: number): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim().slice(0, max);
  return t || null;
}

function date(v: unknown): string | null {
  return typeof v === "string" && DATE.test(v) ? v : null;
}

/** 받은 JSON을 검사해 저장할 모양으로. 틀리면 이유를 문자열로 돌려준다. */
export function parseReport(body: unknown): PatternReport | string {
  if (!body || typeof body !== "object") return "본문이 없습니다";
  const b = body as Record<string, unknown>;
  const code = typeof b.code === "string" ? b.code.trim() : "";
  if (!CODE.test(code)) return "종목 코드가 올바르지 않습니다";
  const type = b.type;
  if (type !== "missed" && type !== "wrong") return "제보 유형이 올바르지 않습니다";
  const pattern = typeof b.pattern === "string" ? b.pattern.trim() : "";
  if (!PATTERN.test(pattern)) return "패턴이 올바르지 않습니다";

  const inst = (b.instance ?? {}) as Record<string, unknown>;
  const period = (b.period ?? {}) as Record<string, unknown>;
  let from = date(period.from);
  let to = date(period.to);
  if (from && to && from > to) [from, to] = [to, from];

  return {
    code,
    name: str(b.name, 60) ?? code,
    type,
    pattern,
    forming: type === "wrong" && typeof inst.forming === "boolean" ? inst.forming : null,
    pattern_start: type === "wrong" ? date(inst.start) : null,
    pattern_end: type === "wrong" ? date(inst.end) : null,
    pattern_completed: type === "wrong" ? date(inst.completed) : null,
    period_from: from,
    period_to: to,
    note: str(b.note, 300),
    data_date: date(b.data_date),
    app_version: str(b.app_version, 40),
    platform: str(b.platform, 40),
  };
}

function supabase(): { url: string; key: string } | null {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  return url && key ? { url: url.replace(/\/$/, ""), key } : null;
}

/** 저장할 곳이 있는가. 운영에서 Supabase 설정이 없으면 false. */
export function canStore(): boolean {
  return supabase() !== null || process.env.NODE_ENV !== "production";
}

const DEV_FILE = path.join(process.cwd(), ".data", "pattern-reports.json");

async function readDev(): Promise<PatternReport[]> {
  try {
    return JSON.parse(await fs.readFile(DEV_FILE, "utf-8")) as PatternReport[];
  } catch {
    return [];
  }
}

export async function saveReport(r: PatternReport): Promise<void> {
  const sb = supabase();
  if (sb) {
    const res = await fetch(`${sb.url}/rest/v1/pattern_reports`, {
      method: "POST",
      headers: {
        apikey: sb.key,
        Authorization: `Bearer ${sb.key}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(r),
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`supabase ${res.status}: ${await res.text()}`);
    return;
  }
  if (process.env.NODE_ENV === "production") throw new Error("저장소 미설정");
  const all = await readDev();
  all.push({ ...r, id: all.length + 1, created_at: new Date().toISOString() });
  await fs.mkdir(path.dirname(DEV_FILE), { recursive: true });
  await fs.writeFile(DEV_FILE, JSON.stringify(all, null, 2));
}

/** 최근 제보부터. 저장소가 없으면 null (페이지가 설정 안내를 띄운다). */
export async function listReports(limit = 300): Promise<PatternReport[] | null> {
  const sb = supabase();
  if (sb) {
    const res = await fetch(
      `${sb.url}/rest/v1/pattern_reports?select=*&order=created_at.desc&limit=${limit}`,
      {
        headers: { apikey: sb.key, Authorization: `Bearer ${sb.key}` },
        cache: "no-store",
      },
    );
    if (!res.ok) throw new Error(`supabase ${res.status}: ${await res.text()}`);
    return (await res.json()) as PatternReport[];
  }
  if (process.env.NODE_ENV === "production") return null;
  return (await readDev()).reverse().slice(0, limit);
}
