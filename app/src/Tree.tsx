import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./icons";
import type { Item, State } from "./types";

interface Props {
  state: State; selected: string | null; checked: Set<string>; folded: Set<string>;
  search: string; tags: Set<string>; renaming: string | null; columns: string[];
  onSelect: (id: string) => void; onActivate: (id: string) => void; onToggleFold: (id: string) => void;
  onCheck: (ids: string[], on: boolean) => void; onRename: (id: string, name: string | null) => void;
  onMenu: (id: string | null, x: number, y: number) => void; onMove: (id: string, parent: string | null, index?: number) => void;
}

export function visibleRows(state: State, folded: Set<string>, search: string, tags: Set<string>) {
  const kids = new Map<string | null, Item[]>();
  for (const it of state.items) kids.set(it.parent, [...(kids.get(it.parent) || []), it]);
  const text = search.trim().toLowerCase();
  const filtering = !!text || tags.size > 0;
  const match = (it: Item): boolean => {
    if (it.type === "folder") return (kids.get(it.id) || []).some(match) || (!tags.size && !!text && it.name.toLowerCase().includes(text));
    return (!text || it.name.toLowerCase().includes(text)) && (!tags.size || it.tags.some((t) => tags.has(t)));
  };
  const out: { item: Item; depth: number; count: number }[] = [];
  const count = (id: string): number => (kids.get(id) || []).reduce((n, c) => n + (c.type === "setup" ? 1 : count(c.id)), 0);
  const walk = (parent: string | null, depth: number) => {
    for (const it of kids.get(parent) || []) {
      if (filtering && !match(it)) continue;
      out.push({ item: it, depth, count: it.type === "folder" ? count(it.id) : 0 });
      if (it.type === "folder" && (filtering || !folded.has(it.id))) walk(it.id, depth + 1);
    }
  };
  walk(null, 0);
  return { rows: out, kids };
}

export function Tree(p: Props) {
  const { rows, kids } = useMemo(() => visibleRows(p.state, p.folded, p.search, p.tags), [p.state, p.folded, p.search, p.tags]);
  const [drop, setDrop] = useState<{ id: string; where: "in" | "before" } | null>(null);
  const drag = useRef<string | null>(null);
  const sel = useRef<HTMLDivElement>(null);
  useEffect(() => { sel.current?.scrollIntoView({ block: "nearest" }); }, [p.selected]);
  const cols = p.state.columns.filter((c) => p.columns.includes(c.key));

  const setupsIn = (id: string): string[] => (kids.get(id) || []).flatMap((c) => (c.type === "setup" ? [c.id] : setupsIn(c.id)));

  return (
    <div className="tree" onContextMenu={(e) => { e.preventDefault(); p.onMenu(null, e.clientX, e.clientY); }}>
      <div className="tree-head"><span className="grow">Setup</span>{cols.map((c) => <span key={c.key} className="col">{c.label}</span>)}</div>
      {rows.map(({ item, depth, count }) => {
        const active = item.id === p.state.active;
        const folder = item.type === "folder";
        const inside = folder ? setupsIn(item.id) : [];
        const on = folder ? inside.length > 0 && inside.every((i) => p.checked.has(i)) : p.checked.has(item.id);
        const cls = "tree-row" + (item.id === p.selected ? " selected" : "") + (active ? " active" : "")
          + (drop?.id === item.id ? " drop-" + drop.where : "");
        return (
          <div key={item.id} ref={item.id === p.selected ? sel : undefined} className={cls} style={{ paddingLeft: 6 + depth * 16 }}
            draggable={p.renaming !== item.id}
            onDragStart={(e) => { drag.current = item.id; e.dataTransfer.effectAllowed = "move"; }}
            onDragOver={(e) => {
              if (!drag.current || drag.current === item.id) return;
              e.preventDefault();
              const r = e.currentTarget.getBoundingClientRect();
              setDrop({ id: item.id, where: folder && e.clientY > r.top + r.height * 0.3 ? "in" : "before" });
            }}
            onDragLeave={() => setDrop(null)}
            onDrop={(e) => {
              e.preventDefault();
              const id = drag.current; drag.current = null;
              const d = drop; setDrop(null);
              if (!id || !d) return;
              if (d.where === "in") p.onMove(id, item.id);
              else p.onMove(id, item.parent, (kids.get(item.parent) || []).filter((x) => x.id !== id).findIndex((x) => x.id === item.id));
            }}
            onClick={() => p.onSelect(item.id)}
            onDoubleClick={(e) => { if (!(e.target as HTMLElement).closest("input,button")) folder ? p.onToggleFold(item.id) : p.onActivate(item.id); }}
            onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); p.onSelect(item.id); p.onMenu(item.id, e.clientX, e.clientY); }}>
            {folder
              ? <button className={"chev" + (p.folded.has(item.id) ? "" : " open")} onClick={(e) => { e.stopPropagation(); p.onToggleFold(item.id); }}><Icon name="chevron" size={12} /></button>
              : <span className="chev" />}
            <input type="checkbox" className="tick square" checked={on} title="Queue for rendering"
              onClick={(e) => e.stopPropagation()} onChange={(e) => p.onCheck(folder ? inside : [item.id], e.target.checked)} />
            {folder
              ? <Icon name="folder" size={16} color={item.color || undefined} />
              : <span className="marker"><i className="bar" style={{ background: item.color || "transparent" }} /><i className={"state" + (active ? " on" : "")} /></span>}
            {p.renaming === item.id
              ? <input className="rename" autoFocus defaultValue={item.name} onFocus={(e) => e.currentTarget.select()}
                  onClick={(e) => e.stopPropagation()}
                  onBlur={(e) => p.onRename(item.id, e.target.value.trim() || null)}
                  onKeyDown={(e) => { e.stopPropagation(); if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") p.onRename(item.id, null); }} />
              : <span className="name" title={item.description || item.name}>{item.name}</span>}
            {folder ? <span className="col count">{count}</span>
              : cols.map((c) => <span key={c.key} className="col" title={item.summary?.[c.key]}>{item.summary?.[c.key]}</span>)}
          </div>
        );
      })}
      {rows.length === 0 && <p className="muted pad">{p.state.items.length ? "Nothing matches." : "No setups yet. Set up the scene and press New Setup."}</p>}
    </div>
  );
}
