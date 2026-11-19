import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { call, connected as isConnected, inApp, onEvent, store } from "./api";
import { Board } from "./Board";
import { Icon } from "./icons";
import { Menu, MenuItem, MenuState } from "./Menu";
import { Tree, visibleRows } from "./Tree";
import { Chat } from "./Chat";
import { Library, LibraryCtx } from "./Library";
import type { CardPref, Detail, Schema, State } from "./types";

const TAG_COLORS = ["#ff453a", "#ff9f0a", "#30d158", "#2ad4c4", "#64d2ff", "#0a84ff", "#5e5ce6", "#bf5af2"];
type Page = "setups" | "queue" | "claude" | "settings";

export function App() {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [online, setOnline] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("setups");
  const [category, setCategory] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [folded, setFolded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [tags, setTags] = useState<Set<string>>(new Set());
  const [renaming, setRenaming] = useState<string | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [palette, setPalette] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [prefs, setPrefsState] = useState<Record<string, CardPref>>({});
  const [order, setOrderState] = useState<string[]>([]);
  const [thumbs, setThumbs] = useState<Record<string, string | null>>({});
  const [message, setMessage] = useState("");
  const [onTop, setOnTop] = useState(false);
  const [wnd, setWnd] = useState({ owned: false, rolled: false, attach: true });
  const [queue, setQueue] = useState<any[]>([]);
  const [busy, setBusy] = useState("");
  const [library, setLibrary] = useState<string | null>(null);   // open environment library, aimed at this slot
  const openLibrary = useCallback((target: string) => { setPage("setups"); setLibrary(target); }, []);
  const selRef = useRef(selected); selRef.current = selected;
  const searchRef = useRef<HTMLInputElement>(null);
  const msgTimer = useRef<number>();

  const flash = useCallback((text: string) => {
    setMessage(text);
    window.clearTimeout(msgTimer.current);
    msgTimer.current = window.setTimeout(() => setMessage(""), 5000);
  }, []);
  const run = useCallback((cmd: string, args: object = {}) => call(cmd, args).catch((e) => { flash(String(e.message || e)); throw e; }), [flash]);

  // ---- data: 3ds Max is the single source; the app only shows it ----
  const refresh = useCallback(async () => {
    try {
      const st: State = await call("ui_state");
      setOnline(true);
      setState(st);
      let id = selRef.current;
      if (!id || !st.items.some((i) => i.id === id)) { id = st.active || st.items[0]?.id || null; setSelected(id); }
      setDetail(id ? await call("ui_item", { id }) : null);
    } catch { setOnline(false); }
  }, []);

  useEffect(() => {
    let pending = false, alive = true;
    const soon = () => { if (!pending) { pending = true; setTimeout(() => { pending = false; if (alive) refresh(); }, 20); } };
    const boot = async () => {
      if (!(await isConnected())) { setOnline(false); return; }
      setSchema(await call("ui_schema"));
      await refresh();
    };
    boot();
    const off = onEvent((ev) => {
      if (ev.event === "connected") boot();
      else if (ev.event === "disconnected" || ev.event === "closing") setOnline(false);
      else if (ev.event === "changed") soon();
      else if (ev.event === "window") { setWnd({ owned: !!ev.owned, rolled: !!ev.rolled, attach: ev.attach !== false }); setOnTop(!!ev.onTop); }
    });
    const retry = inApp ? 0 : window.setInterval(() => { if (!document.hidden) soon(); }, 4000);
    // back from 3ds Max: the scene may have changed, so read it again for the "differs" dots
    window.addEventListener("focus", soon);
    store.get("cards", {} as Record<string, CardPref>).then(setPrefsState);
    store.get("order", [] as string[]).then(setOrderState);
    store.get("folded", [] as string[]).then((f) => setFolded(new Set(f)));
    window.sm?.status().then((s) => { setOnTop(s.onTop); setWnd({ owned: s.owned, rolled: s.rolled, attach: s.attach }); });
    return () => { alive = false; off(); window.clearInterval(retry); window.removeEventListener("focus", soon); };
  }, [refresh]);

  useEffect(() => { if (selected && online) call("ui_item", { id: selected }).then(setDetail).catch(() => {}); }, [selected]);
  useEffect(() => {  // thumbnail of the selected item, asked for once and again when it changes
    const it = state?.items.find((i) => i.id === selected);
    if (it?.thumb) call("ui_thumbnail", { id: it.id }).then((r) => setThumbs((t) => ({ ...t, [it.id]: r.data }))).catch(() => {});
  }, [selected, state]);
  useEffect(() => { if (page === "queue") call("ui_queue", { ids: [...checked] }).then(setQueue).catch(() => {}); }, [page, checked, state]);

  const setPref = useCallback((key: string, patch: CardPref) => setPrefsState((old) => {
    const next = { ...old, [key]: { ...(old[key] || {}), ...patch } };
    store.set("cards", next);
    return next;
  }), []);
  const setPrefs = useCallback((next: Record<string, CardPref>) => { setPrefsState(next); store.set("cards", next); }, []);
  const setOrder = useCallback((next: string[]) => { setOrderState(next); store.set("order", next); }, []);
  const toggleFold = (id: string) => setFolded((old) => {
    const next = new Set(old); next.has(id) ? next.delete(id) : next.add(id);
    store.set("folded", [...next]);
    return next;
  });

  // ---- actions ----
  const item = state?.items.find((i) => i.id === selected) || null;
  const parentFor = () => (item ? (item.type === "folder" ? item.id : item.parent) : null);
  const activate = (id: string) => run("ui_activate", { id }).then((r) => {
    const it = state?.items.find((i) => i.id === id);
    flash(r.errors.length ? "Activated with errors: " + r.errors.join("; ") : `Activated ${it?.name ?? ""} in ${r.ms} ms`);
  }).catch(() => {});
  const reveal = (id: string, rename: boolean) => { setSearch(""); setTags(new Set()); setSelected(id); if (rename) setRenaming(id); };
  const newSetup = (parent = parentFor()) => run("ui_new_setup", { parent }).then((r) => reveal(r.id, true)).catch(() => {});
  const newFolder = (parent = parentFor()) => run("ui_new_folder", { parent }).then((r) => reveal(r.id, true)).catch(() => {});
  const remove = (id: string) => {
    const it = state?.items.find((i) => i.id === id);
    if (it && window.confirm(`Delete '${it.name}'${it.type === "folder" ? " and everything inside it" : ""}?`)) run("ui_delete", { id }).catch(() => {});
  };
  const render = async (ids: string[]) => {
    if (!ids.length) return;
    setBusy("Rendering… 3ds Max is busy until it finishes.");
    try {
      const res = await run("ui_render", { ids });
      flash(res.map((r: any) => `${r.setup}: ${r.status}`).join("  ·  "));
    } catch { /* shown by run */ } finally { setBusy(""); }
  };

  const itemMenu = (id: string | null, x: number, y: number) => {
    const it = state?.items.find((i) => i.id === id);
    const folder = it ? (it.type === "folder" ? it.id : it.parent) : null;
    const items: MenuItem[] = it ? [
      ...(it.type === "setup" ? [{ label: "Activate", hint: "Enter", onClick: () => activate(it.id) }] : []),
      { label: "Render", onClick: () => render([it.id]) },
      { sep: true },
      { label: "New setup here", hint: "Ctrl+N", onClick: () => newSetup(folder) },
      { label: "New folder here", onClick: () => newFolder(folder) },
      { sep: true },
      { label: `Capture scene into this ${it.type}`, onClick: () => run("ui_fetch", { id: it.id }).catch(() => {}) },
      { label: "Grab thumbnail", onClick: () => run("ui_grab_thumbnail", { id: it.id }).catch(() => {}) },
      { label: "Rename", hint: "F2", onClick: () => setRenaming(it.id) },
      { label: "Duplicate", hint: "Ctrl+D", onClick: () => run("ui_duplicate", { id: it.id }).then((r) => reveal(r.id, false)).catch(() => {}) },
      { custom: <div className="color-dots">{[null, ...TAG_COLORS].map((c) =>
          <button key={c || "none"} className={"color-dot" + (it.color === c ? " current" : "")} style={{ background: c || "transparent" }} title={c || "No colour"}
            onClick={() => { setMenu(null); run("ui_update", c ? { id: it.id, color: c } : { id: it.id, clear_color: true }).catch(() => {}); }} />)}</div> },
      { sep: true },
      { label: "Delete", hint: "Del", danger: true, onClick: () => remove(it.id) },
    ] : [
      { label: "New setup", hint: "Ctrl+N", onClick: () => newSetup(null) },
      { label: "New folder", onClick: () => newFolder(null) },
    ];
    items.push({ sep: true },
      { label: state?.baseline ? "Replace scene baseline" : "Capture scene baseline", onClick: () => run("ui_baseline", { action: "capture" }).then(() => flash("Baseline captured.")).catch(() => {}) },
      { label: "Restore scene to baseline", disabled: !state?.baseline, onClick: () => run("ui_baseline", { action: "restore" }).catch(() => {}) },
      { label: "Clear baseline", disabled: !state?.baseline, onClick: () => run("ui_baseline", { action: "clear" }).catch(() => {}) });
    setMenu({ x, y, items });
  };

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest("input,textarea,select")) return;
    const ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && e.key.toLowerCase() === "f") { e.preventDefault(); setPage("setups"); searchRef.current?.focus(); return; }
    if (page !== "setups" || !state) return;
    if (ctrl && e.key.toLowerCase() === "n") { e.preventDefault(); e.shiftKey ? newFolder() : newSetup(); }
    else if (!item) return;
    else if (e.key === "Enter" && item.type === "setup") activate(item.id);
    else if (e.key === "F2") setRenaming(item.id);
    else if (e.key === "Delete") remove(item.id);
    else if (ctrl && e.key.toLowerCase() === "d") { e.preventDefault(); run("ui_duplicate", { id: item.id }).then((r) => reveal(r.id, false)).catch(() => {}); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const rows = visibleRows(state, folded, search, tags).rows;
      const i = rows.findIndex((r) => r.item.id === item.id) + (e.key === "ArrowDown" ? 1 : -1);
      if (rows[i]) setSelected(rows[i].item.id);
    }
  };

  const tagCounts = useMemo(() => {
    const m = new Map<string, number>();
    state?.items.forEach((i) => i.tags.forEach((t) => m.set(t, (m.get(t) || 0) + 1)));
    return [...m.entries()].sort();
  }, [state]);
  const setupCount = state?.items.filter((i) => i.type === "setup").length ?? 0;
  const active = state?.items.find((i) => i.id === state.active);
  const pathOf = (id: string | null | undefined): string => {
    const it = state?.items.find((i) => i.id === id);
    return it ? (it.parent ? pathOf(it.parent) + " / " : "") + it.name : "";
  };

  // Moving the window: the pointer is followed by the app itself (see main.cjs "sm:drag").
  const dragBar = (e: React.PointerEvent<HTMLElement>) => {
    if (!inApp || e.button !== 0 || (e.target as HTMLElement).closest("button")) return;
    const bar = e.currentTarget, id = e.pointerId;
    let frame = 0, x = e.screenX, y = e.screenY;
    const move = (ev: PointerEvent) => {
      x = ev.screenX; y = ev.screenY;
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; window.sm!.win.drag("move", x, y); });
    };
    const end = () => {
      bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", end); bar.removeEventListener("pointercancel", end);
      try { bar.releasePointerCapture(id); } catch (_) { /* already released */ }
      window.sm!.win.drag("end");
    };
    bar.setPointerCapture(id);
    bar.addEventListener("pointermove", move); bar.addEventListener("pointerup", end); bar.addEventListener("pointercancel", end);
    window.sm!.win.drag("start", x, y);
  };

  return (
    <LibraryCtx.Provider value={openLibrary}>
    <div className={"app" + (wnd.rolled ? " rolled" : "")} onKeyDown={onKey} tabIndex={-1}>
      <header className="titlebar" onPointerDown={dragBar} onDoubleClick={(e) => { if (inApp && !wnd.rolled && !(e.target as HTMLElement).closest("button")) window.sm!.win.maximize(); }}>
        <Icon name="setups" size={16} color="#64d2ff" />
        <span className="title">Scene Manager</span>
        {state?.file && <span className="muted file">{state.file}</span>}
        <span className="grow" />
        {inApp && <>
          <button className={"win-btn pin" + (onTop ? " on" : "")} title={onTop ? "Above all programs: on" : "Above all programs: off (stays above 3ds Max)"}
            onClick={() => window.sm!.win.setOnTop(!onTop).then(setOnTop)}><Icon name="pin" size={15} /></button>
          <button className="win-btn" title={wnd.rolled ? "Open" : "Roll up to the title bar"} onClick={() => window.sm!.win.minimize()}><Icon name={wnd.rolled ? "maximize" : "minimize"} size={15} /></button>
          <button className="win-btn max" title="Maximise" onClick={() => window.sm!.win.maximize()}><Icon name="maximize" size={15} /></button>
          <button className="win-btn close" title="Close" onClick={() => window.sm!.win.close()}><Icon name="close" size={15} /></button>
        </>}
      </header>

      <div className="main">
        <nav className="rail">
          <button className={page === "setups" && !category && !library ? "on" : ""} title="Setups: all modules" onClick={() => { setPage("setups"); setLibrary(null); setCategory(null); }}><Icon name="setups" size={20} /></button>
          <button className={page === "queue" ? "on" : ""} title="Render queue" onClick={() => setPage("queue")}><Icon name="render" size={20} /></button>
          <button className={page === "setups" && library ? "on" : ""} title="Environment library: HDRIs and environments as thumbnails" disabled={!detail}
            onClick={() => { setPage("setups"); setLibrary(library ? null : "environment"); }}><Icon name="library" size={20} /></button>
          <hr />
          <button className="add" title="Add a module to this setup or folder" disabled={!detail} onClick={() => setPalette(!palette)}><Icon name="plus" size={20} /></button>
          {schema?.groups.map((g) => (
            <button key={g.key} className={page === "setups" && !library && category === g.key ? "on" : ""} title={`${g.label} modules (click again for all)`}
              style={page === "setups" && category === g.key ? { color: g.tint } : undefined}
              onClick={() => { setPage("setups"); setLibrary(null); setCategory(category === g.key ? null : g.key); }}><Icon name={g.icon} size={20} /></button>))}
          <span className="grow" />
          <button className={chatOpen ? "on" : ""} title="Claude: ask for changes in plain words" onClick={() => setChatOpen(!chatOpen)}><Icon name="claude" size={20} /></button>
          <button className={page === "settings" ? "on" : ""} title="Settings" onClick={() => setPage("settings")}><Icon name="settings" size={20} /></button>
        </nav>

        {!online || !state || !schema ? (
          <section className="waiting">
            <div className="pulse" />
            <h2>Waiting for 3ds Max</h2>
            <p className="muted">Open 3ds Max and press the Scene Manager button. This window connects by itself.</p>
          </section>
        ) : page === "setups" ? (
          <>
            <aside className="sidebar">
              <div className="side-head">
                <h1>Setups</h1><span className="muted">{setupCount}</span><span className="grow" />
                <button className="icon-btn" title="New folder (Ctrl+Shift+N)" onClick={() => newFolder()}><Icon name="folder" size={17} /></button>
                <button className="btn primary" title="New setup from the current scene (Ctrl+N)" onClick={() => newSetup()}>New Setup</button>
              </div>
              <label className="search"><Icon name="search" size={15} />
                <input ref={searchRef} value={search} placeholder="Search setups" onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Escape") { setSearch(""); e.currentTarget.blur(); } }} /></label>
              {tagCounts.length > 0 && <div className="chips">
                <button className={"chip" + (tags.size ? "" : " on")} onClick={() => setTags(new Set())}>All {setupCount}</button>
                {tagCounts.map(([t, n]) => <button key={t} className={"chip" + (tags.has(t) ? " on" : "")}
                  onClick={() => setTags((old) => { const s = new Set(old); s.has(t) ? s.delete(t) : s.add(t); return s; })}>{t} {n}</button>)}
              </div>}
              <Tree state={state} selected={selected} checked={checked} folded={folded} search={search} tags={tags} renaming={renaming}
                columns={["camera", "output"]} onSelect={setSelected} onActivate={activate} onToggleFold={toggleFold}
                onCheck={(ids, on) => setChecked((old) => { const s = new Set(old); ids.forEach((i) => (on ? s.add(i) : s.delete(i))); return s; })}
                onRename={(id, name) => { setRenaming(null); if (name && name !== state.items.find((i) => i.id === id)?.name) run("ui_update", { id, name }).catch(() => {}); }}
                onMenu={itemMenu} onMove={(id, parent, index) => run("ui_move", { id, parent, index }).catch(() => {})} />
            </aside>

            {library && detail ? <Library detail={detail} target={library} setTarget={setLibrary} onClose={() => setLibrary(null)} flash={flash} openMenu={setMenu} /> :
            <section className="detail">
              {detail && item ? <>
                <div className="detail-head">
                  <button className="thumb" title="Click to grab the active viewport as thumbnail" onClick={() => run("ui_grab_thumbnail", { id: detail.id }).catch(() => {})}>
                    {item.thumb && thumbs[item.id] ? <img src={"data:image/png;base64," + thumbs[item.id]} alt="" /> : <Icon name="photo" size={22} />}
                  </button>
                  <div className="names">
                    <Inline key={detail.id + "n"} className="name" value={detail.name} onCommit={(v) => v && run("ui_update", { id: detail.id, name: v }).catch(() => {})} />
                    <Inline key={detail.id + "d"} className="desc" value={detail.description} placeholder="Add a description" onCommit={(v) => run("ui_update", { id: detail.id, description: v }).catch(() => {})} />
                    <Inline key={detail.id + "t"} className="desc" value={detail.tags.join(", ")} placeholder="Tags, comma separated"
                      onCommit={(v) => run("ui_update", { id: detail.id, tags: v.split(",").map((t) => t.trim()).filter(Boolean) }).catch(() => {})} />
                  </div>
                  {detail.type === "setup" && <button className={"btn primary" + (detail.active ? " active" : "")} title="Apply this setup to the scene (Enter)" onClick={() => activate(detail.id)}>{detail.active ? "Re-apply" : "Activate"}</button>}
                  <button className="btn" title="Render this setup, or every setup in this folder" onClick={() => render([detail.id])}>Render</button>
                  <button className="icon-btn" title="More" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); itemMenu(detail.id, r.right - 200, r.bottom + 4); }}><Icon name="more" /></button>
                </div>
                <p className="muted hint">
                  {detail.type === "folder" ? `Folder. Values set here pass down to the ${detail.setups_inside} setup(s) inside; a setup overrides any of them by ticking the property.`
                    : <><i className="dot own" /> set here <i className="dot inherited" /> from {detail.folder ? `folder '${detail.folder}'` : "a folder"} <i className="dot none" /> scene value kept <i className="dot differs" /> differs from the scene</>}
                </p>
                <Board item={detail} schema={schema} category={category} prefs={prefs} setPref={setPref} setPrefs={setPrefs}
                  order={order} setOrder={setOrder} openMenu={setMenu} flash={flash} />
              </> : <p className="muted pad">No setups yet. Set up the scene in 3ds Max and press New Setup.</p>}
            </section>}
          </>
        ) : page === "queue" ? (
          <section className="page">
            <h1>Render queue</h1>
            <p className="muted">Tick setups or folders in the Setups list to queue them. Renders run in 3ds Max, one after another.</p>
            <div className="queue">
              <div className="q-row q-head"><span>Setup</span><span>Camera</span><span>Size</span><span>Frames</span><span>Output</span></div>
              {queue.map((q) => <div key={q.id} className="q-row"><span>{q.path}</span><span>{q.camera}</span><span>{q.size}</span><span>{q.frames}</span><span title={q.output}>{q.output || "not saved"}</span></div>)}
              {!queue.length && <p className="muted pad">Nothing queued.</p>}
            </div>
            <div className="right"><button className="btn primary" disabled={!queue.length} onClick={() => render(queue.map((q) => q.id))}>Render {queue.length || ""} setup{queue.length === 1 ? "" : "s"}</button></div>
          </section>
        ) : (
          <section className="page">
            <h1>Settings</h1>
            {inApp && <label className="setting"><input type="checkbox" className="tick square" checked={onTop} onChange={(e) => window.sm!.win.setOnTop(e.target.checked).then(setOnTop)} /> Keep this window above all programs, not only 3ds Max</label>}
            {inApp && <label className="setting"><input type="checkbox" className="tick square" checked={wnd.attach} onChange={(e) => window.sm!.win.setAttach(e.target.checked)} /> Follow 3ds Max (stay above it, step behind other programs, hide while Max is minimized)
              {wnd.attach && !wnd.owned && online && <span className="muted"> · not following, see docs/app.md</span>}</label>}
            <p className="muted">Card places, sizes and colours are saved per user. Use a card's gear menu, or reset them all here.</p>
            <div><button className="btn" onClick={() => { setPrefs({}); setOrder([]); flash("Card layout reset."); }}>Reset card layout</button></div>
          </section>
        )}
        <Chat open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>

      <footer className="status">
        <span className="grow ellipsis">{busy || message || state?.notice || (online && state ? `${active ? pathOf(active.id) : "No active setup"}   ·   ${state.renderer}${state.baseline ? "   ·   baseline" : ""}` : "")}</span>
        <span className={"conn" + (online ? " on" : "")}>{online ? "● Connected to 3ds Max" : "○ Waiting for 3ds Max"}</span>
      </footer>

      {palette && schema && detail && <Palette schema={schema} detail={detail} category={category} onClose={() => setPalette(false)}
        onAdd={(module) => { setPalette(false); run("ui_add_module", { id: detail.id, module }).catch(() => {}); }} />}
      {menu && <Menu menu={menu} onClose={() => setMenu(null)} />}
      {busy && <div className="veil" />}
    </div>
    </LibraryCtx.Provider>
  );
}

function Inline({ value, onCommit, className, placeholder }: { value: string; onCommit: (v: string) => void; className: string; placeholder?: string }) {
  const [text, setText] = useState(value);
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setText(value); }, [value]);
  return <input className={"inline " + className} value={text} placeholder={placeholder} spellCheck={false}
    onFocus={() => { focused.current = true; }} onChange={(e) => setText(e.target.value)}
    onBlur={() => { focused.current = false; if (text.trim() !== value) onCommit(text.trim()); }}
    onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") { setText(value); focused.current = false; e.currentTarget.blur(); } }} />;
}

function Palette({ schema, detail, category, onAdd, onClose }: { schema: Schema; detail: Detail; category: string | null; onAdd: (key: string) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const down = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node) && !(e.target as HTMLElement).closest(".rail .add")) onClose(); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("mousedown", down); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("mousedown", down); window.removeEventListener("keydown", key); };
  }, [onClose]);
  const on = new Set(detail.cards.map((c) => c.key));
  return (
    <div ref={ref} className="palette">
      <h1>Add module</h1>
      {schema.groups.filter((g) => !category || g.key === category).map((g) => {
        const mods = schema.modules.filter((m) => m.group === g.key && (m.installed !== false || on.has(m.key)));
        return mods.length === 0 ? null : (
          <div key={g.key}>
            <h3><Icon name={g.icon} size={14} color={g.tint} /> {g.label}</h3>
            <div className="tiles">{mods.map((m) => (
              <button key={m.key} disabled={on.has(m.key)} className={m.available ? "" : "dim"} onClick={() => onAdd(m.key)}
                title={on.has(m.key) ? `Already on this ${detail.type}` : m.available ? `Add ${m.label}, filled from the scene` : `Add ${m.label}. Not part of a new setup in this scene (other renderer, or nothing for it to control yet).`}>
                <Icon name={g.icon} size={15} color={on.has(m.key) ? undefined : g.tint} /><span>{m.label}</span>{on.has(m.key) && <em>✓</em>}
              </button>))}</div>
          </div>);
      })}
    </div>
  );
}
