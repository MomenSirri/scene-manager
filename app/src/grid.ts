// The board's dot grid. Every card edge sits on a dot: left edge, width and height are whole dots.
// The board flows, but keeps the user's own spacing: a card keeps the column it was dropped in (gx), its turn in
// that column (from gy) and the empty space left above it (gap). A card that grows pushes the ones below down by
// that much, one that folds lets them come back up by that much. Cards that do not fit the window's width move to
// the place with the most room. Cards never placed by hand fill the default columns in `order`, close together.
export const GRID = 18;   // px between dots
export const GAP = 1;     // dots between cards
export const COL = 17;    // default card width in dots (306 px)
// A card never shrinks past the point where it stops being usable: label + field stay readable (MIN_W, tables
// MIN_W_TABLE), and the header plus about three rows stay visible (MIN_H; less only when the card has less in it).
export const MIN_W = 15;
export const MIN_W_TABLE = 22;
export const ROOM = 8;    // empty dots kept below the last card, to drop cards into
export const MIN_H = 7;
export const HEAD_H = 3;  // a folded card: header only

export interface Cell { gx: number; gy: number; w: number; h: number }
export interface Size { w: number; h: number }

export const toDots = (px: number) => Math.round(px / GRID);
export const upDots = (px: number) => Math.ceil(px / GRID);
export const px = (c: Cell) => ({ left: c.gx * GRID, top: c.gy * GRID, width: c.w * GRID, height: c.h * GRID });

export const overlaps = (a: Cell, b: Cell) =>
  a.gx < b.gx + b.w + GAP && b.gx < a.gx + a.w + GAP && a.gy < b.gy + b.h + GAP && b.gy < a.gy + a.h + GAP;

export interface Pos { gx?: number; gy?: number; gap?: number }
// gap: empty dots the user left above the card (kept when the cards above change height); want: a row to hold if free
type Item = { key: string; gx?: number; gy?: number; gap?: number; want?: number; w: number; h: number };
export type Placed = Cell & { gap: number };

/** Cards in the turn they are placed: by hand placed ones top to bottom, then the ones never placed. */
function sequence(order: string[], sizeOf: (k: string) => Size, posOf: (k: string) => Pos | undefined): Item[] {
  const placed: Item[] = [], loose: Item[] = [];
  for (const key of order) {
    const p = posOf(key) || {};
    // placed before gaps were stored: hold the stored row
    (p.gx !== undefined && p.gy !== undefined ? placed : loose).push({ key, gx: p.gx, gy: p.gy, gap: p.gap, want: p.gap === undefined ? p.gy : undefined, ...sizeOf(key) });
  }
  placed.sort((a, b) => a.gy! - b.gy! || a.gx! - b.gx!);
  return [...placed, ...loose];
}

/** Put every card in turn under what is already there, plus the space it keeps above it. `viewW` = dots that fit the window (0: no limit). */
function flow(seq: Item[], viewW: number): Record<string, Placed> {
  const sky = new Map<number, number>();
  const top = (gx: number, w: number) => {
    let y = 0;
    for (let i = gx; i < gx + w + GAP; i++) y = Math.max(y, sky.get(i) ?? 0);
    return y;
  };
  const baseCols = viewW ? Math.max(1, Math.floor((viewW + GAP) / (COL + GAP))) : 2;
  const lefts = new Set<number>();
  for (let i = 0; i < baseCols; i++) lefts.add(i * (COL + GAP));
  const out: Record<string, Placed> = {};
  for (const it of seq) {
    const { w, h } = it;
    const maxX = viewW ? Math.max(0, viewW - w) : Infinity;
    let gx = it.gx;
    if (gx === undefined || gx > maxX) {
      // no place of its own, or it would stick out of the window: the left edge with the most room above it
      let best = 0, bestY = Infinity;
      for (const x of [...lefts].sort((a, b) => a - b)) {
        if (x > maxX) continue;
        const y = top(x, w);
        if (y < bestY) { best = x; bestY = y; }
      }
      gx = best;
    }
    const under = top(gx, w);   // right under the cards above
    const gy = it.want !== undefined ? Math.max(under, it.want) : under + (it.gap ?? 0);
    for (let i = gx; i < gx + w + GAP; i++) sky.set(i, gy + h + GAP);
    lefts.add(gx);
    out[it.key] = { gx, gy, w, h, gap: gy - under };
  }
  return out;
}

/** Where every card goes. `moved` plans a drag: that card takes its turn at the dot it is held over (before the
 *  first card under it whose middle is still below), everything else flows around it. */
export function layout(order: string[], sizeOf: (k: string) => Size, posOf: (k: string) => Pos | undefined,
                       viewW = 0, moved?: { key: string; gx: number; gy: number; shown: Record<string, Cell> }): Record<string, Placed> {
  let seq = sequence(order, sizeOf, posOf);
  if (moved) {
    const me = seq.find((i) => i.key === moved.key);
    if (me) {
      // the others keep the turn they show in now
      const rest = seq.filter((i) => i !== me).map((i) => ({ i, c: moved.shown[i.key] }))
        .sort((a, b) => (a.c && b.c ? a.c.gy - b.c.gy || a.c.gx - b.c.gx : 0));
      const gx = viewW ? Math.min(moved.gx, Math.max(0, viewW - me.w)) : moved.gx;
      const at = rest.findIndex(({ c }) => c && c.gx < gx + me.w + GAP && gx < c.gx + c.w + GAP && c.gy + c.h / 2 > moved.gy);
      // the held card lands on the row it is held over when that is free; the others stay where they show, or move down
      const mine = { ...me, gx, gy: moved.gy, want: moved.gy };
      const list = rest.map(({ i, c }) => ({ ...i, gx: c ? c.gx : i.gx, want: c ? c.gy : i.want }));
      list.splice(at < 0 ? list.length : at, 0, mine);
      seq = list;
    }
  }
  return flow(seq, viewW);
}

