"use client";

import { useEffect, useState } from "react";

/** 종목 관련 뉴스. 서버리스 함수(/api/news)가 구글 뉴스 RSS를 받아 넘겨준다.
 *  본문은 싣지 않고 제목·출처·시각만 보여준 뒤 원문으로 보낸다. */

interface NewsItem {
  title: string;
  source: string;
  url: string;
  date: string;
}

function ago(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "";
  const h = Math.floor((Date.now() - d) / 3600000);
  if (h < 1) return "방금";
  if (h < 24) return `${h}시간 전`;
  const days = Math.floor(h / 24);
  return days < 7 ? `${days}일 전` : new Date(d).toLocaleDateString("ko-KR");
}

export default function StockNews({ name }: { name: string }) {
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setItems(null);
    setFailed(false);
    fetch(`/api/news?name=${encodeURIComponent(name)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => alive && setItems(d.items ?? []))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [name]);

  // 종목명이 '대상'·'동원'처럼 흔한 낱말이면 걸러도 잡음이 남는다. 직접 검색으로 보낸다.
  const searchUrl = `https://search.naver.com/search.naver?where=news&query=${encodeURIComponent(name + " 주가")}`;

  return (
    <section className="news-box">
      <div className="news-head">
        <h2>{name} 뉴스</h2>
        <a href={searchUrl} target="_blank" rel="noopener noreferrer">
          직접 검색 ↗
        </a>
      </div>

      {items === null && !failed && <p className="notice">불러오는 중…</p>}
      {failed && <p className="notice">뉴스를 불러오지 못했습니다.</p>}
      {items && items.length === 0 && (
        <p className="notice">관련 뉴스를 찾지 못했습니다.</p>
      )}

      {items && items.length > 0 && (
        <ul className="news-list">
          {items.map((n) => (
            <li key={n.url}>
              <a href={n.url} target="_blank" rel="noopener noreferrer">
                {n.title}
              </a>
              <span className="news-meta">
                {n.source}
                {n.date && ` · ${ago(n.date)}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="news-foot">
        검색 결과를 그대로 보여줍니다. 기사 내용은 해당 언론사의 것이며 본 서비스의
        견해가 아닙니다. 종목명이 일반 명사인 경우 관련 없는 기사가 섞일 수 있습니다.
      </p>
    </section>
  );
}
