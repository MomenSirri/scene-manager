// The board's dot grid. Every card edge sits on a dot: left edge, width and height are whole dots.
// The board is a free canvas: a card stays where it was dropped (gx, gy). Cards never placed by hand are packed
// into the default columns in `order`.
export const GRID = 18;   // px between dots
export const GAP = 1;     // dots between cards
export const COL = 17;    // default card width in dots (306 px)
// A card never shrinks past the point where it stops being usable: label + field stay readable (MIN_W, tables
// MIN_W_TABLE), and the header plus about three rows stay visible (MIN_H; less only when the card has less in it).
export const MIN_W = 15;
export const MIN_W_TABLE = 22;
export const ROOM = 24;   // empty dots kept right of and below the last card, to drop cards into
export const MIN_H = 7;
export const HEAD_H = 3;  // a folded card: header only

export interface Cell { gx: number; gy: number; w: number; h: number }
export interface Size { w: number; h: number }

export const toDots = (px: number) => Math.round(px / GRID);
export const upDots = (px: number) => Math.ceil(px / GRID);
export const px = (c: Cell) => ({ left: c.gx * GRID, top: c.gy * GRID, width: c.w * GRID, height: c.h * GRID });

/** Where every card goes. `gxOf` gives a stored left edge (undefined = first free default column).
 *  `moved` plans a drag without changing anything. */
export function plan(order: string[], sizeOf: (k: string) => Size, gxOf: (k: string) => number | undefined,
                     baseCols = 2, moved?: { key: string; gx: number }): Record<string, Cell> {
  const sky = new Map<number, number>();
  const top = (gx: number, w: number) => {
    let y = 0;
    for (let i = gx; i < gx + w + GAP; i++) y = Math.max(y, sky.get(i) ?? 0);
    return y;
  };
  const out: Record<string, Cell> = {};
  for (const key of order) {
    const { w, h } = sizeOf(key);
    let gx = moved && moved.key === key ? moved.gx : gxOf(key);
    if (gx === undefined) {
      let best = 0, bestY = Infinity;
      for (let i = 0; i < baseCols; i++) {
        const x = i * (COL + GAP), y = top(x, w);
        if (y < bestY) { best = x; bestY = y; }
      }
      gx = best;
    }
    const gy = top(gx, w);
    for (let i = gx; i < gx + w + GAP; i++) sky.set(i, gy + h + GAP);
    out[key] = { gx, gy, w, h };
  }
  return out;
}

export const overlaps = (a: Cell, b: Cell) =>
  a.gx < b.gx + b.w + GAP && b.gx < a.gx + a.w + GAP && a.gy < b.gy + b.h + GAP && b.gy < a.gy + a.h + GAP;

/** The free board: a card with a stored place (gx and gy) sits exactly there. Cards never placed by hand are packed
 *  into the default columns. Then nothing may overlap: a card that would cover one above it moves down under it
 *  (a card that grew, or was resized, pushes its neighbours instead of hiding them). */
export function layout(order: string[], sizeOf: (k: string) => Size,
                       posOf: (k: string) => { gx?: number; gy?: number } | undefined, baseCols = 2): Record<string, Cell> {
  const placed: [string, Cell][] = [], loose: string[] = [];
  for (const k of order) {
    const p = posOf(k);
    if (p && p.gx !== undefined && p.gy !== undefined) placed.push([k, { gx: p.gx, gy: p.gy, ...sizeOf(k) }]);
    else loose.push(k);
  }
  const packed = plan(loose, sizeOf, (k) => posOf(k)?.gx, baseCols);
  const byPlace = (a: [string, Cell], b: [string, Cell]) => a[1].gy - b[1].gy || a[1].gx - b[1].gx;
  const all = [...placed.sort(byPlace), ...loose.map((k) => [k, packed[k]] as [string, Cell]).sort(byPlace)];
  const out: Record<string, Cell> = {}, done: Cell[] = [];
  for (const [k, c] of all) {
    const cell = { ...c };
    for (let hit = done.find((d) => overlaps(cell, d)); hit; hit = done.find((d) => overlaps(cell, d))) cell.gy = hit.gy + hit.h + GAP;
    done.push(cell); out[k] = cell;
  }
  return out;
}

// offsets around a spot, nearest first (searched when a card is dropped onto another one)
const RING: [number, number][] = [];
for (let dx = -48; dx <= 48; dx++) for (let dy = -48; dy <= 48; dy++) RING.push([dx, dy]);
RING.sort((a, b) => a[0] * a[0] + a[1] * a[1] - (b[0] * b[0] + b[1] * b[1]));

/** Where a card dropped at `want` lands: there when the space is empty, otherwise the nearest empty space. */
export function freeSpot(want: Cell, others: Cell[]): Cell {
  for (const [dx, dy] of RING) {
    const c = { ...want, gx: want.gx + dx, gy: want.gy + dy };
    if (c.gx >= 0 && c.gy >= 0 && !others.some((o) => overlaps(c, o))) return c;
  }
  let gy = 0;
  for (const o of others) gy = Math.max(gy, o.gy + o.h + GAP);
  return { ...want, gy };
}
