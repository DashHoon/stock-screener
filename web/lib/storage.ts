"use client";

// 로그인·DB 없이 브라우저(localStorage)에만 저장하는 사용자 데이터.
// 관심종목 / 최근 본 종목 / 저장한 스크리닝 조건. 기기·브라우저별로 보관된다.
import { useEffect, useState } from "react";

export interface StockRef {
  code: string;
  name: string;
}

export interface SavedScreen {
  id: string;
  name: string;
  flags: string[];
  within: number;
  cap: number;
  mkt: string;
}

const isBrowser = typeof window !== "undefined";

function read<T>(key: string, fb: T): T {
  if (!isBrowser) return fb;
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fb;
  } catch {
    return fb;
  }
}

function write<T>(key: string, val: T): void {
  if (!isBrowser) return;
  localStorage.setItem(key, JSON.stringify(val));
  // 같은 탭의 다른 컴포넌트에 변경 통지 (native 'storage'는 다른 탭에만 발생)
  window.dispatchEvent(new CustomEvent("ls-change", { detail: key }));
}

export const rid = (): string =>
  Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

/** localStorage 값을 반응형으로 읽는다 (같은 탭 변경 + 다른 탭 변경 모두 반영). */
export function useLocal<T>(key: string, fb: T): T {
  const [val, setVal] = useState<T>(fb);
  useEffect(() => {
    const sync = () => setVal(read(key, fb));
    sync();
    const onCustom = (e: Event) => {
      if ((e as CustomEvent).detail === key) sync();
    };
    window.addEventListener("ls-change", onCustom);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("ls-change", onCustom);
      window.removeEventListener("storage", sync);
    };
    // fb는 초기값 용도로만 쓰고 key만 구독 대상으로 삼는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return val;
}

// ── 관심종목 ─────────────────────────────
const WATCH = "watchlist";
export const getWatchlist = () => read<StockRef[]>(WATCH, []);
export const useWatchlist = () => useLocal<StockRef[]>(WATCH, []);
export function toggleWatch(ref: StockRef): boolean {
  const list = getWatchlist();
  const i = list.findIndex((s) => s.code === ref.code);
  if (i >= 0) {
    list.splice(i, 1);
    write(WATCH, list);
    return false;
  }
  write(WATCH, [{ code: ref.code, name: ref.name }, ...list]);
  return true;
}

// ── 최근 본 종목 ──────────────────────────
const RECENT = "recentStocks";
const RECENT_CAP = 12;
export const useRecent = () => useLocal<StockRef[]>(RECENT, []);
export function pushRecent(ref: StockRef): void {
  const list = read<StockRef[]>(RECENT, []).filter((s) => s.code !== ref.code);
  write(RECENT, [{ code: ref.code, name: ref.name }, ...list].slice(0, RECENT_CAP));
}

// ── 저장한 스크리닝 조건 ────────────────────
const SCREENS = "savedScreens";
const SCREENS_CAP = 30;
export const useScreens = () => useLocal<SavedScreen[]>(SCREENS, []);
export function saveScreen(s: SavedScreen): void {
  const list = read<SavedScreen[]>(SCREENS, []).filter((x) => x.id !== s.id);
  write(SCREENS, [s, ...list].slice(0, SCREENS_CAP));
}
export function removeScreen(id: string): void {
  write(
    SCREENS,
    read<SavedScreen[]>(SCREENS, []).filter((x) => x.id !== id),
  );
}
