/** 스퀘어리파이드 트리맵 레이아웃.
 *
 *  d3-hierarchy를 넣지 않고 직접 구현한다 (의존성 4개 유지). 알고리즘은
 *  Bruls et al.(2000) squarified treemap — 타일을 한 줄씩 채우되, 그 줄에 하나 더
 *  넣었을 때 가로세로비가 나빠지면 줄을 끊는 방식. 값 순서대로 쌓기만 하는
 *  slice-and-dice보다 정사각형에 가까워 라벨이 읽힌다.
 */

export interface TreeItem {
  key: string;
  value: number; // 넓이 기준 (시가총액)
}

export interface Tile<T> {
  item: T;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 한 줄에 담긴 타일들의 최악 가로세로비 (1에 가까울수록 정사각형) */
function worstRatio(row: number[], side: number, scale: number): number {
  const sum = row.reduce((a, b) => a + b, 0) * scale;
  if (sum <= 0 || side <= 0) return Infinity;
  const max = Math.max(...row) * scale;
  const min = Math.min(...row) * scale;
  const s2 = side * side;
  const sum2 = sum * sum;
  return Math.max((s2 * max) / sum2, sum2 / (s2 * min));
}

export function squarify<T extends TreeItem>(
  items: T[],
  width: number,
  height: number,
): Tile<T>[] {
  const valid = items.filter((i) => i.value > 0).sort((a, b) => b.value - a.value);
  if (!valid.length || width <= 0 || height <= 0) return [];

  const total = valid.reduce((a, b) => a + b.value, 0);
  const scale = (width * height) / total; // 값 → 픽셀 넓이
  const out: Tile<T>[] = [];
  let rect: Rect = { x: 0, y: 0, w: width, h: height };
  let i = 0;

  while (i < valid.length) {
    const side = Math.min(rect.w, rect.h);
    const row: number[] = [];
    const rowItems: T[] = [];

    // 가로세로비가 나빠지기 직전까지 한 줄에 채운다
    while (i < valid.length) {
      const next = [...row, valid[i].value];
      if (row.length && worstRatio(next, side, scale) > worstRatio(row, side, scale)) break;
      row.push(valid[i].value);
      rowItems.push(valid[i]);
      i++;
    }

    // 줄을 배치하고 남은 영역을 다음 루프로 넘긴다
    const rowArea = row.reduce((a, b) => a + b, 0) * scale;
    const horizontal = rect.w >= rect.h;
    const thickness = rowArea / side; // 줄의 두께

    let pos = horizontal ? rect.y : rect.x;
    for (let k = 0; k < rowItems.length; k++) {
      const len = (row[k] * scale) / thickness;
      out.push(
        horizontal
          ? { item: rowItems[k], x: rect.x, y: pos, w: thickness, h: len }
          : { item: rowItems[k], x: pos, y: rect.y, w: len, h: thickness },
      );
      pos += len;
    }

    rect = horizontal
      ? { x: rect.x + thickness, y: rect.y, w: rect.w - thickness, h: rect.h }
      : { x: rect.x, y: rect.y + thickness, w: rect.w, h: rect.h - thickness };

    if (rect.w < 0.5 || rect.h < 0.5) break;
  }
  return out;
}

/** 등락률 → 배경색. 국내 관례대로 상승 빨강 / 하락 파랑.
 *  ±3%에서 채도가 최대가 되도록 잘라 쓴다 (그 이상은 색이 더 진해지지 않음). */
export function changeColor(pct: number | null | undefined): string {
  if (pct == null) return "var(--tm-flat)";
  const t = Math.min(Math.abs(pct) / 3, 1);
  if (Math.abs(pct) < 0.05) return "var(--tm-flat)";
  const a = 0.18 + t * 0.62;
  return pct > 0
    ? `color-mix(in srgb, var(--up) ${Math.round(a * 100)}%, var(--tm-flat))`
    : `color-mix(in srgb, var(--down) ${Math.round(a * 100)}%, var(--tm-flat))`;
}

/** 타일 크기와 이름 길이에 맞는 글자 크기. 너무 작으면 라벨을 생략한다(null).
 *  글자 수를 안 보면 "자동차·부품"이 "다동차·부품"처럼 양옆이 잘린다
 *  (가운데 정렬이라 넘친 만큼 좌우가 같이 깎인다). */
export function labelSize(
  w: number,
  h: number,
  label: string,
): { name: number; pct: number } | null {
  if (w < 34 || h < 22) return null;
  const side = Math.min(w, h);
  // 한글은 글자 폭이 대략 1em. 좌우 여백 8px을 빼고 들어갈 수 있는 크기를 구한다.
  // 타일이 높으면 두 줄까지 쓴다 — "소프트웨어·인터넷"처럼 긴 이름을 살리기 위함.
  const lines = h >= 52 ? 2 : 1;
  const byWidth = (w - 8) / Math.max(Math.ceil(label.length / lines), 1);
  const name = Math.min(side / 4.2, 22, byWidth);
  if (name < 8) return null; // 이 크기면 읽을 수 없다 — 색만 보여준다
  return { name, pct: Math.max(8, name * 0.72) };
}
