// node --test web/scripts — 배포 데이터 검사가 앱에서 보였던 실제 결함을 잡는지.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { audit } from "./audit-data.mjs";

const CAL = ["2026-10-01", "2026-10-02", "2026-10-06", "2026-10-07", "2026-10-08"];

function series(dates, closes) {
  const c = closes ?? dates.map((_, i) => 100 + i);
  return { dates, open: c, high: c.map((x) => x + 1), low: c.map((x) => x - 1), close: c };
}

function write({ stocks = { "005930": series(CAL) }, cardDate = "2026-10-08", tweak } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "audit-"));
  const chart = path.join(root, "chart");
  fs.mkdirSync(path.join(chart, "mini"), { recursive: true });
  fs.mkdirSync(path.join(root, "signals"));
  for (const sym of ["KS11", "KQ11"]) {
    fs.writeFileSync(path.join(chart, `${sym}.json`), JSON.stringify({ tf: { d: series(CAL) } }));
  }
  const entries = Object.entries(stocks).map(([code, d]) => {
    fs.writeFileSync(path.join(chart, `${code}.json`), JSON.stringify({ tf: { d } }));
    fs.writeFileSync(path.join(chart, "mini", `${code}.json`), JSON.stringify({ c: d.close.slice(-3) }));
    const c = d.close;
    return { code, name: code, close: c.at(-1), m: c.slice(-3),
      change_pct: Math.round((c.at(-1) / c.at(-2) - 1) * 10000) / 100 };
  });
  const latest = { date: "2026-10-08", stocks: entries,
    indices: ["KS11", "KQ11"].map((code) => ({ code, date: cardDate })) };
  tweak?.(latest);
  fs.writeFileSync(path.join(root, "signals", "latest.json"), JSON.stringify(latest));
  return root;
}

test("정상 데이터는 통과", () => {
  const { errors, warns } = audit(write());
  assert.deepEqual(errors, []);
  assert.deepEqual(warns, []);
});

test("거래정지일 구멍은 오류 (2026-10 실제 결함, 190종목)", () => {
  const { errors } = audit(write({ stocks: { "412540": series(["2026-10-01", "2026-10-07", "2026-10-08"]) } }));
  assert.ok(errors.some((e) => e.includes("빠진 날 2개")), errors.join("\n"));
});

test("기준일에 못 미친 종목은 오류 (구멍 난 로컬 캐시로 직접 배포된 경우)", () => {
  const { errors } = audit(write({ stocks: { "000660": series(CAL.slice(0, 4)) } }));
  assert.ok(errors.some((e) => e.includes("마지막 봉 2026-10-07")), errors.join("\n"));
});

test("멈춘 지수 카드는 오류 (9/17 정체)", () => {
  const { errors } = audit(write({ cardDate: "2026-09-17" }));
  assert.ok(errors.some((e) => e.includes("지수 카드")));
});

test("latest 종가가 차트와 다르면 오류", () => {
  const { errors } = audit(write({ tweak: (j) => { j.stocks[0].close += 5; } }));
  assert.ok(errors.some((e) => e.includes("latest 종가")));
});

test("성립하지 않는 봉은 오류", () => {
  const d = series(CAL);
  d.low[2] = d.close[2] + 10;
  const { errors } = audit(write({ stocks: { X: d } }));
  assert.ok(errors.some((e) => e.includes("성립하지 않는 봉")));
});

test("가격제한폭 밖 변동은 경고만 (정리매매 등)", () => {
  const { errors, warns } = audit(write({ stocks: { "005110": series(CAL, [100, 100, 100, 100, 40]) } }));
  assert.deepEqual(errors, []);
  assert.equal(warns.length, 1);
});
