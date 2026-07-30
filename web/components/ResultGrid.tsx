"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { StockSignal } from "@/lib/types";

/** 미니 차트 데이터 (chart/mini/{code}.json).
 *  좌표는 날짜가 아니라 종가 배열의 인덱스다 — 미니 차트는 시간축을 안 그린다. */
interface Mini {
  c: number[];
  pats: {
    k: string;
    g: string;
    pts: [number, number][];
    pts2?: [number, number][];
  }[];
}

const W = 260;
const H = 120;
const PAD = 6;

/** 미니 차트 하나. lightweight-charts 인스턴스를 12개 띄우면 무거워 SVG로 직접 그린다. */
function MiniChart({
  mini,
  highlight,
  up,
}: {
  mini: Mini | null;
  highlight: Set<string>; // 검색에 쓴 패턴 종류만 그린다
  up: boolean;
}) {
  if (!mini || mini.c.length < 2) {
    return <div className="mini-empty">차트 없음</div>;
  }
  // 그릴 패턴 좌표까지 포함해 y 범위를 잡아야 선이 화면 밖으로 나가지 않는다
  const pats = mini.pats.filter((p) => highlight.has(p.k));
  const ys = [...mini.c];
  for (const p of pats) {
    for (const [, v] of p.pts) ys.push(v);
    for (const [, v] of p.pts2 ?? []) ys.push(v);
  }
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  const span = hi - lo || 1;
  const n = mini.c.length;
  const x = (i: number) => PAD + (i / (n - 1)) * (W - PAD * 2);
  const y = (v: number) => PAD + (1 - (v - lo) / span) * (H - PAD * 2);

  const line = mini.c.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const poly = (pts: [number, number][]) =>
    pts.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");

  return (
    <svg className="mini-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <path d={line} className={`mini-line ${up ? "up" : "down"}`} />
      {pats.map((p, k) => (
        <g key={`${p.k}${k}`} className="mini-pat">
          <path d={poly(p.pts)} />
          {p.pts2 && <path d={poly(p.pts2)} />}
        </g>
      ))}
    </svg>
  );
}

export default function ResultGrid({
  rows,
  page,
  perPage,
  patKinds,
  patParam,
}: {
  rows: StockSignal[];
  page: number;
  perPage: number;
  /** 검색 조건에 든 패턴 종류 (미니 차트에 이것만 그린다) */
  patKinds: string[];
  patParam: string;
}) {
  const shown = useMemo(
    () => rows.slice(page * perPage, (page + 1) * perPage),
    [rows, page, perPage],
  );
  const [minis, setMinis] = useState<Record<string, Mini | null>>({});
  const cache = useRef<Record<string, Mini | null>>({});

  // 화면에 보이는 12개만 받는다. 이미 받은 종목은 캐시에서 꺼낸다.
  useEffect(() => {
    let alive = true;
    const need = shown.map((s) => s.code).filter((c) => !(c in cache.current));
    if (!need.length) {
      setMinis({ ...cache.current });
      return;
    }
    Promise.all(
      need.map(async (code) => {
        try {
          const r = await fetch(`/data/chart/mini/${code}.json`);
          cache.current[code] = r.ok ? ((await r.json()) as Mini) : null;
        } catch {
          cache.current[code] = null;
        }
      }),
    ).then(() => {
      if (alive) setMinis({ ...cache.current });
    });
    return () => {
      alive = false;
    };
  }, [shown]);

  const highlight = useMemo(() => new Set(patKinds), [patKinds]);

  return (
    <ul className="result-grid">
      {shown.map((s) => {
        const pct = s.change_pct ?? 0;
        return (
          <li key={s.code} className="grid-card">
            <Link href={`/stock/${s.code}${patParam}`} className="gc-link">
              <div className="gc-head">
                <span className="gc-name">{s.name}</span>
                <span className={pct > 0 ? "pct-up" : pct < 0 ? "pct-down" : ""}>
                  {s.change_pct == null
                    ? "-"
                    : `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`}
                </span>
              </div>
              <MiniChart
                mini={s.code in minis ? minis[s.code] : null}
                highlight={highlight}
                up={pct >= 0}
              />
              <div className="gc-foot">
                <span className="code">{s.code}</span>
                <span>{s.close.toLocaleString()}</span>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
