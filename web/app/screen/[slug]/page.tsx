import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import AdSlot from "@/components/AdSlot";
import Screener from "@/components/Screener";
import { loadLatest } from "@/lib/data";
import { PRESETS, PRESET_BY_SLUG } from "@/lib/presets";

export const dynamicParams = false;

export function generateStaticParams() {
  return PRESETS.map(({ slug }) => ({ slug }));
}

/** 검색 결과에 뜰 제목·설명.
 *
 *  2026-08-08 개편. 이 페이지들은 노출은 나오는데 클릭이 0이었다
 *  (macd-golden-cross 노출 32·클릭 0, oversold-bb-lower 17·0).
 *  제목이 "MACD 골든크로스 종목 — 오늘의 스크리닝"처럼 지표 이름만 있어서
 *  검색 결과에서 다른 설명글과 구분이 안 됐다. 우리가 가진 건 '설명'이 아니라
 *  '오늘 그 조건에 해당하는 종목 목록'인데 그게 제목에 드러나지 않았다.
 *
 *  종목 수와 기준일을 빌드 시점에 넣는다. 배치가 매일 사이트를 다시 만들므로
 *  그날 값이 그대로 반영된다. 스크리너 기본값(최근 5봉 안 발생)과 같은 기준으로
 *  세어야 페이지를 열었을 때 숫자가 어긋나지 않는다. */
const DEFAULT_WINDOW_BARS = 5;

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const preset = PRESET_BY_SLUG.get(params.slug);
  if (!preset) return {};

  let count: number | null = null;
  let date = "";
  try {
    const latest = await loadLatest();
    date = latest.date;
    count = latest.stocks.filter((s) =>
      preset.flags.every((k) => (s.sig?.[k] ?? Infinity) <= DEFAULT_WINDOW_BARS),
    ).length;
  } catch {
    /* 데이터가 없으면 숫자 없이 나간다 */
  }

  const md = date ? `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}` : "";

  // 제목은 짧게. 한국어 검색결과는 30자 근처에서 잘리므로 사이트명 접미사
  // (`| 주식 시그널 스크리너`)를 붙이지 않는다 — 종목 수가 잘리면 넣은 의미가 없다.
  const title =
    count !== null
      ? `${preset.title} 종목 ${count.toLocaleString("ko-KR")}개 · ${md} 기준`
      : `${preset.title} 종목 — 오늘의 스크리닝`;

  // 설명은 본문 첫 문장까지만 빌려 쓴다. 본문을 통째로 넣으면 190자가 되어
  // 검색결과에서 뒷부분이 잘린다.
  const lead = preset.description.split(". ")[0] + ".";
  const description =
    count !== null
      ? `${md} 기준 ${count.toLocaleString("ko-KR")}개. ${lead} 코스피·코스닥 전 종목을 매일 자동 계산해 종목명·종가·등락률과 함께 보여줍니다.`
      : preset.description;

  return { title: { absolute: title }, description };
}

export default function PresetPage({ params }: { params: { slug: string } }) {
  const preset = PRESET_BY_SLUG.get(params.slug);
  if (!preset) notFound();

  return (
    <div>
      <div className="prose" style={{ marginTop: 24 }}>
        <h1>{preset.title}</h1>
        <p>{preset.description}</p>
      </div>

      <Suspense>
        <Screener initialFlags={preset.flags} />
      </Suspense>

      <nav className="preset-links">
        <span>다른 조합:</span>
        {PRESETS.filter((p) => p.slug !== preset.slug).map((p) => (
          <Link key={p.slug} href={`/screen/${p.slug}`}>
            {p.title}
          </Link>
        ))}
      </nav>

      <AdSlot id={`preset-${preset.slug}`} />
    </div>
  );
}
