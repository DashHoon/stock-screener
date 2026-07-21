"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { LatestSignals } from "@/lib/types";

interface Item {
  code: string;
  name: string;
}

export default function StockSearch() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  // 목록은 검색창에 처음 포커스될 때 한 번만 로드
  function ensureLoaded() {
    if (items) return;
    fetch("/data/signals/latest.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: LatestSignals) =>
        setItems(d.stocks.map(({ code, name }) => ({ code, name }))),
      )
      .catch(() => setItems([]));
  }

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const query = q.trim().toLowerCase();
  const results =
    query && items
      ? items
          .filter(
            (s) =>
              s.name.toLowerCase().includes(query) || s.code.startsWith(query),
          )
          .slice(0, 8)
      : [];

  function go(code: string) {
    setOpen(false);
    setQ("");
    router.push(`/stock/${code}`);
  }

  return (
    <div className="stock-search" ref={boxRef}>
      <input
        type="search"
        placeholder="종목명·코드 검색"
        value={q}
        onFocus={() => {
          ensureLoaded();
          setOpen(true);
        }}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          setHi(0);
        }}
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing) return; // 한글 조합 중 키는 무시
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setHi((h) => Math.min(h + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHi((h) => Math.max(h - 1, 0));
          } else if (e.key === "Enter" && results[hi]) {
            go(results[hi].code);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        aria-label="종목 검색"
      />
      {open && results.length > 0 && (
        <ul className="search-results">
          {results.map((s, i) => (
            <li key={s.code}>
              <button
                type="button"
                className={i === hi ? "hi" : ""}
                onMouseEnter={() => setHi(i)}
                onClick={() => go(s.code)}
              >
                {s.name} <span className="code">{s.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
