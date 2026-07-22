"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FLAG_GROUPS, FLAG_BY_KEY, parseFlagsParam } from "@/lib/flags";
import type { FlagKey, LatestSignals, StockSignal } from "@/lib/types";

type SortKey = "name" | "close" | "change_pct" | "rsi";

// 기간 필터: 최근 N봉(거래일) 내 발생. 기본 1주
const WINDOWS = [
  { label: "오늘", bars: 0 },
  { label: "1주", bars: 5 },
  { label: "1개월", bars: 21 },
  { label: "3개월", bars: 63 },
];
const DEFAULT_WINDOW = 5;

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
  function syncUrl(next: Set<FlagKey>, bars: number) {
    const flags = [...next].join(",");
    const within = bars !== DEFAULT_WINDOW ? `&within=${bars}` : "";
    const target = flags ? `/screen?flags=${flags}${within}` : "/";
    const current =
      pathname + (searchParams.size ? `?${searchParams.toString()}` : "");
    if (target !== current) router.replace(target, { scroll: false });
  }

  const rows = useMemo(() => {
    if (!data) return [];
    const keys = [...selected];
    const filtered = data.stocks.filter((s) =>
      keys.every((k) => (s.sig?.[k] ?? Infinity) <= windowBars),
    );
    const dir = sortDesc ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sortKey === "name") return dir * a.name.localeCompare(b.name, "ko");
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return dir * (Number(av) - Number(bv));
    });
  }, [data, selected, windowBars, sortKey, sortDesc]);

  function toggle(key: FlagKey) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      syncUrl(next, windowBars);
      return next;
    });
  }

  function setWindow(bars: number) {
    setWindowBars(bars);
    syncUrl(selected, bars);
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

      <div className="result-meta">
        <span className="count">
          {data ? `${rows.length.toLocaleString()}종목` : error ? "데이터 로드 실패" : "불러오는 중…"}
        </span>
        <span className="hint">
          선택한 조건이 모두 {WINDOWS.find((w) => w.bars === windowBars)?.label}{" "}
          안에 발생한(AND) 종목입니다. 전일 기준 데이터.
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
            <th className="num" onClick={() => sortBy("change_pct")}>
              등락률{arrow("change_pct")}
            </th>
            <th className="num" onClick={() => sortBy("rsi")}>
              RSI{arrow("rsi")}
            </th>
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
