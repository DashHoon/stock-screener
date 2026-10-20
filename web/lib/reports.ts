/** 앱에서 보낸 패턴 오류 제보.
 *
 *  저장은 Upstash Redis REST로 한다. 상시 서버 없이 API 함수가 호출될 때만
 *  쓰고, 주인 페이지(/reports)가 읽는다. 제보 하나를 JSON 문자열로 리스트
 *  `pattern_reports` 맨 앞에 넣고, 최근 MAX_KEPT건만 남긴다.
 *
 *  Supabase를 쓰려 했으나 무료 프로젝트 한도(계정당 2개)가 다른 서비스로 차
 *  있어(2026-10-20), Vercel Storage의 Upstash 연동으로 바꿨다. 연동이
 *  KV_REST_API_URL · KV_REST_API_TOKEN을 환경변수로 넣어 준다 (접두어를 바꿔
 *  만들면 UPSTASH_REDIS_REST_URL · _TOKEN). 토큰은 서버 전용 — 이 파일은
 *  API 라우트·서버 컴포넌트에서만 import한다.
 *
 *  로컬 개발에서 값이 없으면 web/.data/pattern-reports.json에 쌓는다
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

const KEY = "pattern_reports";
const ID_KEY = "pattern_reports:id";
/** 이보다 오래된 제보는 지운다 (무료 한도 256MB에 한참 못 미치지만 끝은 둔다). */
const MAX_KEPT = 5000;

function redis(): { url: string; token: string } | null {
  const url = process.env.KV_REST_API_URL ?? process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN ?? process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? { url: url.replace(/\/$/, ""), token } : null;
}

/** 명령 여러 개를 한 번에 보낸다 (Upstash REST /pipeline). 결과를 차례대로. */
async function pipeline(cmds: (string | number)[][]): Promise<unknown[]> {
  const r = redis()!;
  const res = await fetch(`${r.url}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${r.token}`, "Content-Type": "application/json" },
    body: JSON.stringify(cmds),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`upstash ${res.status}: ${await res.text()}`);
  const out = (await res.json()) as { result?: unknown; error?: string }[];
  const err = out.find((o) => o.error);
  if (err) throw new Error(`upstash: ${err.error}`);
  return out.map((o) => o.result);
}

/** 저장할 곳이 있는가. 운영에서 Redis 설정이 없으면 false. */
export function canStore(): boolean {
  return redis() !== null || process.env.NODE_ENV !== "production";
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
  if (redis()) {
    const [id] = await pipeline([["INCR", ID_KEY]]);
    const row = { ...r, id: Number(id), created_at: new Date().toISOString() };
    await pipeline([
      ["LPUSH", KEY, JSON.stringify(row)],
      ["LTRIM", KEY, 0, MAX_KEPT - 1],
    ]);
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
  if (redis()) {
    const [rows] = await pipeline([["LRANGE", KEY, 0, limit - 1]]);
    return ((rows as string[]) ?? []).map((t) => JSON.parse(t) as PatternReport);
  }
  if (process.env.NODE_ENV === "production") return null;
  return (await readDev()).reverse().slice(0, limit);
}
