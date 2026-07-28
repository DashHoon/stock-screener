"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { squarify, changeColor, labelSize, type Tile } from "@/lib/treemap";
import type { LatestSignals, StockSignal } from "@/lib/types";
import { SECTOR_ORDER, sectorSlug } from "@/lib/sectors";

// 타일 넓이를 시가총액에 그대로 비례시키면 한 종목이 화면을 다 먹는다
// (반도체 섹터에서 SK하이닉스 1,104조 : 2위 약 10조 = 110:1). 제곱근으로 압축해
// 순서와 규모감은 유지하면서 작은 종목도 보이게 한다.
const AREA_EXP = 0.5;
const area = (cap: number) => Math.pow(Math.max(cap, 0), AREA_EXP);

// 2단계에서 한 화면에 그릴 최대 종목 수. 이 이상은 타일이 1px대라 못 읽는다.
const MAX_TILES = 45;

interface Node {
  key: string;
  value: number; // 타일 넓이 (시가총액을 압축한 값)
  change: number | null; // 시총가중 등락률 (타일 색)
  label: string;
  href?: string; // 종목 타일이면 상세 페이지
  count?: number;
}

/** 시가총액 가중 평균 등락률. 단순 평균을 쓰면 소형주 급등이 섹터 색을 뒤집는다. */
function weightedChange(items: StockSignal[]): number | null {
  let w = 0;
  let sum = 0;
  for (const s of items) {
    const cap = s.cap ?? 0;
    if (cap <= 0 || s.change_pct == null) continue;
    w += cap;
    sum += cap * s.change_pct;
  }
  return w > 0 ? sum / w : null;
}

function group(stocks: StockSignal[], by: (s: StockSignal) => string): Map<string, StockSignal[]> {
  const m = new Map<string, StockSignal[]>();
  for (const s of stocks) {
    const k = by(s) || "기타";
    const arr = m.get(k);
    if (arr) arr.push(s);
    else m.set(k, [s]);
  }
  return m;
}

export default function SectorMap({
  data,
  sector,
}: {
  data: LatestSignals;
  sector?: string; // 있으면 그 섹터로 드릴다운된 상태
}) {
  const router = useRouter();
  const boxRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  // 컨테이너 크기를 재서 그린다 (창 크기·회전에 따라 다시 계산)
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      // 세로는 화면 비율에 맞춘다. 모바일에서 가로로 납작하면 타일이 못 읽힌다.
      const h = w < 560 ? Math.round(w * 1.25) : Math.round(Math.min(w * 0.58, 640));
      setSize({ w, h });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const nodes: Node[] = useMemo(() => {
    const pool = sector
      ? data.stocks.filter((s) => (s.sec || "기타") === sector)
      : data.stocks;

    if (!sector) {
      // 1단계: 섹터별
      const g = group(pool, (s) => s.sec || "기타");
      return SECTOR_ORDER.filter((k) => g.has(k)).map((k) => {
        const items = g.get(k)!;
        return {
          key: k,
          label: k,
          value: area(items.reduce((a, b) => a + Math.max(b.cap ?? 0, 0), 0)),
          change: weightedChange(items),
          count: items.length,
          href: `/map/${sectorSlug(k)}`,
        };
      });
    }
    // 2단계: 그 섹터의 개별 종목 (시총 상위만)
    return [...pool]
      .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
      .slice(0, MAX_TILES)
      .map((s) => ({
        key: s.code,
        label: s.name,
        value: area(s.cap ?? 0),
        change: s.change_pct ?? null,
        href: `/stock/${s.code}`,
      }));
  }, [data, sector]);

  const tiles: Tile<Node>[] = useMemo(
    () => (size.w > 0 ? squarify(nodes, size.w, size.h) : []),
    [nodes, size],
  );

  return (
    <div className="treemap-wrap" ref={boxRef} style={{ height: size.h || undefined }}>
      {tiles.map((t) => {
        const font = labelSize(t.w, t.h, t.item.label);
        const pct = t.item.change;
        const body = (
          <>
            {font && (
              <span className="tm-label" style={{ fontSize: font.name }}>
                <span className="tm-name">{t.item.label}</span>
                {t.h > 34 && (
                  <span className="tm-pct" style={{ fontSize: font.pct }}>
                    {pct == null ? "-" : `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`}
                  </span>
                )}
              </span>
            )}
          </>
        );
        const style = {
          left: t.x,
          top: t.y,
          width: t.w,
          height: t.h,
          background: changeColor(pct),
        };
        const title = `${t.item.label} ${pct == null ? "" : `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`}`;
        return t.item.href ? (
          <Link
            key={t.item.key}
            href={t.item.href}
            className="tm-tile"
            style={style}
            title={title}
            prefetch={false}
          >
            {body}
          </Link>
        ) : (
          <div key={t.item.key} className="tm-tile" style={style} title={title}>
            {body}
          </div>
        );
      })}
      {tiles.length === 0 && <p className="notice">불러오는 중…</p>}
      {/* 드릴다운 상태에서 스와이프 대신 쓸 상위 복귀 (뒤로가기도 동작) */}
      {sector && (
        <button type="button" className="tm-up" onClick={() => router.push("/map")}>
          ↑ 전체 업종
        </button>
      )}
    </div>
  );
}
