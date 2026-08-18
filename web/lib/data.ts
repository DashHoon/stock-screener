import { promises as fs } from "fs";
import path from "path";
import type { ChartData, LatestSignals } from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

export async function loadLatest(): Promise<LatestSignals> {
  const raw = await fs.readFile(
    path.join(DATA_DIR, "signals", "latest.json"),
    "utf-8",
  );
  return JSON.parse(raw);
}

export async function loadChart(code: string): Promise<ChartData | null> {
  try {
    const raw = await fs.readFile(
      path.join(DATA_DIR, "chart", `${code}.json`),
      "utf-8",
    );
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function listChartCodes(): Promise<string[]> {
  try {
    const files = await fs.readdir(path.join(DATA_DIR, "chart"));
    return files
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""));
  } catch {
    return [];
  }
}

/** 업종 지수 차트 (chart/sector/{slug}.json).
 *  종목 차트와 같은 형식이지만 별도 폴더에 둔다 — chart/ 바로 아래 두면
 *  listChartCodes가 종목으로 착각해 /stock/{slug} 페이지가 생긴다. */
export async function loadSectorChart(slug: string): Promise<ChartData | null> {
  try {
    const buf = await fs.readFile(
      path.join(DATA_DIR, "chart", "sector", `${slug}.json`),
      "utf-8",
    );
    return JSON.parse(buf) as ChartData;
  } catch {
    return null;
  }
}
