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

/** 타일에 들어갈 글자 크기. 넣을 수 없으면 null (색만 보여준다).
 *
 *  가로만 보면 안 된다 — 가운데 정렬이라 넘친 만큼 좌우가 같이 깎여
 *  "자동차·부품"이 "다동차·부품"으로 보인다. 폭·높이·줄수를 함께 따진다.
 */
export function labelSize(
  w: number,
  h: number,
  label: string,
  opts: { pct?: boolean } = {},
): { name: number; pct: number; lines: number } | null {
  const showPct = opts.pct !== false;
  if (w < 30 || h < 18) return null;

  const padX = 6;
  const padY = 4;
  const avail = w - padX;
  // 굵은 한글은 글자 폭이 글자 크기보다 약간 넓다. 1.04로 잡아 여유를 둔다.
  const CHAR_W = 1.04;
  const chars = Math.max(label.length, 1);

  // "미래에셋증권"처럼 띄어쓰기·가운뎃점이 없는 한글 이름은 줄바꿈이 안 된다
  // (word-break: keep-all). 2줄로 계산해 글자를 키우면 한 줄로 삐져나와 잘린다.
  const canWrap = /[\s·&]/.test(label);
  for (const lines of canWrap ? [1, 2] : [1]) {
    // 그 줄 수로 나눠 담았을 때 한 줄 최대 글자 수
    const perLine = Math.ceil(chars / lines);
    const byWidth = avail / (perLine * CHAR_W);
    // 세로: 이름 lines줄(줄간 1.15) + 등락률 한 줄(이름의 0.72배)
    const heightUnits = lines * 1.15 + (showPct ? 0.72 * 1.2 : 0);
    const byHeight = (h - padY) / heightUnits;
    const name = Math.min(byWidth, byHeight, 22);
    if (name >= 9) return { name, pct: Math.max(8, name * 0.72), lines };
  }

  // 등락률을 빼면 들어가는지 한 번 더 본다 (작은 타일은 이름만이라도 보이게)
  if (showPct) {
    const only = labelSize(w, h, label, { pct: false });
    if (only) return { ...only, pct: 0 };
  }
  return null;
}
