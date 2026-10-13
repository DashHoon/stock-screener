// 배포 데이터 검사. 하나라도 어긋나면 종료 코드 1.
//
// 세 곳에서 같은 파일을 돌린다:
//   - Vercel 빌드 (package.json prebuild, web/vercel.json이 npm run build를 강제) —
//     어떤 경로로 배포하든 마지막 관문.
//     실패하면 빌드가 실패하고 직전 정상 배포가 그대로 서빙된다
//   - GitHub Actions daily-batch (data 브랜치 push 전)
//   - scripts/deploy_data.sh (수동 배포)
//
// 2026-10-13 도입. 그때까지 산출물을 검사하지 않아 결함이 앱 사용자 눈으로만
// 발견됐다: 지수가 3주 멈춰 있었고(9/17), 190종목 차트에 거래정지일 구멍이 있었고,
// 같은 날 가격이 평일(공공 API)과 주말(네이버 재백필)에 달랐다. 같은 날 새벽에는
// 다른 작업이 로컬의 구멍 난 캐시로 만든 데이터를 프로덕션에 직접 배포해 2,000여
// 종목 차트가 6주씩 비었다 — 워크플로에만 검사를 두면 이런 배포를 못 막는다.
// 표본으로는 못 잡는다(190종목은 60종목 표본에 하나도 안 걸렸다). 전 종목을 본다.
//
// 오류 (배포 중단):
//   - 지수 차트·카드가 latest.json 기준일에 끝나는가
//   - 종목·업종 차트 날짜가 거래일 달력(코스피 지수 봉 날짜)과 한 칸도 어긋나지 않는가
//   - 봉이 성립하는가 (값 > 0, 저가 ≤ 시가·종가 ≤ 고가)
//   - 같은 값이 파일마다 같은가 (latest.json 종가·등락률·스파크라인, 미니 차트)
// 경고 (진행): 하루 ±30% 초과 변동 — 수정주가 누락일 수 있다
//   (신규상장 첫날·정리매매는 정상적으로 걸린다)
//
// 사용: node web/scripts/audit-data.mjs [데이터 디렉터리]   (기본: web/public/data)
// 통과하면 데이터 디렉터리에 audit.json(검사 결과)을 남긴다.
// 데이터가 없으면(main 브랜치 미리보기 빌드) 검사할 것이 없으므로 통과한다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const LIMIT_PCT = 30;

const load = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const sameArr = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

function checkSeries(name, d, cal, calPos, latest, errors, warns) {
  let dates = d.dates;
  if (!dates || dates.length === 0) {
    errors.push(`${name}: 봉 없음`);
    return;
  }
  if (dates[dates.length - 1] !== latest) {
    errors.push(`${name}: 마지막 봉 ${dates[dates.length - 1]} ≠ 기준일 ${latest}`);
  }
  let offset = 0; // 달력보다 앞선 봉은 비교에서 뺀다
  let start = calPos.get(dates[0]);
  if (start === undefined) {
    if (dates[0] < cal[0]) {
      offset = dates.findIndex((x) => x >= cal[0]);
      dates = dates.slice(offset);
      start = 0;
    } else {
      errors.push(`${name}: 거래일이 아닌 날 ${dates[0]}`);
      return;
    }
  }
  const expect = cal.slice(start, start + dates.length);
  if (!sameArr(dates, expect)) {
    const have = new Set(dates);
    const miss = cal.slice(start).filter((x) => x <= latest && !have.has(x));
    const extra = dates.filter((x) => !calPos.has(x));
    errors.push(`${name}: 빠진 날 ${miss.length}개 [${miss.slice(0, 3)}] / 없는 날 [${extra.slice(0, 3)}]`);
    return;
  }
  const { open: o, high: h, low: lo, close: c } = d;
  const bad = [];
  for (let i = 0; i < c.length; i++) {
    if (Math.min(o[i], h[i], lo[i], c[i]) <= 0 || lo[i] > Math.min(o[i], c[i]) || h[i] < Math.max(o[i], c[i])) {
      bad.push(d.dates[i]);
    }
  }
  if (bad.length) errors.push(`${name}: 성립하지 않는 봉 ${bad.length}개 [${bad.slice(0, 3)}]`);
  for (let i = offset + 1; i < c.length; i++) {
    if (c[i - 1] > 0 && Math.abs(c[i] / c[i - 1] - 1) * 100 > LIMIT_PCT + 0.5) {
      warns.push(`${name}: ${d.dates[i]} ${c[i - 1]}→${c[i]} (${((c[i] / c[i - 1] - 1) * 100).toFixed(0)}%)`);
    }
  }
}

export function audit(dataDir) {
  const errors = [];
  const warns = [];
  const latestJson = load(path.join(dataDir, "signals", "latest.json"));
  const latest = latestJson.date;
  const chartDir = path.join(dataDir, "chart");

  // 거래일 달력 = 코스피 지수 봉 날짜 (종목과 출처가 달라 교차 검증이 된다)
  const ks = load(path.join(chartDir, "KS11.json")).tf.d;
  const cal = ks.dates.filter((x) => x <= latest);
  const calPos = new Map(cal.map((x, i) => [x, i]));
  for (const sym of ["KS11", "KQ11"]) {
    const d = load(path.join(chartDir, `${sym}.json`)).tf.d;
    const last = d.dates[d.dates.length - 1];
    if (last !== latest) errors.push(`지수 ${sym}: 마지막 봉 ${last} ≠ 기준일 ${latest}`);
    const card = (latestJson.indices || []).find((i) => i.code === sym);
    if (!card) errors.push(`지수 카드 ${sym} 없음`);
    else if (card.date !== latest) errors.push(`지수 카드 ${sym}: ${card.date} ≠ 기준일 ${latest}`);
  }

  for (const s of latestJson.stocks) {
    const name = `${s.code} ${s.name ?? ""}`;
    const p = path.join(chartDir, `${s.code}.json`);
    if (!fs.existsSync(p)) {
      errors.push(`${name}: 차트 파일 없음`);
      continue;
    }
    const d = load(p).tf.d;
    checkSeries(name, d, cal, calPos, latest, errors, warns);
    const c = d.close;
    if (s.close !== c[c.length - 1]) errors.push(`${name}: latest 종가 ${s.close} ≠ 차트 ${c[c.length - 1]}`);
    if (c.length >= 2 && s.change_pct != null) {
      if (Math.abs(s.change_pct - (c[c.length - 1] / c[c.length - 2] - 1) * 100) > 0.01) {
        errors.push(`${name}: 등락률 ${s.change_pct} ≠ 차트 기준`);
      }
    }
    if (s.m && !sameArr(s.m, c.slice(-s.m.length))) errors.push(`${name}: 스파크라인이 차트와 다름`);
    const mp = path.join(chartDir, "mini", `${s.code}.json`);
    if (!fs.existsSync(mp)) errors.push(`${name}: 미니 차트 없음`);
    else {
      const mc = load(mp).c;
      if (!sameArr(mc, c.slice(-mc.length))) errors.push(`${name}: 미니 차트가 차트와 다름`);
    }
  }

  const secDir = path.join(chartDir, "sector");
  if (fs.existsSync(secDir)) {
    for (const f of fs.readdirSync(secDir).filter((f) => f.endsWith(".json")).sort()) {
      checkSeries(`업종 ${f.slice(0, -5)}`, load(path.join(secDir, f)).tf.d, cal, calPos, latest, errors, warns);
    }
  }

  const stats = { date: latest, stocks: latestJson.stocks.length, calendarDays: cal.length,
    errors: errors.length, warnings: warns.length };
  return { errors, warns, stats };
}

function main() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const dataDir = path.resolve(process.argv[2] || path.join(here, "..", "public", "data"));
  if (!fs.existsSync(path.join(dataDir, "signals", "latest.json"))) {
    console.log(`데이터 검사: ${dataDir}에 latest.json 없음 — 건너뜀 (미리보기 빌드)`);
    return;
  }
  const { errors, warns, stats } = audit(dataDir);
  console.log(`데이터 검사: ${JSON.stringify(stats)}`);
  for (const e of errors.slice(0, 50)) console.log("  [오류]", e);
  for (const w of warns.slice(0, 20)) console.log("  [경고]", w);
  const summary = process.env.GITHUB_STEP_SUMMARY;
  if (summary) {
    const lines = [`### 데이터 검사 ${stats.date}`, "",
      `- 종목 ${stats.stocks} · 거래일 ${stats.calendarDays}`,
      `- 오류 ${stats.errors} · 경고 ${stats.warnings}`, "",
      ...errors.slice(0, 50).map((e) => `- ❌ ${e}`),
      ...warns.slice(0, 20).map((w) => `- ⚠️ ${w}`), ""];
    fs.appendFileSync(summary, lines.join("\n"));
  }
  if (errors.length) {
    console.error(`데이터 검사 실패 — 오류 ${errors.length}건, 배포하지 않는다`);
    process.exit(1);
  }
  // 통과 기록. 배포된 /data/audit.json으로 '이 배포가 검사를 거쳤는가'를 밖에서 확인한다.
  fs.writeFileSync(path.join(dataDir, "audit.json"), JSON.stringify({
    ...stats, checkedAt: new Date().toISOString(), warningSamples: warns.slice(0, 20),
  }));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
