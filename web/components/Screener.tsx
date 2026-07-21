"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FLAG_GROUPS, FLAG_BY_KEY, parseFlagsParam } from "@/lib/flags";
import type { FlagKey, LatestSignals, StockSignal } from "@/lib/types";

type SortKey = "name" | "close" | "change_pct" | "rsi";

function activeBadges(s: StockSignal) {
  return (Object.keys(s.flags) as FlagKey[])
    .filter((k) => s.flags[k])
    .map((k) => FLAG_BY_KEY.get(k)!)
    .filter(Boolean);
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
  function syncUrl(next: Set<FlagKey>) {
    const flags = [...next].join(",");
    const target = flags ? `/screen?flags=${flags}` : "/";
    const current =
      pathname + (searchParams.size ? `?${searchParams.toString()}` : "");
    if (target !== current) router.replace(target, { scroll: false });
  }

  const rows = useMemo(() => {
    if (!data) return [];
    const keys = [...selected];
    const filtered = data.stocks.filter((s) =>
      keys.every((k) => s.flags[k]),
    );
    const dir = sortDesc ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sortKey === "name") return dir * a.name.localeCompare(b.name, "ko");
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return dir * (Number(av) - Number(bv));
    });
  }, [data, selected, sortKey, sortDesc]);

  function toggle(key: FlagKey) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      syncUrl(next);
      return next;
    });
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
          선택한 조건을 모두 만족(AND)하는 종목입니다. 전일 기준 데이터.
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
                {activeBadges(s).map((f) => (
                  <span
                    key={f.key}
                    className={`badge${
                      f.bullish === true ? " bull" : f.bullish === false ? " bear" : ""
                    }`}
                  >
                    {f.short}
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
