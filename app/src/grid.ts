// The board's dot grid. Every card edge sits on a dot: left edge, width and height are whole dots.
// Cards keep their left edge (gx) and pack upward under the cards above them, in `order`.
export const GRID = 18;   // px between dots
export const GAP = 1;     // dots between cards
export const COL = 17;    // default card width in dots (306 px)
export const MIN_W = 10;
export const MIN_H = 3;

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

/** Dropping `key` with its top-left corner at (x, y) px: its new left edge, the new order, and where it lands. */
export function dropPlan(key: string, x: number, y: number, pointerY: number, order: string[], cells: Record<string, Cell>,
                         sizeOf: (k: string) => Size, gxOf: (k: string) => number | undefined, baseCols = 2) {
  const gx = Math.max(0, toDots(x));
  const w = sizeOf(key).w;
  const others = order.filter((k) => k !== key);
  // among the cards the footprint overlaps sideways, go in front of the first one whose middle is below the pointer
  const before = [...others].sort((a, b) => cells[a].gy - cells[b].gy).find((k) => {
    const c = cells[k];
    return c.gx < gx + w + GAP && gx < c.gx + c.w + GAP && pointerY < (c.gy + c.h / 2) * GRID;
  });
  const next = [...others];
  next.splice(before ? next.indexOf(before) : next.length, 0, key);
  // the others are planned where they are now, so only the dragged card moves
  const pinned = (k: string) => (k === key ? gx : cells[k]?.gx ?? gxOf(k));
  const cell = plan(next, sizeOf, pinned, baseCols)[key];
  return { gx, order: next, cell };
}
