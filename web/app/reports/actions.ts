"use server";

import { revalidatePath } from "next/cache";
import { deleteReport } from "@/lib/reports";

/** /reports의 '삭제'. 이 페이지 주소로 POST되므로 middleware의 주인 비밀번호
 *  (SITE_PASSWORD) 층을 그대로 거친다 — 앱 열쇠로는 지울 수 없다. */
export async function removeReport(formData: FormData): Promise<void> {
  const id = Number(formData.get("id"));
  if (!Number.isInteger(id) || id <= 0) return;
  await deleteReport(id);
  revalidatePath("/reports");
}
