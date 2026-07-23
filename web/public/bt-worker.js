/* 사용자 정의 백테스트 워커 — 서버 engine.py 로직의 클라이언트 이식.
 *
 * 메시지:
 *   {type:'load', url}          → dataset.json을 워커가 직접 fetch해 보관
 *   {type:'run', sigIdxs, windowBars, minCap}
 *      → 선택 시그널이 모두 최근 windowBars 봉 내 발생한 날 진입,
 *        사후 h거래일 수익률 집계(승률/평균/중앙값), 같은 종목 60봉 중복 억제,
 *        시장 기준선 동시 계산
 * 응답: {type:'loaded', stocks, date} | {type:'result', ...} | {type:'error', message}
 */

const MIN_GAP = 60;
let DATA = null;

function median(arr) {
  if (!arr.length) return 0;
  const s = Float64Array.from(arr).sort();
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
function summarize(rets) {
  if (!rets.length) return null;
  let wins = 0, sum = 0;
  for (const r of rets) { if (r > 0) wins++; sum += r; }
  return {
    n: rets.length,
    win: +(wins / rets.length * 100).toFixed(1),
    mean: +(sum / rets.length).toFixed(2),
    median: +median(rets).toFixed(2),
  };
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  try {
    if (msg.type === "load") {
      if (!DATA) {
        const r = await fetch(msg.url);
        if (!r.ok) throw new Error("dataset " + r.status);
        DATA = await r.json();
      }
      self.postMessage({ type: "loaded", stocks: DATA.stocks.length, date: DATA.date, sigKeys: DATA.sigKeys });
      return;
    }
    if (msg.type === "run") {
      if (!DATA) throw new Error("dataset not loaded");
      const { sigIdxs, windowBars, minCap } = msg;
      const H = DATA.horizons, maxH = Math.max(...H), minH = Math.min(...H);
      const samples = {}, baseline = {};
      for (const h of H) { samples[h] = []; baseline[h] = []; }
      let universe = 0, entries = 0, stocksHit = 0;

      for (const st of DATA.stocks) {
        if (minCap > 0 && (st.cap ?? -1) < minCap) continue;
        const c = st.c, n = c.length;
        if (n < maxH + 5) continue;
        universe++;

        for (let i = 0; i + maxH < n; i += 10) {
          if (c[i] > 0) for (const h of H) baseline[h].push((c[i + h] / c[i] - 1) * 100);
        }

        const occ = sigIdxs.map((si) => st.e[String(si)]);
        if (occ.some((o) => !o)) continue; // 이 종목에 없는 시그널 → 제외
        let hit = false, lastEntry = -1e9;
        const ptr = occ.map(() => 0);
        // 진입은 최소 보유기간까지 가능한 날까지 (각 h는 i+h<n일 때만 집계 —
        // 공개 /stats 서버 엔진과 동일한 방법론)
        for (let i = 0; i < n - minH; i++) {
          let all = true;
          for (let k = 0; k < occ.length; k++) {
            const arr = occ[k];
            while (ptr[k] < arr.length && arr[ptr[k]] < i - windowBars) ptr[k]++;
            let found = false;
            for (let p = ptr[k]; p < arr.length && arr[p] <= i; p++) {
              if (arr[p] >= i - windowBars) { found = true; break; }
            }
            if (!found) { all = false; break; }
          }
          if (!all) continue;
          if (i - lastEntry < MIN_GAP) continue;
          lastEntry = i; entries++; hit = true;
          for (const h of H) if (i + h < n && c[i] > 0) samples[h].push((c[i + h] / c[i] - 1) * 100);
        }
        if (hit) stocksHit++;
      }

      const results = {}, base = {};
      for (const h of H) { results[h] = summarize(samples[h]); base[h] = summarize(baseline[h]); }
      self.postMessage({
        type: "result", horizons: H, results, baseline: base,
        entries, universe, stocksHit, date: DATA.date,
      });
    }
  } catch (e) {
    self.postMessage({ type: "error", message: String(e && e.message || e) });
  }
};
