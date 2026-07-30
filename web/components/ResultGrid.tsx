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
  /** 최근 20영업일 캔들 */
  d20?: { o: number[]; h: number[]; l: number[]; c: number[] };
}

/** 격자에 그릴 방식. 두 방식 다 같은 파일에 담겨 있어 받아 놓은 데이터로 바로 전환된다.
 *  candle — 최근 20영업일 캔들. 음/양·꼬리·몸통이 보인다
 *  line   — 120봉 종가선. 패턴 전체 모양이 화면에 들어온다 */
export type MiniKind = "candle" | "line";

const W = 320;
const H = 190;
const PADX = 8;
const PADY = 10;

/** 값 → y 좌표 변환기 */
function scaleY(lo: number, hi: number) {
  const span = hi - lo || 1;
  return (v: number) => PADY + (1 - (v - lo) / span) * (H - PADY * 2);
}

/** 최근 20영업일 캔들. 봉이 적어 격자에서도 몸통·꼬리가 읽힌다. */
function CandleMini({
  d,
  pats,
  total,
}: {
  d: NonNullable<Mini["d20"]>;
  pats: Mini["pats"];
  total: number; // 패턴 좌표가 매겨진 라인 구간의 봉 수
}) {
  const n = d.c.length;
  // 패턴 좌표는 라인 구간(120봉) 기준이라 20봉 창으로 옮긴다. 패턴 대부분은
  // 20일보다 앞에서 시작해 걸러지고, 최근에 끝난 패턴의 마지막 구간만 남는다.
  const shift = total - n;
  const near = pats
    .map((p) => ({
      ...p,
      pts: p.pts.map(([i, v]) => [i - shift, v] as [number, number]).filter(([i]) => i >= 0),
    }))
    .filter((p) => p.pts.length >= 2);

  const ys = [...d.h, ...d.l];
  for (const p of near) for (const [, v] of p.pts) ys.push(v);
  const y = scaleY(Math.min(...ys), Math.max(...ys));

  const slot = (W - PADX * 2) / n;
  const bodyW = Math.min(slot * 0.62, 14);
  const cx = (i: number) => PADX + slot * (i + 0.5);

  return (
    <svg className="mini-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      {d.c.map((close, i) => {
        const open = d.o[i];
        const rise = close >= open;
        const yo = y(open);
        const yc = y(close);
        const top = Math.min(yo, yc);
        return (
          <g key={i} className={`mini-candle ${rise ? "up" : "down"}`}>
            <line x1={cx(i)} y1={y(d.h[i])} x2={cx(i)} y2={y(d.l[i])} />
            <rect
              x={cx(i) - bodyW / 2}
              y={top}
              width={bodyW}
              height={Math.max(Math.abs(yc - yo), 1)}
            />
          </g>
        );
      })}
      {near.map((p, k) => (
        <g key={`${p.k}${k}`} className="mini-pat">
          <path
            d={p.pts
              .map(([i, v], j) => `${j ? "L" : "M"}${cx(i).toFixed(1)},${y(v).toFixed(1)}`)
              .join("")}
          />
        </g>
      ))}
    </svg>
  );
}

/** 120봉 종가선. 패턴 전체 모양이 화면에 들어오는 쪽이 필요할 때 쓴다. */
function LineMini({
  closes,
  pats,
  up,
}: {
  closes: number[];
  pats: Mini["pats"];
  up: boolean;
}) {
  // 그릴 패턴 좌표까지 포함해 y 범위를 잡아야 선이 화면 밖으로 나가지 않는다
  const ys = [...closes];
  for (const p of pats) {
    for (const [, v] of p.pts) ys.push(v);
    for (const [, v] of p.pts2 ?? []) ys.push(v);
  }
  const y = scaleY(Math.min(...ys), Math.max(...ys));
  const n = closes.length;
  const x = (i: number) => PADX + (i / (n - 1)) * (W - PADX * 2);

  const poly = (pts: [number, number][]) =>
    pts.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");

  return (
    <svg className="mini-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <path
        d={closes.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("")}
        className={`mini-line ${up ? "up" : "down"}`}
      />
      {pats.map((p, k) => (
        <g key={`${p.k}${k}`} className="mini-pat">
          <path d={poly(p.pts)} />
          {p.pts2 && <path d={poly(p.pts2)} />}
        </g>
      ))}
    </svg>
  );
}

/** 미니 차트 하나. lightweight-charts 인스턴스를 12개 띄우면 무거워 SVG로 직접 그린다. */
function MiniChart({
  mini,
  kind,
  highlight,
  up,
}: {
  mini: Mini | null;
  kind: MiniKind;
  highlight: Set<string>; // 검색에 쓴 패턴 종류만 그린다
  up: boolean;
}) {
  if (!mini || mini.c.length < 2) {
    return <div className="mini-empty">차트 없음</div>;
  }
  const pats = mini.pats.filter((p) => highlight.has(p.k));
  if (kind === "candle" && mini.d20) {
    return <CandleMini d={mini.d20} pats={pats} total={mini.c.length} />;
  }
  return <LineMini closes={mini.c} pats={pats} up={up} />;
}

export default function ResultGrid({
  rows,
  page,
  perPage,
  kind,
  patKinds,
  patParam,
}: {
  rows: StockSignal[];
  page: number;
  perPage: number;
  kind: MiniKind;
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
                kind={kind}
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
