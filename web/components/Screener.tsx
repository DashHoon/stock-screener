"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FLAG_GROUPS, FLAG_BY_KEY, parseFlagsParam } from "@/lib/flags";
import type { FlagMeta } from "@/lib/flags";
import type { FlagKey, LatestSignals, StockSignal } from "@/lib/types";
import BacktestPanel from "@/components/BacktestPanel";
import FlagInfoModal from "@/components/FlagInfoModal";
import Sparkline from "@/components/Sparkline";
import {
  rid,
  removeScreen,
  saveScreen,
  useScreens,
  type SavedScreen,
} from "@/lib/storage";

type SortKey = "name" | "close" | "change_pct" | "rsi" | "cap";

// 시장 구분 필터
const MARKETS = [
  { label: "전체", val: "" },
  { label: "코스피", val: "KOSPI" },
  { label: "코스닥", val: "KOSDAQ" },
];

// 상승/하락 방향 보기 필터 (체크박스 노출을 방향별로 좁힌다)
type Dir = "all" | "up" | "down";
const DIRECTIONS: { label: string; val: Dir }[] = [
  { label: "전체", val: "all" },
  { label: "📈 상승", val: "up" },
  { label: "📉 하락", val: "down" },
];
function inDir(bullish: boolean | null, dir: Dir): boolean {
  if (dir === "all") return true;
  if (dir === "up") return bullish === true;
  return bullish === false;
}

// 기간 필터: 최근 N봉(거래일) 내 발생. 기본 1주
const WINDOWS = [
  { label: "당일", bars: 0 },
  { label: "1주", bars: 5 },
  { label: "1개월", bars: 21 },
  { label: "3개월", bars: 63 },
];
const DEFAULT_WINDOW = 5;

// "2026-07-22" → "7/22" (기준일 표시용). 지연 시세라 '당일'은 데이터 기준일을 뜻한다.
function shortDate(date?: string): string {
  const m = date?.match(/^\d{4}-(\d{2})-(\d{2})$/);
  return m ? `${+m[1]}/${+m[2]}` : "";
}

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
  const [market, setMarketState] = useState<string>(() => {
    const m = searchParams.get("mkt") ?? "";
    return MARKETS.some((x) => x.val === m) ? m : "";
  });
  const [dir, setDir] = useState<Dir>("all"); // 방향 보기 필터 (URL 비반영)
  const [infoFlag, setInfoFlag] = useState<FlagMeta | null>(null); // 지표설명 팝오버
  const savedScreens = useScreens(); // 저장한 스크리닝 조건 (localStorage)
  const [sortKey, setSortKey] = useState<SortKey>("change_pct");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    fetch("/data/signals/latest.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError(true));
  }, []);

  // 필터 상태를 URL에 동기화. 지표를 다 해제해도 기간·시총 파라미터가 있으면
  // /screen에 머문다(홈 '/'으로 보내면 컴포넌트가 재마운트되며 기간·시총이
  // 초기값으로 리셋되는 문제 방지). 전부 기본값일 때만 홈으로.
  function syncUrl(next: Set<FlagKey>, bars: number, cap: number, mkt: string) {
    const flags = [...next].join(",");
    const parts: string[] = [];
    if (flags) parts.push(`flags=${flags}`);
    if (bars !== DEFAULT_WINDOW) parts.push(`within=${bars}`);
    if (cap > 0) parts.push(`cap=${cap}`);
    if (mkt) parts.push(`mkt=${mkt}`);
    const target = parts.length ? `/screen?${parts.join("&")}` : "/";
    const current =
      pathname + (searchParams.size ? `?${searchParams.toString()}` : "");
    if (target !== current) router.replace(target, { scroll: false });
  }

  // 지표 조건이 하나도 없으면 '초기 화면' — 시총 상위 10만 보여준다
  const noFilter = selected.size === 0;

  const rows = useMemo(() => {
    if (!data) return [];
    const mktOk = (s: StockSignal) => !market || s.mkt === market;
    if (noFilter) {
      return [...data.stocks]
        .filter((s) => mktOk(s) && (s.cap ?? -1) >= minCap)
        .sort((a, b) => (b.cap ?? -1) - (a.cap ?? -1))
        .slice(0, 10);
    }
    const keys = [...selected];
    const filtered = data.stocks.filter(
      (s) =>
        mktOk(s) &&
        (minCap === 0 || (s.cap ?? -1) >= minCap) &&
        keys.every((k) => (s.sig?.[k] ?? Infinity) <= windowBars),
    );
    const sdir = sortDesc ? -1 : 1;
    return filtered.sort((a, b) => {
      if (sortKey === "name") return sdir * a.name.localeCompare(b.name, "ko");
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return sdir * (Number(av) - Number(bv));
    });
  }, [data, noFilter, selected, windowBars, minCap, market, sortKey, sortDesc]);

  function toggle(key: FlagKey) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      syncUrl(next, windowBars, minCap, market);
      return next;
    });
  }

  function setWindow(bars: number) {
    setWindowBars(bars);
    syncUrl(selected, bars, minCap, market);
  }

  function setCap(cap: number) {
    setMinCap(cap);
    syncUrl(selected, windowBars, cap, market);
  }

  function setMarket(mkt: string) {
    setMarketState(mkt);
    syncUrl(selected, windowBars, minCap, mkt);
  }

  // 현재 필터 조합을 이름 붙여 저장 (localStorage)
  function saveCurrentScreen() {
    if (selected.size === 0) return;
    const def = [...selected].map((k) => FLAG_BY_KEY.get(k)?.short ?? k).join("+");
    const name = window.prompt("저장할 조건 이름", def)?.trim();
    if (!name) return;
    saveScreen({
      id: rid(),
      name,
      flags: [...selected],
      within: windowBars,
      cap: minCap,
      mkt: market,
    });
  }

  // 저장한 조건을 현재 화면에 적용 (재마운트 없이 상태·URL 동기화)
  function applyScreen(s: SavedScreen) {
    const next = new Set(s.flags.filter((k) => FLAG_BY_KEY.has(k as FlagKey)) as FlagKey[]);
    setSelected(next);
    setWindowBars(s.within);
    setMinCap(s.cap);
    setMarketState(s.mkt ?? "");
    syncUrl(next, s.within, s.cap, s.mkt ?? "");
    window.scrollTo({ top: 0, behavior: "smooth" });
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
              <Link className="index-card" key={ix.name} href={`/stock/${ix.code}`}>
                <div className="index-info">
                  <span className="index-name">{ix.name} ›</span>
                  <span className="index-close">{ix.close.toLocaleString()}</span>
                  <span className={up ? "pct-up" : down ? "pct-down" : ""}>
                    {ix.change_pct == null
                      ? ""
                      : `${ix.change_pct > 0 ? "+" : ""}${ix.change_pct.toFixed(2)}%`}
                  </span>
                </div>
                <Sparkline data={ix.spark} width={96} height={32} />
              </Link>
            );
          })}
        </div>
      )}
      {savedScreens.length > 0 && (
        <div className="saved-screens">
          <span className="saved-label">저장한 조건:</span>
          {savedScreens.map((s) => (
            <span key={s.id} className="saved-chip">
              <button type="button" className="saved-apply" onClick={() => applyScreen(s)}>
                {s.name}
              </button>
              <button
                type="button"
                className="saved-del"
                aria-label={`${s.name} 삭제`}
                onClick={() => removeScreen(s.id)}
              >
                ×
              </button>
            </span>
          ))}
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
                title={w.bars === 0 ? "데이터 기준일(전일) 당일" : undefined}
              >
                {w.bars === 0 && data?.date ? shortDate(data.date) : w.label}
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
        <div className="filter-group">
          <div className="filter-group-name">시장</div>
          <div className="filter-options">
            {MARKETS.map((m) => (
              <button
                key={m.val}
                type="button"
                className={`filter-chip window-chip${market === m.val ? " on" : ""}`}
                onClick={() => setMarket(m.val)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <div className="filter-group-name">시그널 방향 (상승/하락 스크리닝)</div>
          <div className="filter-options">
            {DIRECTIONS.map((d) => (
              <button
                key={d.val}
                type="button"
                className={`filter-chip window-chip${dir === d.val ? " on" : ""}`}
                onClick={() => setDir(d.val)}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
        {FLAG_GROUPS.map((g) => {
          const flags = g.flags.filter((f) => inDir(f.bullish, dir));
          if (flags.length === 0) return null; // 방향 필터로 비면 그룹 숨김
          return (
            <div className="filter-group" key={g.name}>
              <div className="filter-group-name">{g.name}</div>
              <div className="filter-options">
                {flags.map((f) => (
                  <div
                    key={f.key}
                    className={`filter-chip${selected.has(f.key) ? " on" : ""}${
                      f.bullish === true ? " dir-up" : f.bullish === false ? " dir-down" : ""
                    }`}
                  >
                    <label className="chip-main">
                      <input
                        type="checkbox"
                        checked={selected.has(f.key)}
                        onChange={() => toggle(f.key)}
                      />
                      {f.label}
                    </label>
                    <button
                      type="button"
                      className="chip-info"
                      aria-label={`${f.label} 설명`}
                      onClick={() => setInfoFlag(f)}
                    >
                      ⓘ
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {infoFlag && <FlagInfoModal flag={infoFlag} onClose={() => setInfoFlag(null)} />}

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
        {!noFilter && (
          <button type="button" className="save-screen-btn" onClick={saveCurrentScreen}>
            ＋ 조건 저장
          </button>
        )}
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
                {s.mkt && (
                  <span className={`mkt-tag ${s.mkt === "KOSPI" ? "kospi" : "kosdaq"}`}>
                    {s.mkt === "KOSPI" ? "코스피" : "코스닥"}
                  </span>
                )}
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
