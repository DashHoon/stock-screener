"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FLAG_GROUPS, FLAG_BY_KEY, parseFlagsParam } from "@/lib/flags";
import type { FlagKey, LatestSignals, StockSignal } from "@/lib/types";
import BacktestPanel from "@/components/BacktestPanel";
import Sparkline from "@/components/Sparkline";

type SortKey = "name" | "close" | "change_pct" | "rsi" | "cap";

// 기간 필터: 최근 N봉(거래일) 내 발생. 기본 1주
const WINDOWS = [
  { label: "오늘", bars: 0 },
  { label: "1주", bars: 5 },
  { label: "1개월", bars: 21 },
  { label: "3개월", bars: 63 },
];
const DEFAULT_WINDOW = 5;

// 시가총액 하한 필터 (억원). 0 = 전체
const CAP_TIERS = [
  { label: "전체", min: 0 },
  { label: "1천억+", min: 1000 },
  { label: "5천억+", min: 5000 },
  { label: "1조+", min: 10000 },
  { label: "10조+", min: 100000 },
];

/** 억원 → 사람이 읽는 표기 (예: 156,388억 → "15.6조") */
function fmtCap(cap: number): string {
  if (cap < 0) return "-";
  if (cap >= 10000) {
    const jo = cap / 10000;
    return `${jo >= 100 ? Math.round(jo) : jo.toFixed(1)}조`;
  }
  return `${cap.toLocaleString()}억`;
}

function badgesWithin(s: StockSignal, bars: number) {
  return (Object.keys(s.sig) as FlagKey[])
    .filter((k) => (s.sig[k] ?? Infinity) <= bars && FLAG_BY_KEY.has(k))
    .sort((a, b) => (s.sig[a] ?? 0) - (s.sig[b] ?? 0))
    .map((k) => ({ meta: FLAG_BY_KEY.get(k)!, ago: s.sig[k]! }));
}

export default function Screener({ initialFlags }: { initialFlags?: FlagKey[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [data, setData] = useState<LatestSignals | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<Set<FlagKey>>(
    () => new Set(initialFlags ?? parseFlagsParam(searchParams.get("flags"))),
  );
  const [windowBars, setWindowBars] = useState<number>(() => {
    const p = searchParams.get("within");
    if (p == null) return DEFAULT_WINDOW;
    const w = Number(p);
    return WINDOWS.some((x) => x.bars === w) ? w : DEFAULT_WINDOW;
  });
  const [minCap, setMinCap] = useState<number>(() => {
    const c = Number(searchParams.get("cap"));
    return CAP_TIERS.some((t) => t.min === c) ? c : 0;
  });
  const [sortKey, setSortKey] = useState<SortKey>("change_pct");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    fetch("/data/signals/latest.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError(true));
  }, []);

  // 사용자가 필터를 바꿨을 때만 URL 동기화 (프리셋 페이지 /screen/[slug]의
  // 예쁜 URL은 사용자가 손대기 전까지 유지)
  function syncUrl(next: Set<FlagKey>, bars: number, cap: number) {
    const flags = [...next].join(",");
    const within = bars !== DEFAULT_WINDOW ? `&within=${bars}` : "";
    const capp = cap > 0 ? `&cap=${cap}` : "";
    const target = flags ? `/screen?flags=${flags}${within}${capp}` : "/";
    const current =
      pathname + (searchParams.size ? `?${searchParams.toString()}` : "");
    if (target !== current) router.replace(target, { scroll: false });
  }

  // 지표 조건이 하나도 없으면 '초기 화면' — 시총 상위 10만 보여준다
  const noFilter = selected.size === 0;

  const rows = useMemo(() => {
    if (!data) return [];
    if (noFilter) {
      return [...data.stocks]
        .filter((s) => (s.cap ?? -1) >= minCap)
        .sort((a, b) => (b.cap ?? -1) - (a.cap ?? -1))
        .slice(0, 10);
    }
    const keys = [...selected];
    const filtered = data.stocks.filter(
      (s) =>
        (minCap === 0 || (s.cap ?? -1) >= minCap) &&
        keys.every((k) => (s.sig?.[k] ?? Infinity) <= windowBars),
    );
    const dir = sortDesc ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sortKey === "name") return dir * a.name.localeCompare(b.name, "ko");
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return dir * (Number(av) - Number(bv));
    });
  }, [data, noFilter, selected, windowBars, minCap, sortKey, sortDesc]);

  function toggle(key: FlagKey) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      syncUrl(next, windowBars, minCap);
      return next;
    });
  }

  function setWindow(bars: number) {
    setWindowBars(bars);
    syncUrl(selected, bars, minCap);
  }

  function setCap(cap: number) {
    setMinCap(cap);
    syncUrl(selected, windowBars, cap);
  }

  function sortBy(key: SortKey) {
    if (sortKey === key) setSortDesc((d) => !d);
    else {
      setSortKey(key);
      setSortDesc(key !== "name");
    }
  }

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDesc ? " ▾" : " ▴") : "";

  return (
    <div>
      {noFilter && data?.indices && data.indices.length > 0 && (
        <div className="index-cards">
          {data.indices.map((ix) => {
            const up = (ix.change_pct ?? 0) > 0;
            const down = (ix.change_pct ?? 0) < 0;
            return (
              <div className="index-card" key={ix.name}>
                <div className="index-info">
                  <span className="index-name">{ix.name}</span>
                  <span className="index-close">{ix.close.toLocaleString()}</span>
                  <span className={up ? "pct-up" : down ? "pct-down" : ""}>
                    {ix.change_pct == null
                      ? ""
                      : `${ix.change_pct > 0 ? "+" : ""}${ix.change_pct.toFixed(2)}%`}
                  </span>
                </div>
                <Sparkline data={ix.spark} width={96} height={32} />
              </div>
            );
          })}
        </div>
      )}
      <div className="filter-panel">
        <div className="filter-group">
          <div className="filter-group-name">발생 시점 (선택한 모든 조건이 이 기간 안에 발생)</div>
          <div className="filter-options">
            {WINDOWS.map((w) => (
              <button
                key={w.bars}
                type="button"
                className={`filter-chip window-chip${windowBars === w.bars ? " on" : ""}`}
                onClick={() => setWindow(w.bars)}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <div className="filter-group-name">시가총액 (하한)</div>
          <div className="filter-options">
            {CAP_TIERS.map((t) => (
              <button
                key={t.min}
                type="button"
                className={`filter-chip window-chip${minCap === t.min ? " on" : ""}`}
                onClick={() => setCap(t.min)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        {FLAG_GROUPS.map((g) => (
          <div className="filter-group" key={g.name}>
            <div className="filter-group-name">{g.name}</div>
            <div className="filter-options">
              {g.flags.map((f) => (
                <label
                  key={f.key}
                  className={`filter-chip${selected.has(f.key) ? " on" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(f.key)}
                    onChange={() => toggle(f.key)}
                  />
                  {f.label}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <BacktestPanel
        selected={[...selected]}
        windowBars={windowBars}
        minCap={minCap}
      />

      <div className="result-meta">
        <span className="count">
          {!data
            ? error
              ? "데이터 로드 실패"
              : "불러오는 중…"
            : noFilter
              ? "시가총액 상위 10"
              : `${rows.length.toLocaleString()}종목`}
        </span>
        <span className="hint">
          {noFilter
            ? "위에서 지표를 선택하면 조건에 맞는 종목이 표시됩니다. 전일 기준 데이터."
            : `선택한 조건이 모두 ${WINDOWS.find((w) => w.bars === windowBars)?.label} 안에 발생한(AND) 종목입니다. 전일 기준 데이터.`}
        </span>
      </div>

      <div className="table-wrap">
      <table className="stock-table">
        <thead>
          <tr>
            <th onClick={() => sortBy("name")}>종목{arrow("name")}</th>
            <th className="num" onClick={() => sortBy("close")}>
              종가{arrow("close")}
            </th>
            <th className="num" onClick={() => sortBy("cap")}>
              시총{arrow("cap")}
            </th>
            <th className="num" onClick={() => sortBy("change_pct")}>
              등락률{arrow("change_pct")}
            </th>
            <th className="num" onClick={() => sortBy("rsi")}>
              RSI{arrow("rsi")}
            </th>
            <th className="spark-col">20일</th>
            <th>시그널</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.code}>
              <td className="name">
                <Link href={`/stock/${s.code}`}>{s.name}</Link>
                <span className="code">{s.code}</span>
              </td>
              <td className="num">{s.close.toLocaleString()}</td>
              <td className="num cap">{fmtCap(s.cap)}</td>
              <td
                className={`num ${
                  (s.change_pct ?? 0) > 0
                    ? "pct-up"
                    : (s.change_pct ?? 0) < 0
                      ? "pct-down"
                      : ""
                }`}
              >
                {s.change_pct == null
                  ? "-"
                  : `${s.change_pct > 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`}
              </td>
              <td className="num">{s.rsi ?? "-"}</td>
              <td className="spark-col"><Sparkline data={s.m} /></td>
              <td>
                {badgesWithin(s, windowBars).map(({ meta, ago }) => (
                  <span
                    key={meta.key}
                    className={`badge${
                      meta.bullish === true ? " bull" : meta.bullish === false ? " bear" : ""
                    }`}
                  >
                    {meta.short}
                    {ago > 0 && <em className="badge-ago">{ago}일</em>}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
