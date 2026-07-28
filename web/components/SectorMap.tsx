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
const area = (cap: number) => Math.sqrt(Math.max(cap, 0));

// 2단계(섹터 페이지)에서 한 화면에 그릴 최대 종목 수
const MAX_TILES = 45;

// 1단계 섹터 타일 안에 종목을 겹쳐 그릴 최소 크기와 머리글 높이
const NEST_MIN_W = 92;
const NEST_MIN_H = 76;
const HEAD_H = 19;
// 종목 타일 하나에 필요한 최소 넓이(px²) — 섹터마다 몇 종목을 넣을지 여기서 정해진다
const PX_PER_STOCK = 2100;

interface Node {
  key: string;
  value: number; // 타일 넓이 (시가총액을 압축한 값)
  change: number | null;
  label: string;
  href?: string;
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

function pctText(p: number | null): string {
  return p == null ? "-" : `${p > 0 ? "+" : ""}${p.toFixed(2)}%`;
}

function stockNode(s: StockSignal): Node {
  return {
    key: s.code,
    label: s.name,
    value: area(s.cap ?? 0),
    change: s.change_pct ?? null,
    href: `/stock/${s.code}`,
  };
}

/** 타일 하나. 라벨 크기는 타일 크기와 이름 길이에 맞춰 계산한다. */
function TileBox({ t, cls }: { t: Tile<Node>; cls: string }) {
  const font = labelSize(t.w, t.h, t.item.label);
  const inner = font ? (
    <span className="tm-label" style={{ fontSize: font.name }}>
      <span className="tm-name" style={{ WebkitLineClamp: font.lines }}>
        {t.item.label}
      </span>
      {font.pct > 0 && (
        <span className="tm-pct" style={{ fontSize: font.pct }}>
          {pctText(t.item.change)}
        </span>
      )}
    </span>
  ) : null;
  const style = {
    left: t.x,
    top: t.y,
    width: t.w,
    height: t.h,
    background: changeColor(t.item.change),
  };
  const title = `${t.item.label} ${pctText(t.item.change)}`;
  return t.item.href ? (
    <Link href={t.item.href} className={cls} style={style} title={title} prefetch={false}>
      {inner}
    </Link>
  ) : (
    <div className={cls} style={style} title={title}>
      {inner}
    </div>
  );
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

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      // 좁은 화면은 세로로 길게 잡아야 타일이 읽힌다
      const h = w < 560 ? Math.round(w * 1.35) : Math.round(Math.min(w * 0.62, 700));
      setSize({ w, h });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /** 2단계(섹터 페이지): 그 섹터 종목만 평면으로 */
  const flatTiles = useMemo(() => {
    if (!sector || size.w <= 0) return [];
    const pool = data.stocks.filter((s) => (s.sec || "기타") === sector);
    const nodes = [...pool]
      .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0))
      .slice(0, MAX_TILES)
      .map(stockNode);
    return squarify(nodes, size.w, size.h);
  }, [data, sector, size]);

  /** 1단계: 섹터 사각형 + 그 안에 대형 종목 중첩 */
  const groups = useMemo(() => {
    if (sector || size.w <= 0) return [];
    const bySec = new Map<string, StockSignal[]>();
    for (const s of data.stocks) {
      const k = s.sec || "기타";
      const arr = bySec.get(k);
      if (arr) arr.push(s);
      else bySec.set(k, [s]);
    }
    const nodes: Node[] = SECTOR_ORDER.filter((k) => bySec.has(k)).map((k) => {
      const items = bySec.get(k)!;
      return {
        key: k,
        label: k,
        value: area(items.reduce((a, b) => a + Math.max(b.cap ?? 0, 0), 0)),
        change: weightedChange(items),
        href: `/map/${sectorSlug(k)}`,
      };
    });

    return squarify(nodes, size.w, size.h).map((g) => {
      const items = (bySec.get(g.item.key) ?? [])
        .slice()
        .sort((a, b) => (b.cap ?? 0) - (a.cap ?? 0));
      // 작은 섹터 칸에 종목을 우겨넣으면 아무것도 안 읽힌다 — 섹터 이름만 남긴다
      if (g.w < NEST_MIN_W || g.h < NEST_MIN_H) {
        return { g, nested: false, inner: [] as Tile<Node>[] };
      }
      const innerH = g.h - HEAD_H;
      const count = Math.max(1, Math.min(24, Math.floor((g.w * innerH) / PX_PER_STOCK)));
      const inner = squarify(items.slice(0, count).map(stockNode), g.w, innerH);
      return { g, nested: true, inner };
    });
  }, [data, sector, size]);

  return (
    <div className="treemap-wrap" ref={boxRef} style={{ height: size.h || undefined }}>
      {/* 섹터 페이지 — 종목만 */}
      {sector && flatTiles.map((t) => <TileBox key={t.item.key} t={t} cls="tm-tile" />)}

      {/* 전체 맵 — 섹터 상자 안에 대형 종목 */}
      {!sector &&
        groups.map(({ g, nested, inner }) => (
          <div
            key={g.item.key}
            className="tm-group"
            style={{ left: g.x, top: g.y, width: g.w, height: g.h }}
          >
            {nested ? (
              <>
                <Link
                  href={g.item.href!}
                  className="tm-group-head"
                  style={{ height: HEAD_H, background: changeColor(g.item.change) }}
                  title={`${g.item.label} ${pctText(g.item.change)}`}
                >
                  <span className="tm-group-name">{g.item.label}</span>
                  <span className="tm-group-pct">{pctText(g.item.change)}</span>
                </Link>
                <div className="tm-group-body" style={{ top: HEAD_H }}>
                  {inner.map((t) => (
                    <TileBox key={t.item.key} t={t} cls="tm-tile tm-sub" />
                  ))}
                </div>
              </>
            ) : (
              <TileBox t={{ item: g.item, x: 0, y: 0, w: g.w, h: g.h }} cls="tm-tile" />
            )}
          </div>
        ))}

      {size.w > 0 && flatTiles.length === 0 && groups.length === 0 && (
        <p className="notice">불러오는 중…</p>
      )}
      {sector && (
        <button type="button" className="tm-up" onClick={() => router.push("/map")}>
          ↑ 전체 업종
        </button>
      )}
    </div>
  );
}
