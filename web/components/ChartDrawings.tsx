"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, Time, UTCTimestamp } from "lightweight-charts";

/** 가격축 변환에 쓰는 시리즈 (캔들 또는 라인) */
export type PriceSeries = ISeriesApi<"Candlestick"> | ISeriesApi<"Line">;

/** 추세선·박스는 화면 좌표가 아니라 (시간, 가격)으로 저장한다.
 *  픽셀로 저장하면 확대·이동할 때 캔들과 따로 놀아 쓸모가 없다. */
export interface Shape {
  id: string;
  type: "line" | "box";
  t1: number; // UTC seconds
  p1: number;
  t2: number;
  p2: number;
}

export type DrawTool = "line" | "box" | null;

type Drag =
  | { kind: "new"; type: "line" | "box"; t1: number; p1: number }
  | { kind: "handle"; id: string; end: "a" | "b" }
  | { kind: "move"; id: string; t0: number; p0: number; orig: Shape };

const HANDLE_R = 5;

export default function ChartDrawings({
  chart,
  series,
  enabled,
  tool,
  onToolDone,
  shapes,
  setShapes,
  paneHeight,
  version,
}: {
  chart: IChartApi | null;
  series: PriceSeries | null;
  /** 그리기 모드. 꺼져 있으면 그려진 도형은 보이기만 하고 손댈 수 없다
   *  (차트를 보다가 실수로 선을 끌어 옮기는 사고를 막는다). */
  enabled: boolean;
  tool: DrawTool;
  onToolDone: () => void;
  shapes: Shape[];
  setShapes: (fn: (prev: Shape[]) => Shape[]) => void;
  paneHeight: number;
  version: number; // 차트가 다시 그려질 때 올라간다 (좌표 재계산 트리거)
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [draft, setDraft] = useState<Shape | null>(null);
  // pointerup 핸들러는 등록 시점의 draft를 붙잡는다. 드래그 중 상태가 바뀌어도
  // 마지막 값을 읽도록 ref를 같이 둔다 (안 그러면 길이 0으로 판단해 버려진다).
  const draftRef = useRef<Shape | null>(null);
  const [, force] = useState(0);

  // 확대·이동하면 좌표가 달라지므로 다시 그린다
  useEffect(() => {
    if (!chart) return;
    const redraw = () => force((v) => v + 1);
    const tsApi = chart.timeScale();
    tsApi.subscribeVisibleLogicalRangeChange(redraw);
    redraw();
    return () => tsApi.unsubscribeVisibleLogicalRangeChange(redraw);
  }, [chart, version]);

  const toX = useCallback(
    (t: number) => chart?.timeScale().timeToCoordinate(t as UTCTimestamp) ?? null,
    [chart],
  );
  const toY = useCallback((p: number) => series?.priceToCoordinate(p) ?? null, [series]);

  /** 화면 좌표 → (시간, 가격).
   *
   *  레이어가 차트 전체를 덮으므로 거래량·RSI 패널 위에서도 눌릴 수 있다. 그 높이는
   *  가격 시리즈의 좌표계 밖이라 coordinateToPrice가 null을 돌려주고, 그대로 두면
   *  "눌렀는데 아무 일도 안 일어나는" 상태가 된다. 가격 패널 안으로 끌어와 변환한다.
   *  시간축도 마찬가지로 데이터 밖(오른쪽 여백)을 누르면 null이라 안쪽으로 당긴다. */
  const fromPointer = useCallback(
    (e: { clientX: number; clientY: number }) => {
      const svg = svgRef.current;
      if (!svg || !chart || !series) return null;
      const r = svg.getBoundingClientRect();
      const x0 = e.clientX - r.left;
      const y0 = e.clientY - r.top;

      let t: Time | null = null;
      for (const x of [x0, Math.min(x0, r.width - 2), Math.max(x0, 2)]) {
        t = chart.timeScale().coordinateToTime(x) as Time | null;
        if (t != null) break;
      }
      if (t == null) return null;

      let p = series.coordinateToPrice(y0);
      if (p == null) {
        // 유효한 가장 아래 y를 이분 탐색으로 찾아 거기로 붙인다
        let lo = 0;
        let hi = y0;
        if (series.coordinateToPrice(lo) == null) return null;
        for (let i = 0; i < 12 && hi - lo > 1; i++) {
          const mid = (lo + hi) / 2;
          if (series.coordinateToPrice(mid) != null) lo = mid;
          else hi = mid;
        }
        p = series.coordinateToPrice(lo);
      }
      if (p == null) return null;
      return { t: Number(t), p: Number(p) };
    },
    [chart, series],
  );

  // 그리기·조절 중에는 문서 전체에서 포인터를 추적한다 (차트 밖으로 나가도 이어지게)
  useEffect(() => {
    if (!drag) return;
    const move = (e: PointerEvent) => {
      const c = fromPointer(e);
      if (!c) return;
      if (drag.kind === "new") {
        const next: Shape = {
          id: "draft",
          type: drag.type,
          t1: drag.t1,
          p1: drag.p1,
          t2: c.t,
          p2: c.p,
        };
        draftRef.current = next;
        setDraft(next);
      } else if (drag.kind === "handle") {
        setShapes((prev) =>
          prev.map((s) =>
            s.id !== drag.id
              ? s
              : drag.end === "a"
                ? { ...s, t1: c.t, p1: c.p }
                : { ...s, t2: c.t, p2: c.p },
          ),
        );
      } else {
        const dt = c.t - drag.t0;
        const dp = c.p - drag.p0;
        setShapes((prev) =>
          prev.map((s) =>
            s.id !== drag.id
              ? s
              : {
                  ...s,
                  t1: drag.orig.t1 + dt,
                  p1: drag.orig.p1 + dp,
                  t2: drag.orig.t2 + dt,
                  p2: drag.orig.p2 + dp,
                },
          ),
        );
      }
    };
    const up = () => {
      const cur = draftRef.current;
      if (drag.kind === "new" && cur) {
        // 클릭만 하고 끌지 않은 경우는 도형으로 만들지 않는다
        const dx = Math.abs((toX(cur.t2) ?? 0) - (toX(cur.t1) ?? 0));
        const dy = Math.abs((toY(cur.p2) ?? 0) - (toY(cur.p1) ?? 0));
        if (dx + dy > 8) {
          const id = `d${Date.now().toString(36)}`;
          setShapes((prev) => [...prev, { ...cur, id }]);
          setSelected(id);
        }
        draftRef.current = null;
        setDraft(null);
        onToolDone();
      }
      setDrag(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [drag, fromPointer, setShapes, onToolDone, toX, toY]);

  useEffect(() => {
    if (!enabled) setSelected(null);
  }, [enabled]);

  // Delete 키로 선택한 도형 삭제
  useEffect(() => {
    if (!selected || !enabled) return;
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA)$/.test(t.tagName)) return;
      e.preventDefault();
      setShapes((prev) => prev.filter((s) => s.id !== selected));
      setSelected(null);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [selected, enabled, setShapes]);

  if (!chart || !series) return null;

  const active = enabled && (tool !== null || drag !== null);
  const all = draft ? [...shapes, draft] : shapes;

  return (
    <svg
      ref={svgRef}
      className={`draw-layer${active ? " active" : ""}${
        enabled && tool ? " pen" : ""
      }${enabled ? "" : " locked"}`}
      style={{ height: paneHeight }}
      onPointerDown={(e) => {
        if (!enabled || !tool) return;
        const c = fromPointer(e);
        if (!c) return;
        e.preventDefault();
        setSelected(null);
        setDrag({ kind: "new", type: tool, t1: c.t, p1: c.p });
        const d0: Shape = { id: "draft", type: tool, t1: c.t, p1: c.p, t2: c.t, p2: c.p };
        draftRef.current = d0;
        setDraft(d0);
      }}
    >
      {all.map((s) => {
        const x1 = toX(s.t1);
        const y1 = toY(s.p1);
        const x2 = toX(s.t2);
        const y2 = toY(s.p2);
        if (x1 == null || y1 == null || x2 == null || y2 == null) return null;
        const isSel = s.id === selected;
        const cls = `draw-shape${isSel ? " sel" : ""}`;
        const onBody = (e: React.PointerEvent) => {
          if (!enabled || tool || s.id === "draft") return;
          e.stopPropagation();
          const c = fromPointer(e);
          if (!c) return;
          setSelected(s.id);
          setDrag({ kind: "move", id: s.id, t0: c.t, p0: c.p, orig: s });
        };
        return (
          <g key={s.id}>
            {s.type === "line" ? (
              <line x1={x1} y1={y1} x2={x2} y2={y2} className={cls} onPointerDown={onBody} />
            ) : (
              <rect
                x={Math.min(x1, x2)}
                y={Math.min(y1, y2)}
                width={Math.abs(x2 - x1)}
                height={Math.abs(y2 - y1)}
                className={`${cls} box`}
                onPointerDown={onBody}
              />
            )}
            {isSel &&
              (
                [
                  ["a", x1, y1],
                  ["b", x2, y2],
                ] as const
              ).map(([end, hx, hy]) => (
                <circle
                  key={end}
                  cx={hx}
                  cy={hy}
                  r={HANDLE_R}
                  className="draw-handle"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    setDrag({ kind: "handle", id: s.id, end });
                  }}
                />
              ))}
            {/* 박스는 반대편 두 모서리로도 크기를 조절할 수 있어야 자연스럽다 */}
            {isSel && s.type === "box" && (
              <>
                <circle
                  cx={x1}
                  cy={y2}
                  r={HANDLE_R}
                  className="draw-handle"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    setShapes((prev) =>
                      prev.map((q) =>
                        q.id === s.id ? { ...q, t1: s.t2, t2: s.t1 } : q,
                      ),
                    );
                    setDrag({ kind: "handle", id: s.id, end: "b" });
                  }}
                />
                <circle
                  cx={x2}
                  cy={y1}
                  r={HANDLE_R}
                  className="draw-handle"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    setShapes((prev) =>
                      prev.map((q) =>
                        q.id === s.id ? { ...q, p1: s.p2, p2: s.p1 } : q,
                      ),
                    );
                    setDrag({ kind: "handle", id: s.id, end: "b" });
                  }}
                />
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}
