import { NextResponse } from "next/server";
import { canStore, parseReport, saveReport } from "@/lib/reports";

/** 앱의 '패턴 오류 제보'를 받는다. 주인 페이지 /reports에서 읽는다.
 *
 *  middleware.ts의 앱 전용 층(x-app-key)에 묶여 있다. 앱 열쇠는 비밀이 아니므로
 *  아무나 보낼 수 있다고 보고, 모양·길이를 여기서 엄격히 거른다. 개인정보는
 *  받지 않는다 (종목·패턴·날짜·메모·앱 버전뿐).
 *
 *  fs(로컬 개발 저장)를 쓰므로 edge가 아니라 Node 런타임이다.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY = 4_000;

export async function POST(req: Request) {
  if (!canStore()) {
    return NextResponse.json({ error: "지금은 제보를 받을 수 없습니다" }, { status: 503 });
  }
  const raw = await req.text();
  if (raw.length > MAX_BODY) {
    return NextResponse.json({ error: "본문이 너무 깁니다" }, { status: 413 });
  }
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "JSON이 아닙니다" }, { status: 400 });
  }
  const report = parseReport(body);
  if (typeof report === "string") {
    return NextResponse.json({ error: report }, { status: 400 });
  }
  try {
    await saveReport(report);
  } catch (e) {
    console.error("[report] 저장 실패", e);
    return NextResponse.json({ error: "저장하지 못했습니다" }, { status: 502 });
  }
  return NextResponse.json({ ok: true });
}
