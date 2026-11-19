import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { call } from "./api";
import { ALWAYS, Field, Switch, WIDE } from "./fields";
import { Cell, COL, GAP, GRID, HEAD_H, layout, MIN_H, MIN_W, MIN_W_TABLE, px, ROOM, toDots, upDots } from "./grid";
import { Icon } from "./icons";
import type { MenuItem, MenuState } from "./Menu";
import type { CardData, CardPref, Detail, Group, ModuleSchema, Schema } from "./types";

export const CARD_COLORS = ["#ff453a", "#ff9f0a", "#30d158", "#2ad4c4", "#64d2ff", "#0a84ff", "#5e5ce6", "#bf5af2", "#8e8e93"];

interface CardProps {
  item: Detail; card: CardData; mod: ModuleSchema; group: Group; pref: CardPref;
  onHeight: (key: string, px: number, headPx: number) => void;   // height the rows need, width the header needs
  onDragStart: (key: string, e: React.PointerEvent) => void;
  onResizeStart: (key: string, e: React.PointerEvent) => void;
  setPref: (key: string, patch: CardPref) => void;
  openMenu: (m: MenuState) => void;
  flash: (text: string) => void;
}

function Card({ item, card, mod, group, pref, onHeight, onDragStart, onResizeStart, setPref, openMenu, flash }: CardProps) {
  const inner = useRef<HTMLDivElement>(null);
  const [renaming, setRenaming] = useState(false);
  const tint = pref.color || group.tint;
  // What the content needs, whatever size the card has now: header + all rows, and a header with its full title.
  const measure = useCallback(() => {
    const el = inner.current;
    if (!el) return;
    const head = el.querySelector(".card-head") as HTMLElement, rows = el.querySelector(".card-rows") as HTMLElement | null;
    let need = 22;   // header padding
    for (const c of Array.from(head.children)) if (!c.classList.contains("grow") && !c.classList.contains("origin")) need += Math.ceil(c.getBoundingClientRect().width) + 8;
    onHeight(card.key, head.offsetHeight + (rows ? rows.offsetHeight + 18 : 0) + 2, need);
  }, [card.key, onHeight]);
  useLayoutEffect(measure);
  useLayoutEffect(() => {
    const ro = new ResizeObserver(measure);
    ro.observe(inner.current!);
    return () => ro.disconnect();
  }, [measure]);

  const run = (cmd: string, args: object = {}) =>
    call(cmd, { id: item.id, module: card.key, ...args })
      .then((r) => { if (r?.errors?.length) flash("Applied with errors: " + r.errors.join("; ")); })
      .catch((e) => flash(String(e.message || e)));

  const menu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const free = mod.props.filter((p) => !card.rows.find((x) => x.key === p.key)?.own && !ALWAYS.has(p.kind) && p.installed !== false);
    const items: MenuItem[] = [
      { custom: <div className="color-dots">{[undefined, ...CARD_COLORS].map((c) =>
          <button key={c || "none"} title={c || "No colour"} className={"color-dot" + (pref.color === c ? " current" : "")}
            style={{ background: c || "transparent" }} onClick={() => setPref(card.key, { color: c })} />)}</div> },
      { sep: true },
      { label: "Rename card", onClick: () => setRenaming(true) },
      { label: pref.folded ? "Unfold" : "Fold", onClick: () => setPref(card.key, { folded: !pref.folded }) },
      { label: "Fit to content", onClick: () => setPref(card.key, { w: undefined, h: undefined }), disabled: !pref.w && !pref.h },
      { sep: true },
      { label: "Store every value here", onClick: () => free.forEach((p) => run("ui_set_value", { prop: p.key, value: valueOut(p.kind, card.rows.find((x) => x.key === p.key)?.value) })), disabled: !free.length },
      { label: "Fetch from scene", onClick: () => run("ui_fetch") },
      ...card.actions.map((label) => ({ label, onClick: () => run("ui_action", { label }) })),
      { sep: true },
      { label: "Clear values set here", onClick: () => run("ui_clear_module") },
      { label: "Remove", danger: true, onClick: () => run("ui_remove_module") },
    ];
    openMenu({ x: r.left, y: r.bottom + 4, items });
  };

  return (
    <div ref={inner} className={"card-inner" + (card.enabled ? "" : " off")}>
      <div className="card-head" style={pref.color ? { background: pref.color + "2e" } : undefined}
        title="Drag to move (snaps to the dots) · double-click to fold"
        onPointerDown={(e) => { if (!(e.target as HTMLElement).closest("button,input")) onDragStart(card.key, e); }}
        onDoubleClick={(e) => { if (!(e.target as HTMLElement).closest("button,input")) setPref(card.key, { folded: !pref.folded }); }}>
        <Icon name={group.icon} color={tint} />
        {renaming
          ? <input className="card-rename" autoFocus defaultValue={pref.title || mod.label}
              onBlur={(e) => { setRenaming(false); const t = e.target.value.trim(); setPref(card.key, { title: t && t !== mod.label ? t : undefined }); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === "Escape") e.currentTarget.blur(); }} />
          : <b>{pref.title || mod.label}</b>}
        {(card.origin || !card.enabled) && <span className="origin">{card.enabled ? "from " + card.origin : "off"}</span>}
        <span className="grow" />
        <button className="icon-btn" title="Card menu" onClick={menu}><Icon name="gear" size={16} /></button>
        <Switch on={card.enabled} tint={tint} title="Module on. Off = leave this part of the scene alone."
          onChange={(on) => run("ui_set_enabled", { enabled: on })} />
      </div>
      {!pref.folded && (
        <div className="card-body"><div className="card-rows">
          {mod.props.map((p) => {
            const row = card.rows.find((r) => r.key === p.key);
            if (!row || (p.installed === false && !row.own && !row.inherited)) return null;   // other renderer, nothing stored
            const wide = WIDE.has(p.kind);
            const dot = row.differs ? "differs" : row.own ? "own" : row.inherited ? "inherited" : "none";
            const tip = row.differs ? "Differs from the scene right now" : row.own ? "Set on this " + item.type
              : row.inherited ? "Inherited from folder '" + row.from + "'" : "Not stored: the scene value is kept";
            const editable = card.enabled && (row.own || ALWAYS.has(p.kind));
            return (
              <div key={p.key} className={"row" + (wide ? " wide" : "")}>
                <i className={"dot " + dot} title={tip} />
                <label title={p.tip}>{p.label}</label>
                <input type="checkbox" className="tick" checked={row.own} disabled={!card.enabled}
                  title="Store this value here (unticked = inherit from the folder, or leave the scene alone)"
                  onChange={(e) => e.target.checked ? run("ui_set_value", { prop: p.key, value: valueOut(p.kind, row.value) }) : run("ui_clear_value", { prop: p.key })} />
                <div className="field">
                  <Field p={p} row={row} nodes={item.nodes} disabled={!editable}
                    onChange={(v) => run("ui_set_value", { prop: p.key, value: v })} />
                </div>
              </div>
            );
          })}
        </div></div>)}
      <div className="grip" title="Drag to resize (snaps to the dots) · double-click to fit the content"
        onPointerDown={(e) => onResizeStart(card.key, e)} onDoubleClick={() => setPref(card.key, { w: undefined, h: undefined })} />
    </div>
  );
}

/** Node pickers hold {name, handle} in the setup; the backend takes the name. */
function valueOut(kind: string, v: any) {
  return (kind === "camera" || kind === "sunlight" || kind === "light") && v && typeof v === "object" ? v.name : v;
}

interface BoardProps {
  item: Detail; schema: Schema; category: string | null;
  prefs: Record<string, CardPref>; setPref: (key: string, patch: CardPref) => void; setPrefs: (p: Record<string, CardPref>) => void;
  order: string[]; setOrder: (o: string[]) => void;
  openMenu: (m: MenuState) => void; flash: (text: string) => void;
}

type Gesture =
  | { kind: "drag"; key: string; dx: number; dy: number; x: number; y: number; started: boolean; sx: number; sy: number }
  | { kind: "resize"; key: string; sx: number; sy: number; w0: number; h0: number; atMin?: boolean };

export function Board({ item, schema, category, prefs, setPref, setPrefs, order, setOrder, openMenu, flash }: BoardProps) {
  const mods = useMemo(() => Object.fromEntries(schema.modules.map((m) => [m.key, m])), [schema]);
  const groups = useMemo(() => Object.fromEntries(schema.groups.map((g) => [g.key, g])), [schema]);
  const [heights, setHeights] = useState<Record<string, number>>({});
  const [headW, setHeadW] = useState<Record<string, number>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  // Called by every card after every render: set state ONLY for a real change. (Calling the setters each time, even
  // with the same value, could keep React re-rendering until it gave up: folding a card blanked the whole window.)
  const seen = useRef<Record<string, string>>({});
  const onHeight = useCallback((key: string, h: number, w: number) => {
    if (seen.current[key] === h + ":" + w) return;
    seen.current[key] = h + ":" + w;
    setHeights((old) => (old[key] === h ? old : { ...old, [key]: h }));
    setHeadW((old) => (old[key] === w ? old : { ...old, [key]: w }));
  }, []);

  const cards = item.cards.filter((c) => mods[c.key] && (!category || mods[c.key].group === category));
  const keys = useMemo(() => {
    const pos = new Map(order.map((k, i) => [k, i]));
    return cards.map((c) => c.key).sort((a, b) => (pos.get(a) ?? 1e6) - (pos.get(b) ?? 1e6));
  }, [cards.map((c) => c.key).join(","), order]);

  // smallest size a card may be dragged to (dots), and the height its rows need
  const limits = useCallback((k: string) => {
    const wide = mods[k]?.props.some((x) => x.kind === "table");
    const natural = Math.max(HEAD_H, upDots(heights[k] ?? 60));
    // never narrower than the full title needs, nor than label + value + tick need
    const minW = Math.max(wide ? MIN_W_TABLE : MIN_W, upDots(headW[k] ?? 0));
    return { wide, natural, minW, minH: Math.min(natural, MIN_H) };
  }, [heights, headW, mods]);
  const sizeOf = useCallback((k: string) => {
    const p = prefs[k] || {};
    const { wide, natural, minW, minH } = limits(k);
    const w = Math.max(minW, p.w ?? (wide ? COL * 2 + GAP : COL));
    // as tall as the module's rows need, rounded up to the next dot; a resized card keeps its own height
    return { w, h: p.folded ? natural : Math.max(minH, p.h ?? natural) };
  }, [prefs, limits]);
  // dots that fit across the window: cards that would stick out move to where there is room
  const [viewW, setViewW] = useState(0);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => setViewW(Math.max(MIN_W, Math.floor((el.clientWidth - 2) / GRID)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const rest = useMemo(() => layout(keys, sizeOf, (k) => prefs[k], viewW), [keys, sizeOf, prefs, viewW]);

  const local = (e: PointerEvent | React.PointerEvent) => {
    const r = boardRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  // while a card is dragged, the others already flow around the place it would land in
  const cells = useMemo(() => {
    if (!gesture || gesture.kind !== "drag" || !gesture.started || !rest[gesture.key]) return rest;
    let gx = Math.max(0, toDots(gesture.x - gesture.dx));
    const gy = Math.max(0, toDots(gesture.y - gesture.dy));
    // near the left edge of a column that is already there: line up with it (keeps columns straight)
    const held = gx;
    let near = 4;
    for (const k of keys) {
      if (k === gesture.key) continue;
      const d = Math.abs(rest[k].gx - held);
      if (d < near) { near = d; gx = rest[k].gx; }
    }
    return layout(keys, sizeOf, (k) => prefs[k], viewW, { key: gesture.key, gx, gy, shown: rest });
  }, [gesture, rest, keys, sizeOf, prefs, viewW]);
  const target: Cell | null = gesture?.kind === "drag" && gesture.started ? cells[gesture.key] ?? null : null;

  useEffect(() => {
    if (!gesture) return;
    const move = (e: PointerEvent) => {
      if (gesture.kind === "drag") {
        const sc = scrollRef.current;
        if (sc && gesture.started) {   // near an edge: scroll, so a card can be carried anywhere
          const r = sc.getBoundingClientRect(), edge = 36, step = 24;
          sc.scrollBy((e.clientX > r.right - edge ? step : e.clientX < r.left + edge ? -step : 0),
                      (e.clientY > r.bottom - edge ? step : e.clientY < r.top + edge ? -step : 0));
        }
        const p = local(e);
        const started = gesture.started || Math.abs(e.clientX - gesture.sx) + Math.abs(e.clientY - gesture.sy) > 4;
        setGesture({ ...gesture, x: p.x, y: p.y, started });
      } else {
        const { minW, minH } = limits(gesture.key);
        const w = Math.max(minW, toDots(gesture.w0 + e.clientX - gesture.sx));
        const h = Math.max(minH, toDots(gesture.h0 + e.clientY - gesture.sy));
        const cur = prefs[gesture.key] || {};
        const atMin = w === minW || h === minH;
        if (cur.w !== w || cur.h !== h) setPref(gesture.key, { w, h });
        if (atMin !== !!gesture.atMin) setGesture({ ...gesture, atMin });
      }
    };
    const up = () => {
      if (gesture.kind === "drag" && target) {
        // every card keeps the place and turn it shows at now
        const next = { ...prefs };
        // (a card the narrow window moved aside keeps its own column for when the window is wide again)
        for (const k of keys) {
          const c = cells[k], own = prefs[k]?.gx;
          const gx = k !== gesture.key && own !== undefined && viewW && own + c.w > viewW ? own : c.gx;
          next[k] = { ...(next[k] || {}), gx, gy: c.gy, gap: c.gap };
        }
        setPrefs(next);
      }
      setGesture(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", up); };
  }, [gesture, target, prefs, keys, cells, order, limits]);

  const startDrag = (key: string, e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const p = local(e), c = px(cells[key]);
    setGesture({ kind: "drag", key, dx: p.x - c.left, dy: p.y - c.top, x: p.x, y: p.y, started: false, sx: e.clientX, sy: e.clientY });
  };
  const startResize = (key: string, e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault(); e.stopPropagation();
    const c = px(cells[key]);
    setGesture({ kind: "resize", key, sx: e.clientX, sy: e.clientY, w0: c.width, h0: c.height });
  };

  const glow = target ? px(target) : gesture?.kind === "resize" && cells[gesture.key] ? px(cells[gesture.key]) : null;
  let right = 0, bottom = 0;
  for (const c of Object.values(cells)) { right = Math.max(right, (c.gx + c.w) * GRID); bottom = Math.max(bottom, (c.gy + c.h) * GRID); }
  if (glow) { right = Math.max(right, glow.left + glow.width); bottom = Math.max(bottom, glow.top + glow.height); }

  return (
    <div className="board-scroll" ref={scrollRef}>
      <div ref={boardRef} className={"board" + (gesture ? " busy" : "")} style={{ width: right, height: bottom + GRID * ROOM }}>
        {glow && <>
          <div className="hot-dots" style={{ left: glow.left - GRID / 2, top: glow.top - GRID / 2, width: glow.width + GRID, height: glow.height + GRID }} />
          <div className={"glow" + (target ? " fill" : "") + (gesture?.kind === "resize" && gesture.atMin ? " limit" : "")} style={glow} />
        </>}
        {cards.length === 0 && <p className="muted empty-board">No {category ? groups[category]?.label.toLowerCase() + " " : ""}modules on this {item.type}. Use + in the left bar.</p>}
        {cards.map((card) => {
          const cell = cells[card.key];
          if (!cell) return null;
          const dragging = gesture?.kind === "drag" && gesture.key === card.key && gesture.started;
          const box = px(cell);
          const style = dragging ? { ...box, left: gesture.x - gesture.dx, top: gesture.y - gesture.dy } : box;
          const fixed = !!(prefs[card.key]?.h) && !prefs[card.key]?.folded;
          return (
            <div key={card.key} className={"card" + (dragging ? " dragging" : "") + (gesture?.kind === "resize" && gesture.key === card.key ? " resizing" : "") + (fixed ? " fixed" : "")}
              style={style} data-module={card.key}>
              <Card item={item} card={card} mod={mods[card.key]} group={groups[mods[card.key].group] || schema.groups[0]}
                pref={prefs[card.key] || {}} onHeight={onHeight} onDragStart={startDrag} onResizeStart={startResize}
                setPref={setPref} openMenu={openMenu} flash={flash} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
