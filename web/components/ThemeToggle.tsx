"use client";

import { useEffect, useState } from "react";

// 다크/화이트 토글. 선택값은 localStorage에 남고, 첫 페인트 전 적용은
// layout의 인라인 스크립트가 담당한다(테마가 번쩍이는 현상 방지).
export type Theme = "light" | "dark";

export function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === "dark") root.dataset.theme = "dark";
  else delete root.dataset.theme;
  localStorage.setItem("theme", t);
  // 차트는 CSS 변수를 읽어 캔버스에 그리므로 다시 그리라고 알린다
  window.dispatchEvent(new CustomEvent("themechange", { detail: t }));
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={theme === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환"}
      title={theme === "dark" ? "라이트 모드" : "다크 모드"}
    >
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
