import { promises as fs } from "fs";
import path from "path";
import type { Metadata } from "next";
import AdSlot from "@/components/AdSlot";

export const metadata: Metadata = {
  title: "시그널 백테스트 — 지난 10년 성과 통계",
  description:
    "RSI 다이버전스, MACD 골든크로스 등 기술적 시그널 전략들이 지난 10년간 국내주식 전 종목에서 보인 승률과 평균 수익률 통계.",
};

interface HorizonStat {
  n: number;
  win: number;
  mean: number;
  median: number;
}

interface BacktestData {
  generated: string;
  period: { from: string; to: string };
  universe: number;
  horizons: number[];
  baseline: Record<string, HorizonStat>;
  strategies: {
    id: string;
    name: string;
    desc: string;
    stocks: number;
    results: Record<string, HorizonStat | null>;
  }[];
}

async function loadBacktest(): Promise<BacktestData | null> {
  try {
    const raw = await fs.readFile(
      path.join(process.cwd(), "public", "data", "stats", "backtest.json"),
      "utf-8",
    );
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function Pct({ v, signed = true }: { v: number; signed?: boolean }) {
  const cls = v > 0 ? "pct-up" : v < 0 ? "pct-down" : "";
  return (
    <span className={cls}>
      {signed && v > 0 ? "+" : ""}
      {v.toFixed(v % 1 === 0 && !signed ? 0 : 2)}%
    </span>
  );
}

export default async function StatsPage() {
  const data = await loadBacktest();
  if (!data) {
    return (
      <div className="prose">
        <h1>시그널 백테스트</h1>
        <p>통계 데이터가 아직 준비되지 않았습니다. 다음 배치 후 다시 확인해 주세요.</p>
      </div>
    );
  }

  return (
    <div className="prose">
      <h1>시그널 백테스트 — 지난 10년 성과 통계</h1>
      <p>
        {data.period.from} ~ {data.period.to} 기간, 국내주식{" "}
        {data.universe.toLocaleString()}종목 일봉 데이터로 각 전략의 신호
        발생일(종가 진입) 이후 수익률을 집계했습니다. 같은 종목에서 60거래일
        내 중복 신호는 표본에서 제외해 부풀림을 방지했습니다.
      </p>

      <AdSlot id="stats-top" variant="banner" />

      <div className="stats-baseline">
        <strong>시장 기준선</strong> (같은 기간 임의 시점 매수 시):{" "}
        {data.horizons.map((h) => {
          const b = data.baseline[String(h)];
          return b ? (
            <span key={h} className="baseline-item">
              {h}일 후 평균 <Pct v={b.mean} /> · 승률 {b.win}%
            </span>
          ) : null;
        })}
      </div>

      {data.strategies.map((s) => (
        <section key={s.id} className="strategy-card">
          <h2>{s.name}</h2>
          <p className="strategy-desc">
            {s.desc} <span className="muted">— 신호 발생 {s.stocks.toLocaleString()}종목</span>
          </p>
          <div className="table-wrap">
            <table className="stock-table stats-table">
              <thead>
                <tr>
                  <th>보유기간</th>
                  <th className="num">표본수</th>
                  <th className="num">승률</th>
                  <th className="num">평균 수익률</th>
                  <th className="num">중앙값</th>
                  <th className="num">시장 대비</th>
                </tr>
              </thead>
              <tbody>
                {data.horizons.map((h) => {
                  const r = s.results[String(h)];
                  const b = data.baseline[String(h)];
                  if (!r) return null;
                  return (
                    <tr key={h}>
                      <td>{h}거래일</td>
                      <td className="num">{r.n.toLocaleString()}</td>
                      <td className="num">{r.win}%</td>
                      <td className="num"><Pct v={r.mean} /></td>
                      <td className="num"><Pct v={r.median} /></td>
                      <td className="num">
                        {b ? <Pct v={+(r.mean - b.mean).toFixed(2)} /> : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <div className="stats-disclaimer">
        <h2>읽기 전 유의사항</h2>
        <ul>
          <li>
            <strong>과거 통계이며 미래 수익을 보장하지 않습니다.</strong> 본
            자료는 투자 조언이 아닌 통계 정보 제공이며, 투자 판단과 책임은
            투자자 본인에게 있습니다.
          </li>
          <li>
            현재 상장 종목만 포함되어 <strong>생존 편향</strong>이 있습니다.
            상장폐지 종목의 실패 사례가 빠져 실제보다 낙관적일 수 있습니다.
          </li>
          <li>수수료·세금·슬리피지를 반영하지 않은 종가 기준 계산입니다.</li>
          <li>
            [대형주] 표기는 시가총액 상위 300 종목만 대상으로 한 전략입니다.
            품질 필터(거래량·추세) 실험 결과, 같은 필터가 전 종목에서는 무효한
            반면 대형주에서는 유효했습니다 — 유니버스에 따라 결과가 크게 달라질
            수 있음을 보여주는 사례입니다.
          </li>
          <li>통계는 주 1회 갱신됩니다. (생성일: {data.generated})</li>
        </ul>
      </div>

      <AdSlot id="stats-bottom" variant="banner" />
    </div>
  );
}
