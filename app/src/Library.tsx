// Environment library: browse the HDRI / environment folders Scene Manager already knows (favourites in
// ~/.scene_manager/hdri.json, the team folder under the presets folder, recent picks) as thumbnails, and click
// one to put it into the selected setup's Environment, Dome light, GI or Reflection slot.
import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { call, inApp, store } from "./api";
import { Icon } from "./icons";
import type { MenuItem, MenuState } from "./Menu";
import { baseName, useThumb } from "./thumbs";
import type { Detail } from "./types";

export interface Target { key: string; label: string; module: string; prop: string; available: boolean; why: string }
interface Root { path: string; label: string; kind: string; exists: boolean }
interface Dir { name: string; path: string; has_dirs: boolean }
interface Asset { path: string; name: string; ext: string; size: number; folder: string }
interface Listing { folder: string; dirs: Dir[]; files: Asset[]; missing: boolean; truncated: boolean }

/** Opens the library aimed at one slot (cards' HDRI fields use this). */
export const LibraryCtx = createContext<(target: string) => void>(() => {});
/** Which library slot a card field feeds. */
export const TARGET_OF: Record<string, string> = { "environment.hdri": "environment", "dome.hdri": "dome", "env_override.gi_hdri": "gi", "env_override.refl_hdri": "refl" };
const SHORT: Record<string, string> = { environment: "Env", dome: "Dome", gi: "GI", refl: "Refl" };
const RECENT = "recent";
const same = (a?: string | null, b?: string | null) => !!a && !!b && a.replace(/\\/g, "/").toLowerCase() === b.replace(/\\/g, "/").toLowerCase();

/** Path each slot uses on this setup now (stored, inherited, or the scene's). */
function currentPaths(detail: Detail, targets: Target[]) {
  const out: Record<string, string> = {};
  for (const t of targets) {
    const card = detail.cards.find((c) => c.key === t.module);
    const row = card?.rows.find((r) => r.key === t.prop);
    const mode = card?.rows.find((r) => r.key === "mode")?.value;
    const on = t.key === "gi" ? card?.rows.find((r) => r.key === "gi_on")?.value : t.key === "refl" ? card?.rows.find((r) => r.key === "refl_on")?.value : true;
    if (row?.value && on !== false && (t.key !== "environment" || mode === "hdri")) out[t.key] = String(row.value);
  }
  return out;
}

export function Library({ detail, target, setTarget, onClose, flash, openMenu }: {
  detail: Detail; target: string; setTarget: (t: string) => void; onClose: () => void;
  flash: (text: string) => void; openMenu: (m: MenuState) => void;
}) {
  const [roots, setRoots] = useState<Root[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [folder, setFolder] = useState<string>("");
  const [listing, setListing] = useState<Listing | null>(null);
  const [kids, setKids] = useState<Record<string, Dir[]>>({});
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [images, setImages] = useState(false);
  const [size, setSize] = useState(180);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  const loadRoots = useCallback(async () => {
    const r = await call("lib_roots");
    setRoots(r.roots); setTargets(r.targets);
    return r as { roots: Root[]; recent: string[] };
  }, []);

  useEffect(() => {   // first open: last folder, else the first library folder, else Recent
    Promise.all([loadRoots(), store.get("library", {} as any)]).then(([r, saved]) => {
      setImages(!!saved.images); if (saved.size) setSize(saved.size);
      if (saved.open) setOpen(new Set(saved.open));
      setFolder(saved.folder && (saved.folder === RECENT || r.roots.some((x) => saved.folder.toLowerCase().startsWith(x.path.toLowerCase()))) ? saved.folder
        : r.roots[0]?.path || RECENT);
    }).catch((e) => flash(String(e.message || e)));
  }, [loadRoots, flash]);

  useEffect(() => { if (folder) store.set("library", { folder, images, size, open: [...open] }); }, [folder, images, size, open]);

  useEffect(() => {   // listing of the folder shown (debounced while typing a search)
    if (!folder) return;
    let alive = true;
    const t = window.setTimeout(() => {
      setLoading(true);
      call<Listing>("lib_list", { folder, search, images }).then((l) => {
        if (!alive) return;
        setListing(l);
        if (!search) setKids((k) => ({ ...k, [folder]: l.dirs }));
      }).catch((e) => alive && flash(String(e.message || e))).finally(() => alive && setLoading(false));
    }, search ? 250 : 0);
    return () => { alive = false; window.clearTimeout(t); };
  }, [folder, search, images, flash]);

  const toggle = (p: string) => {
    const next = new Set(open);
    if (next.has(p)) next.delete(p);
    else {
      next.add(p);
      if (!kids[p]) call<Listing>("lib_list", { folder: p }).then((l) => setKids((k) => ({ ...k, [p]: l.dirs }))).catch(() => {});
    }
    setOpen(next);
  };
  const go = (p: string) => {   // open a folder, unfolding the tree down to it
    setSearch("");
    setFolder(p);
    const root = roots.find((r) => p.toLowerCase().startsWith(r.path.toLowerCase()));
    if (root && p !== root.path) {
      const next = new Set(open);
      let cur = p;
      while (cur.length > root.path.length) { cur = cur.replace(/[\\/][^\\/]*$/, ""); next.add(cur); }
      next.forEach((d) => { if (!kids[d]) call<Listing>("lib_list", { folder: d }).then((l) => setKids((k) => ({ ...k, [d]: l.dirs }))).catch(() => {}); });
      setOpen(next);
    }
  };

  const addFolder = async () => {
    const p = inApp ? await window.sm!.pickFolder("Add a folder to the environment library") : window.prompt("Folder path to add to the library") || "";
    if (!p) return;
    try { await call("lib_add_folder", { path: p }); await loadRoots(); go(p); }
    catch (e: any) { flash(String(e.message || e)); }
  };
  const removeFolder = async (p: string) => {
    await call("lib_remove_folder", { path: p }).catch(() => {});
    const r = await loadRoots();
    if (folder.toLowerCase().startsWith(p.toLowerCase())) setFolder(r.roots[0]?.path || RECENT);
  };

  const cur = useMemo(() => currentPaths(detail, targets), [detail, targets]);
  const tgt = targets.find((t) => t.key === target);

  const apply = async (path: string, to = target) => {
    const t = targets.find((x) => x.key === to);
    if (!t) return;
    if (!t.available) { flash(t.why); return; }
    setBusy(path);
    try {
      const r = await call("lib_apply", { id: detail.id, target: to, path });
      const where = `${t.label} of ${detail.name}`;
      flash(r.errors?.length ? `Stored in ${where}, with errors: ${r.errors.join("; ")}`
        : `${baseName(path)} → ${where}${r.created ? ` (created ${r.created})` : ""}${r.active ? "" : " · activate the setup to see it"}`);
    } catch (e: any) { flash(String(e.message || e)); }
    finally { setBusy(null); }
  };

  const assetMenu = (a: Asset, x: number, y: number) => {
    const items: MenuItem[] = [
      ...targets.map((t) => ({ label: `Use as ${t.label}`, disabled: !t.available, hint: same(cur[t.key], a.path) ? "in use" : undefined, onClick: () => apply(a.path, t.key) })),
      { sep: true },
      ...(a.folder && search ? [{ label: "Open its folder", onClick: () => go(a.path.replace(/[\\/][^\\/]*$/, "")) }] : []),
      ...(inApp ? [{ label: "Show in Explorer", onClick: () => window.sm!.reveal(a.path) }] : []),
      { label: "Copy path", onClick: () => navigator.clipboard?.writeText(a.path) },
    ];
    openMenu({ x, y, items });
  };

  const crumbs = useMemo(() => {
    if (folder === RECENT) return [{ label: "Recent", path: RECENT }];
    const root = roots.find((r) => folder.toLowerCase().startsWith(r.path.toLowerCase()));
    if (!root) return [{ label: folder, path: folder }];
    const out = [{ label: root.label, path: root.path }];
    let acc = root.path;
    for (const part of folder.slice(root.path.length).split(/[\\/]/).filter(Boolean)) {
      acc += (acc.includes("\\") ? "\\" : "/") + part;
      out.push({ label: part, path: acc });
    }
    return out;
  }, [folder, roots]);

  const tree = (dirs: Dir[], depth: number): JSX.Element[] => dirs.flatMap((d) => [
    <div key={d.path} className={"lib-node" + (folder === d.path ? " on" : "")} style={{ paddingLeft: 6 + depth * 14 }} onClick={() => go(d.path)} title={d.path}>
      <button className={"chev" + (open.has(d.path) ? " open" : "")} style={{ visibility: d.has_dirs ? "visible" : "hidden" }}
        onClick={(e) => { e.stopPropagation(); toggle(d.path); }}><Icon name="chevron" size={12} /></button>
      <Icon name="folder" size={15} /><span className="ellipsis">{d.name}</span>
    </div>,
    ...(open.has(d.path) && kids[d.path] ? tree(kids[d.path], depth + 1) : []),
  ]);

  const files = listing?.files || [];
  const subdirs = !search ? listing?.dirs || [] : [];
  return (
    <section className="library" onKeyDown={(e) => { if (e.key === "Escape" && !(e.target as HTMLElement).closest("input")) onClose(); }}>
      <div className="lib-head">
        <div className="lib-title">
          <h1>Environment library</h1>
          <span className="muted ellipsis">for <b>{detail.name}</b>{detail.active ? " · active, changes show at once" : " · stored on the setup"}</span>
        </div>
        <span className="grow" />
        <div className="seg" role="tablist" title="Where a click puts the file">
          {targets.map((t) => <button key={t.key} className={target === t.key ? "on" : ""} disabled={!t.available} title={t.why || `Click a thumbnail to use it as ${t.label}`}
            onClick={() => setTarget(t.key)}>{t.label}</button>)}
        </div>
        <button className="icon-btn" title="Close (Esc)" onClick={onClose}><Icon name="close" size={16} /></button>
      </div>
      <div className="lib-tools">
        <label className="search"><Icon name="search" size={15} />
          <input value={search} placeholder={folder === RECENT ? "Search recent" : "Search this folder and below"} onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") { setSearch(""); e.currentTarget.blur(); } }} /></label>
        <label className="lib-check" title="Also list LDR images (jpg, png, tif) that are not previews of an HDRI">
          <input type="checkbox" className="tick square" checked={images} onChange={(e) => setImages(e.target.checked)} /> Images too</label>
        <input type="range" min={110} max={320} value={size} title="Thumbnail size" onChange={(e) => setSize(Number(e.target.value))} />
      </div>
      <div className="lib-body">
        <aside className="lib-tree">
          <div className={"lib-node" + (folder === RECENT ? " on" : "")} onClick={() => go(RECENT)}><span className="chev" /><Icon name="clock" size={15} /><span>Recent</span></div>
          <h3>Library</h3>
          {roots.map((r) => [
            <div key={r.path} className={"lib-node root" + (folder === r.path ? " on" : "") + (r.exists ? "" : " missing")} onClick={() => r.exists && go(r.path)} title={r.exists ? r.path : r.path + " (not found)"}
              onContextMenu={(e) => { e.preventDefault(); openMenu({ x: e.clientX, y: e.clientY, items: [
                ...(inApp ? [{ label: "Show in Explorer", onClick: () => window.sm!.reveal(r.path) }] : []),
                r.kind === "team" ? { label: "Team folder (from the presets folder)", disabled: true, onClick: () => {} } : { label: "Remove from library", danger: true, onClick: () => removeFolder(r.path) }] }); }}>
              <button className={"chev" + (open.has(r.path) ? " open" : "")} onClick={(e) => { e.stopPropagation(); toggle(r.path); }}><Icon name="chevron" size={12} /></button>
              <Icon name={r.kind === "team" ? "team" : "library"} size={15} /><span className="ellipsis">{r.label}</span>
            </div>,
            ...(open.has(r.path) && kids[r.path] ? tree(kids[r.path], 1) : [])])}
          {!roots.length && <p className="muted small">No folders yet. Add the folder that holds your HDRIs.</p>}
          <button className="btn small add-folder" onClick={addFolder}><Icon name="plus" size={13} /> Add folder</button>
        </aside>
        <div className="lib-main">
          <div className="crumbs">
            {crumbs.map((c, i) => <span key={c.path}>{i > 0 && <i>/</i>}<button onClick={() => go(c.path)} disabled={i === crumbs.length - 1}>{c.label}</button></span>)}
            <span className="grow" />
            <span className="muted">{loading ? "Loading…" : `${files.length}${listing?.truncated ? "+" : ""} item${files.length === 1 ? "" : "s"}`}</span>
          </div>
          <div ref={gridRef} className="lib-grid" style={{ ["--tile" as any]: size + "px" }}>
            {subdirs.map((d) => (
              <button key={d.path} className="lib-folder" onClick={() => go(d.path)} title={d.path}><Icon name="folder" size={22} /><span className="ellipsis">{d.name}</span></button>))}
            {files.map((a) => (
              <Tile key={a.path} a={a} root={gridRef} busy={busy === a.path} uses={targets.filter((t) => same(cur[t.key], a.path)).map((t) => t.key)}
                target={target} onApply={() => apply(a.path)} onMenu={(x, y) => assetMenu(a, x, y)} search={!!search} />))}
            {listing && !loading && !files.length && !subdirs.length && <p className="muted pad">
              {listing.missing ? "This folder is not reachable (network drive offline?)." : search ? "Nothing matches." : folder === RECENT ? "Nothing picked yet." : "No HDRIs in this folder."}</p>}
          </div>
          <div className="lib-foot muted">
            {tgt && !tgt.available ? tgt.why : <>Click a thumbnail to use it as <b>{tgt?.label || "…"}</b>. Right-click for other slots, Explorer, path.
              {cur[target] && <> In use now: <b>{baseName(cur[target])}</b></>}</>}
          </div>
        </div>
      </div>
    </section>
  );
}

function Tile({ a, root, busy, uses, target, onApply, onMenu, search }: {
  a: Asset; root: React.RefObject<HTMLDivElement>; busy: boolean; uses: string[]; target: string;
  onApply: () => void; onMenu: (x: number, y: number) => void; search: boolean;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {   // ask for the thumbnail only once the tile scrolls into view
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { setSeen(true); io.disconnect(); } }, { root: root.current, rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, [root, seen]);
  const thumb = useThumb(a.path, seen);
  const mb = a.size > 1 << 20 ? (a.size / (1 << 20)).toFixed(a.size > 100 << 20 ? 0 : 1) + " MB" : Math.max(1, Math.round(a.size / 1024)) + " KB";
  return (
    <button ref={ref} className={"lib-tile" + (uses.includes(target) ? " current" : "") + (busy ? " busy" : "")} title={`${a.path}\n${mb}`}
      onClick={onApply} onContextMenu={(e) => { e.preventDefault(); onMenu(e.clientX, e.clientY); }}>
      <div className="lib-img">
        {thumb ? <img src={thumb} alt="" draggable={false} /> : <span className={thumb === null ? "none" : "wait"}>{thumb === null ? a.ext.toUpperCase() : ""}</span>}
        <em className="ext">{a.ext}</em>
        {uses.length > 0 && <span className="uses">{uses.map((u) => <b key={u} className={u === target ? "on" : ""}>{SHORT[u]}</b>)}</span>}
      </div>
      <span className="lib-name ellipsis">{a.name}</span>
      {search && a.folder && <span className="lib-sub ellipsis">{a.folder}</span>}
    </button>
  );
}

/** Small preview + library button for an HDRI field on a card. */
export function HdriThumb({ path }: { path: string }) {
  const t = useThumb(path || null);
  return <span className="hdri-mini">{t ? <img src={t} alt="" /> : <Icon name="photo" size={12} />}</span>;
}
