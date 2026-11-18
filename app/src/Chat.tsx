import { useEffect, useRef, useState } from "react";
import { inApp, onEvent } from "./api";
import { Icon } from "./icons";

// Claude in the app. The work happens in electron/chat.cjs (the user's own Claude Code, only the 3ds Max tools);
// this is the conversation: what was asked, what Claude said, each tool step, and a question before anything
// that deletes or renders.
type Step = { id: string; name: string; input: any; state: "run" | "ok" | "error"; note?: string };
type Part = { text: string } | { step: Step };
interface Msg { who: "you" | "claude" | "note"; parts: Part[]; denied?: { name: string; input: any }[]; signIn?: boolean; install?: boolean }

const VERBS: Record<string, string> = {
  scene_info: "Read the scene", list_setups: "Listed the setups", get_setup: "Read setup", apply_setup: "Activated setup",
  capture_setup: "Saved setup", create_folder: "Created folder", move_item: "Moved", set_module_values: "Changed setup",
  delete_setup: "Delete", render_setups: "Render", set_sun: "Set the sun", set_sun_direction: "Set the sun direction",
  set_environment: "Set the environment", set_dome: "Set the dome light", set_lights: "Changed lights", set_layers: "Changed layers",
  inspect_node: "Inspected", run_python: "Run Python in 3ds Max", run_maxscript: "Run MAXScript in 3ds Max", create_sun: "Create a sun",
  render_info: "Read the render settings", set_render_props: "Changed render settings", capture_baseline: "Saved the scene baseline",
};
/** "set_sun" + {elevation: 12} -> "Set the sun · elevation 12" */
export function describe(name: string, input: any): string {
  const verb = VERBS[name] || name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const main = input?.name ?? input?.setup ?? input?.names ?? input?.folder ?? input?.sun_name;
  const head = main !== undefined ? ` “${Array.isArray(main) ? main.join(", ") : main}”` : "";
  const rest = Object.entries(input || {}).filter(([k, v]) => !["name", "setup", "names", "sun_name", "code"].includes(k) && v !== null && typeof v !== "object")
    .slice(0, 4).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ");
  return verb + head + (rest ? " · " + rest : "");
}

/** Just enough formatting for short answers: **bold**, `code`, line breaks. */
function Rich({ text }: { text: string }) {
  const bits = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return <>{bits.map((b, i) => b.startsWith("**") && b.endsWith("**") && b.length > 4 ? <b key={i}>{b.slice(2, -2)}</b>
    : b.startsWith("`") && b.endsWith("`") && b.length > 2 ? <code key={i}>{b.slice(1, -1)}</code> : <span key={i}>{b}</span>)}</>;
}

export function Chat({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  // the answer being written is always the last message
  const patch = (fn: (m: Msg) => Msg) => setMsgs((all) => {
    const last = all[all.length - 1];
    return last && last.who === "claude" ? [...all.slice(0, -1), fn(last)] : [...all, fn({ who: "claude", parts: [] })];
  });

  useEffect(() => onEvent((ev) => {
    if (ev.event !== "chat") return;
    if (ev.kind === "text") patch((m) => {
      const parts = [...m.parts], last = parts[parts.length - 1];
      if (last && "text" in last) parts[parts.length - 1] = { text: last.text + ev.text }; else parts.push({ text: ev.text });
      return { ...m, parts };
    });
    else if (ev.kind === "tool") patch((m) => m.parts.some((p) => "step" in p && p.step.id === ev.id) ? m
      : { ...m, parts: [...m.parts, { step: { id: ev.id, name: ev.name, input: ev.input, state: "run" } }] });
    else if (ev.kind === "tool-result") patch((m) => ({ ...m, parts: m.parts.map((p) => "step" in p && p.step.id === ev.id
      ? { step: { ...p.step, state: ev.error ? "error" : "ok", note: ev.error ? ev.text : undefined } } : p) }));
    else if (ev.kind === "warn") setMsgs((all) => [...all, { who: "note", parts: [{ text: ev.text }] }]);
    else if (ev.kind === "done") {
      setBusy(false);
      // a step the CLI refused shows as failed in the stream; the question below replaces it
      patch((m) => ({ ...m, denied: ev.denied?.length ? ev.denied : undefined,
        parts: m.parts.filter((p) => !("step" in p) || p.step.state !== "run").map((p) =>
          "step" in p && ev.denied?.some((d: any) => d.name === p.step.name) ? { step: { ...p.step, state: "run" as const, note: "waiting for your OK" } } : p) }));
      if (ev.stopped) setMsgs((all) => [...all, { who: "note", parts: [{ text: "Stopped." }] }]);
      else if (ev.signedOut) setMsgs((all) => [...all, { who: "note", signIn: true, parts: [{ text: "Claude is not signed in on this PC." }] }]);
      else if (ev.error && ev.text) setMsgs((all) => [...all, { who: "note", parts: [{ text: ev.text }] }]);
    }
  }), []);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);
  useEffect(() => { if (open) box.current?.focus(); }, [open]);

  const send = async (text: string, allow: string[] = [], show = true) => {
    if (!text.trim() || busy || !inApp) return;
    if (show) setMsgs((all) => [...all.map((m) => ({ ...m, denied: undefined })), { who: "you", parts: [{ text }] }]);
    setBusy(true);
    const r = await window.sm!.chat("send", text, allow);
    if (r?.ok) return;
    setBusy(false);
    setMsgs((all) => [...all, r?.error === "no-cli"
      ? { who: "note", install: true, parts: [{ text: "Claude Code is not installed on this PC, or this app cannot find it." }] }
      : { who: "note", parts: [{ text: String(r?.error || "Could not start Claude.") }] }]);
  };
  const submit = () => { const t = draft; setDraft(""); send(t); };
  const allow = (m: Msg) => {
    const names = [...new Set(m.denied!.map((d) => d.name))];
    setMsgs((all) => all.map((x) => (x === m ? { ...x, denied: undefined } : x)));
    send("Approved by me in the app: " + m.denied!.map((d) => describe(d.name, d.input)).join("; ") + ". Go ahead with exactly that.", names, false);
  };
  const refuse = (m: Msg) => setMsgs((all) => [...all.map((x) => (x === m ? { ...x, denied: undefined } : x)), { who: "note", parts: [{ text: "Not allowed. Nothing was changed by that step." }] }]);

  return (
    <aside className={"chat" + (open ? "" : " closed")}>
      <header>
        <Icon name="claude" size={16} color="#d97757" /><b>Claude</b><span className="grow" />
        <button className="btn small" title="Forget this conversation and start a new one" disabled={busy || !msgs.length}
          onClick={() => { window.sm?.chat("reset"); setMsgs([]); }}>New chat</button>
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="close" size={15} /></button>
      </header>
      <div className="chat-log">
        {!msgs.length && <div className="chat-empty">
          <p>Tell Claude what to do in 3ds Max. It uses your own Claude account and only Scene Manager's 3ds Max tools.</p>
          {["Make a Dusk setup: sun low in the west, softer shadows", "What is different between Day and Night?", "Set every setup to 4K, 16:9"].map((s) =>
            <button key={s} className="chat-hint" disabled={!inApp} onClick={() => send(s)}>{s}</button>)}
          {!inApp && <p className="muted">The chat works in the app window, not in the browser preview.</p>}
        </div>}
        {msgs.map((m, i) => (
          <div key={i} className={"chat-msg " + m.who}>
            {m.parts.map((p, j) => "text" in p
              ? <div key={j} className="chat-text"><Rich text={p.text} /></div>
              : <div key={j} className={"chat-step " + p.step.state} title={p.step.note || JSON.stringify(p.step.input)}>
                  <i />{describe(p.step.name, p.step.input)}{p.step.note && <em> · {p.step.note}</em>}
                </div>)}
            {m.denied && <div className="chat-ask">
              <b>Claude asks before doing this:</b>
              {m.denied.map((d, j) => <div key={j}>{describe(d.name, d.input)}{d.input?.code && <pre>{String(d.input.code).slice(0, 800)}</pre>}</div>)}
              <div className="chat-ask-buttons">
                <button className="btn primary small" onClick={() => allow(m)}>Allow</button>
                <button className="btn small" onClick={() => refuse(m)}>Don't</button>
              </div>
            </div>}
            {m.signIn && <button className="btn primary small" onClick={() => window.sm?.chat("sign-in")}>Sign in to Claude</button>}
            {m.install && <button className="btn small" onClick={() => window.open("https://claude.com/claude-code")}>How to install Claude Code</button>}
          </div>))}
        {busy && <div className="chat-busy"><span /><span /><span /></div>}
        <div ref={end} />
      </div>
      <footer>
        <textarea ref={box} value={draft} rows={2} placeholder="Ask Claude to change the scene…" onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } e.stopPropagation(); }} />
        {busy
          ? <button className="btn" title="Stop Claude" onClick={() => window.sm?.chat("stop")}>Stop</button>
          : <button className="btn primary" disabled={!draft.trim() || !inApp} onClick={submit}>Send</button>}
      </footer>
    </aside>
  );
}
