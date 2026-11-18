import { useEffect, useRef, useState } from "react";
import type { PropSchema, Row } from "./types";

export function Switch({ on, onChange, tint, disabled, title }: { on: boolean; onChange: (v: boolean) => void; tint?: string; disabled?: boolean; title?: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} title={title} disabled={disabled}
      className={"switch" + (on ? " on" : "")} style={on && tint ? { background: tint } : undefined}
      onClick={() => onChange(!on)}><i /></button>
  );
}

/** Text box that keeps what is being typed until Enter or blur; values from 3ds Max only replace it when it is not in use. */
function Draft({ value, onCommit, disabled, className, align, suffix, parse, title, placeholder, stepKeys }: {
  value: string; onCommit: (text: string) => void; disabled?: boolean; className?: string; align?: "right";
  suffix?: string; parse?: (t: string) => string | null; title?: string; placeholder?: string;
  stepKeys?: (dir: 1 | -1, text: string) => string;
}) {
  const [text, setText] = useState(value);
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setText(value); }, [value]);
  const commit = (t: string) => {
    const clean = parse ? parse(t) : t;
    if (clean === null) { setText(value); return; }
    setText(clean);
    if (clean !== value) onCommit(clean);
  };
  return (
    <span className={"input" + (disabled ? " disabled" : "") + (className ? " " + className : "")}>
      <input value={text} disabled={disabled} title={title} placeholder={placeholder} spellCheck={false}
        style={align ? { textAlign: align } : undefined}
        onFocus={(e) => { focused.current = true; e.currentTarget.select(); }}
        onChange={(e) => setText(e.target.value)}
        onBlur={(e) => { focused.current = false; commit(e.target.value); }}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit(e.currentTarget.value);
          else if (e.key === "Escape") { setText(value); e.currentTarget.blur(); }
          else if (stepKeys && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
            e.preventDefault();
            commit(stepKeys(e.key === "ArrowUp" ? 1 : -1, e.currentTarget.value));
          }
        }} />
      {suffix && <em>{suffix.trim()}</em>}
    </span>
  );
}

function fmt(v: any, p: PropSchema) {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return p.kind === "int" ? String(Math.round(n)) : n.toFixed(Math.min(p.decimals ?? 2, 6));
}

function NumberField({ p, value, onChange, disabled }: { p: PropSchema; value: any; onChange: (v: number) => void; disabled?: boolean }) {
  const clamp = (n: number) => Math.min(p.max ?? 1e9, Math.max(p.min ?? -1e9, n));
  const parse = (t: string) => {
    const n = Number(t.replace(",", ".").replace(/[^0-9eE+\-.]/g, ""));
    return t.trim() === "" || Number.isNaN(n) ? null : fmt(clamp(n), p);
  };
  return <Draft value={fmt(value, p)} disabled={disabled} suffix={p.suffix} parse={parse} title={p.tip}
    onCommit={(t) => onChange(Number(t))}
    stepKeys={(dir, t) => fmt(clamp((Number(t.replace(",", ".")) || 0) + dir * (p.kind === "int" ? 1 : p.step || 1)), p)} />;
}

function Select({ value, options, onChange, disabled, title }: { value: string; options: string[]; onChange: (v: string) => void; disabled?: boolean; title?: string }) {
  const opts = options.includes(value) || value === "" ? options : [value, ...options];
  return (
    <span className={"input select" + (disabled ? " disabled" : "")}>
      <select value={value} disabled={disabled} title={title} onChange={(e) => onChange(e.target.value)}>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </span>
  );
}

const TRI: [any, string, string, string][] = [[null, "·", "tri none", "Leave alone"], [true, "✓", "tri yes", "On"], [false, "✕", "tri no", "Off"]];

function Cell({ c, v, onChange }: { c: PropSchema; v: any; onChange: (v: any) => void }) {
  if (c.kind === "tristate") {
    const i = Math.max(0, TRI.findIndex((t) => t[0] === (v ?? null)));
    return <button className={TRI[i][2]} title={TRI[i][3] + " (click to change)"} onClick={() => onChange(TRI[(i + 1) % 3][0])}>{TRI[i][1]}</button>;
  }
  if (v === null || v === undefined) return <span className="na" title="Not available here">–</span>;
  if (c.kind === "bool") return <input type="checkbox" className="tick square" checked={!!v} onChange={(e) => onChange(e.target.checked)} />;
  if (c.kind === "float" || c.kind === "int") return <NumberField p={c} value={v} onChange={onChange} />;
  if (c.kind === "enum") return <Select value={String(v)} options={c.options} onChange={onChange} />;
  if (c.kind === "color" && Array.isArray(v)) {
    const hex = "#" + v.slice(0, 3).map((x: number) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, "0")).join("");
    return <input type="color" className="swatch" value={hex}
      onChange={(e) => onChange([1, 3, 5].map((i) => parseInt(e.target.value.slice(i, i + 2), 16)))} />;
  }
  return <span className="na">{String(v)}</span>;
}

/** Rows of scene things (lights, layers, object rules). A ticked row is stored here; the rest follow the folder or the scene. */
function Table({ p, row, onChange }: { p: PropSchema; row: Row; onChange: (v: any) => void }) {
  const own: Record<string, any> = row.own_value || {};
  const merged: Record<string, any> = {};
  for (const src of [row.scene, row.effective, own]) for (const [k, v] of Object.entries(src || {})) merged[k] = { ...(merged[k] || {}), ...(v as object) };
  const names = Object.keys(merged);
  const [filter, setFilter] = useState("");
  const [add, setAdd] = useState("");
  const cols = p.columns || [];
  const shown = names.filter((n) => !filter || n.toLowerCase().includes(filter.toLowerCase()));
  const setRow = (name: string, value: any | undefined) => {
    const next = { ...own };
    if (value === undefined) delete next[name]; else next[name] = value;
    onChange(next);
  };
  return (
    <div className="table">
      {names.length > 8 && <span className="input"><input placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} /></span>}
      <div className="table-scroll">
        <table>
          <thead><tr><th /><th className="name">Name</th>{cols.map((c) => <th key={c.key} title={c.tip}>{c.label}</th>)}</tr></thead>
          <tbody>
            {shown.map((name) => (
              <tr key={name} className={name in own ? "own" : ""}>
                <td><input type="checkbox" className="tick" checked={name in own} title="Store this row here"
                  onChange={(e) => setRow(name, e.target.checked ? merged[name] : undefined)} /></td>
                <td className="name" title={name}>{name}</td>
                {cols.map((c) => <td key={c.key}><Cell c={c} v={merged[name][c.key]} onChange={(v) => setRow(name, { ...merged[name], [c.key]: v })} /></td>)}
              </tr>))}
            {!shown.length && <tr><td colSpan={cols.length + 2} className="empty">Nothing in the scene yet</td></tr>}
          </tbody>
        </table>
      </div>
      {p.options.length > 0 && (
        <form className="table-add" onSubmit={(e) => { e.preventDefault(); const t = add.trim(); if (t && !(t in merged)) setRow(t, {}); setAdd(""); }}>
          <span className="input"><input list={"opts-" + p.key} value={add} placeholder="set:Name, layer:Name, pattern:Tree_*" onChange={(e) => setAdd(e.target.value)} /></span>
          <datalist id={"opts-" + p.key}>{p.options.map((o) => <option key={o} value={o} />)}</datalist>
          <button className="btn small">Add</button>
        </form>)}
    </div>
  );
}

function Todo({ value, onChange }: { value: any; onChange: (v: any) => void }) {
  const items: { text: string; done: boolean }[] = Array.isArray(value) ? value : [];
  const [text, setText] = useState("");
  return (
    <div className="todo">
      {items.map((it, i) => (
        <label key={i} className={it.done ? "done" : ""}>
          <input type="checkbox" className="tick square" checked={it.done} onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, done: e.target.checked } : x)))} />
          <span>{it.text}</span>
          <button className="x" title="Remove" onClick={(e) => { e.preventDefault(); onChange(items.filter((_, j) => j !== i)); }}>×</button>
        </label>))}
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) onChange([...items, { text: text.trim(), done: false }]); setText(""); }}>
        <span className="input"><input value={text} placeholder="Add a to-do, press Enter" onChange={(e) => setText(e.target.value)} /></span>
      </form>
    </div>
  );
}

function Note({ value, onChange }: { value: any; onChange: (v: string) => void }) {
  const [text, setText] = useState(String(value ?? ""));
  const focused = useRef(false);
  useEffect(() => { if (!focused.current) setText(String(value ?? "")); }, [value]);
  return <textarea className="note" value={text} rows={3} placeholder="Notes" onFocus={() => { focused.current = true; }}
    onChange={(e) => setText(e.target.value)} onBlur={() => { focused.current = false; if (text !== String(value ?? "")) onChange(text); }} />;
}

export const WIDE = new Set(["table", "note", "todo", "checklist", "toggles", "lmgroups", "cprops"]);
/** Kinds that can be edited before they are stored on the item (the first edit stores them). */
export const ALWAYS = new Set(["table", "note", "todo"]);

export function Field({ p, row, nodes, disabled, onChange }: { p: PropSchema; row: Row; nodes: Record<string, string[]>; disabled: boolean; onChange: (v: any) => void }) {
  const v = row.value;
  switch (p.kind) {
    case "int": case "float": return <NumberField p={p} value={v} onChange={onChange} disabled={disabled} />;
    case "bool": return <span className="field-switch"><Switch on={!!v} onChange={onChange} disabled={disabled} title={p.tip} /></span>;
    case "enum": return <Select value={v == null ? "" : String(v)} options={p.options} onChange={onChange} disabled={disabled} title={p.tip} />;
    case "camera": case "sunlight": case "light":
      return <Select value={v?.name ?? "(none)"} options={["(none)", ...(nodes[p.kind] || [])]} onChange={onChange} disabled={disabled} title={p.tip} />;
    case "table": return <Table p={p} row={row} onChange={onChange} />;
    case "todo": return <Todo value={v} onChange={onChange} />;
    case "note": return <Note value={v} onChange={onChange} />;
    case "checklist": {
      const scene = row.scene || {}, val = v && typeof v === "object" ? v : {};
      const names = [...Object.keys(scene), ...Object.keys(val).filter((n) => !(n in scene))];
      return <div className="checklist">{names.length === 0 && <span className="muted">(none in the scene)</span>}
        {names.map((n) => <label key={n}><Switch on={!!(val[n] ?? scene[n])} disabled={disabled}
          onChange={(on) => onChange({ ...Object.fromEntries(names.map((k) => [k, !!(val[k] ?? scene[k])])), [n]: on })} /><span>{n}</span></label>)}</div>;
    }
    case "text": case "path": case "hdri": case "image": case "rps":
      return <Draft value={v == null ? "" : String(v)} disabled={disabled} onCommit={onChange} title={p.tip || String(v ?? "")} />;
    default: {  // kinds with their own editor in the Qt panel; shown read-only until they are ported
      const n = v && typeof v === "object" ? Object.keys(v).length : 0;
      return <span className="muted" title="Edit this one in the 3ds Max panel for now">{v == null ? "–" : typeof v === "object" ? n + (n === 1 ? " entry" : " entries") : String(v)}</span>;
    }
  }
}
