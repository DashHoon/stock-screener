"use client";

import { useEffect, useRef, useState } from "react";
import { FLAG_BY_KEY } from "@/lib/flags";
import type { FlagKey } from "@/lib/types";

// 스크리너 FlagKey → 백테스트 데이터셋 시그널 키 매핑.
// 상태형(과매도/과매수)은 진입 트리거가 되는 이벤트로 치환. 미지원(스퀴즈)은 제외.
const BT_KEY: Partial<Record<FlagKey, string>> = {
  rsi_oversold: "rsi_cross_up_30",
  rsi_overbought: "rsi_cross_down_70",
};
function toBtKey(k: FlagKey): string | null {
  if (k === "bb_squeeze") return null;
  return BT_KEY[k] ?? k;
}

interface HStat { n: number; win: number; mean: number; median: number }
interface Result {
  horizons: number[];
  results: Record<string, HStat | null>;
  baseline: Record<string, HStat | null>;
  entries: number;
  stocksHit: number;
  universe: number;
  date: string;
}

export default function BacktestPanel({
  selected,
  windowBars,
  minCap,
}: {
  selected: FlagKey[];
  windowBars: number;
  minCap: number;
}) {
  const workerRef = useRef<Worker | null>(null);
  const sigKeysRef = useRef<string[] | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => workerRef.current?.terminate(), []);

  const btKeys = selected
    .map(toBtKey)
    .filter((x): x is string => x !== null);
  const unsupported = selected.filter((k) => toBtKey(k) === null);

  function dispatchRun() {
    const w = workerRef.current!;
    const sigKeys = sigKeysRef.current!;
    const sigIdxs = btKeys.map((k) => sigKeys.indexOf(k)).filter((i) => i >= 0);
    w.postMessage({ type: "run", sigIdxs, windowBars, minCap });
  }

  function run() {
    if (!btKeys.length) return;
    setError(null);
    setResult(null);
    setRunning(true);

    if (!workerRef.current) {
      const w = new Worker("/bt-worker.js");
      workerRef.current = w;
      w.onmessage = (ev) => {
        const m = ev.data;
        if (m.type === "loaded") {
          sigKeysRef.current = m.sigKeys;
          dispatchRun();
        } else if (m.type === "result") {
          setResult(m);
          setRunning(false);
        } else if (m.type === "error") {
          setError(m.message);
          setRunning(false);
        }
      };
    }

    if (sigKeysRef.current) {
      dispatchRun(); // 이미 로드됨 → 바로 실행
    } else {
      workerRef.current.postMessage({ type: "load", url: "/data/bt/dataset.json" });
    }
  }

  const labels = selected
    .filter((k) => toBtKey(k))
    .map((k) => FLAG_BY_KEY.get(k)?.label ?? k)
    .join(" + ");

  return (
    <div className="bt-panel">
      <div className="bt-head">
        <div>
          <strong>선택 조건 백테스트</strong>
          <span className="bt-sub">
            {btKeys.length
              ? `${labels} — 지난 10년 대형주에서 이 조건이 겹쳐 발생한 뒤의 수익률`
              : "위에서 지표를 선택하면 이 조건의 과거 성과를 계산합니다"}
          </span>
        </div>
        <button
          type="button"
          className="bt-run"
          disabled={!btKeys.length || running}
          onClick={run}
        >
          {running ? "계산 중…" : "백테스트 실행"}
        </button>
      </div>

      {unsupported.length > 0 && (
        <p className="bt-warn">
          백테스트 미지원 지표 제외:{" "}
          {unsupported.map((k) => FLAG_BY_KEY.get(k)?.label ?? k).join(", ")}
        </p>
      )}
      {error && <p className="bt-warn">오류: {error}</p>}

      {result && (
        <div className="bt-result">
          <p className="bt-meta">
            {result.date} 기준 · 대상 {result.universe.toLocaleString()}종목 중{" "}
            {result.stocksHit.toLocaleString()}종목에서{" "}
            {result.entries.toLocaleString()}회 발생
            {windowBars > 0 ? ` · 조건이 최근 ${windowBars}거래일 내 겹친 날 진입` : " · 당일 동시 발생일 진입"}
          </p>
          <div className="table-wrap">
            <table className="stock-table stats-table">
              <thead>
                <tr>
                  <th>보유기간</th>
                  <th className="num">표본</th>
                  <th className="num">승률</th>
                  <th className="num">평균</th>
                  <th className="num">시장 대비</th>
                </tr>
              </thead>
              <tbody>
                {result.horizons.map((h) => {
                  const r = result.results[h];
                  const b = result.baseline[h];
                  if (!r)
                    return (
                      <tr key={h}>
                        <td>{h}거래일</td>
                        <td className="num" colSpan={4}>표본 없음</td>
                      </tr>
                    );
                  const rel = b ? +(r.mean - b.mean).toFixed(2) : null;
                  return (
                    <tr key={h}>
                      <td>{h}거래일</td>
                      <td className="num">{r.n.toLocaleString()}</td>
                      <td className="num">{r.win}%</td>
                      <td className={`num ${r.mean > 0 ? "pct-up" : r.mean < 0 ? "pct-down" : ""}`}>
                        {r.mean > 0 ? "+" : ""}{r.mean}%
                      </td>
                      <td className={`num ${rel && rel > 0 ? "pct-up" : rel && rel < 0 ? "pct-down" : ""}`}>
                        {rel == null ? "-" : `${rel > 0 ? "+" : ""}${rel}%p`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="bt-disc">
            과거 통계이며 미래 수익을 보장하지 않습니다. 상장 대형주(시총 상위 약 800)
            기준, 수수료·세금 미반영, 상장폐지 종목 제외(생존편향). 정보 제공이며 투자
            판단·책임은 본인에게 있습니다.
          </p>
        </div>
      )}
    </div>
  );
}
