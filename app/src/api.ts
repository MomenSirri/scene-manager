// One way to talk to 3ds Max, whether the page runs in the Electron app (window.sm, a local socket to Max)
// or in a browser during development (HTTP to tools/dev_backend.py).
type Listener = (ev: { event: string; [k: string]: any }) => void;

declare global {
  interface Window {
    sm?: {
      call(cmd: string, args?: object): Promise<any>;
      onEvent(fn: Listener): () => void;
      chat(what: "send" | "stop" | "reset" | "sign-in" | "status", text?: string, allow?: string[]): Promise<any>;
      status(): Promise<{ connected: boolean; onTop: boolean; owned: boolean; rolled: boolean; attach: boolean }>;
      pickFolder(title?: string): Promise<string>;
      reveal(path: string): Promise<void>;
      store: { get(key: string): Promise<any>; set(key: string, value: any): Promise<void> };
      win: { minimize(): void; maximize(): void; close(): void; setOnTop(on: boolean): Promise<boolean>; setAttach(on: boolean): Promise<boolean>; roll(on: boolean): Promise<boolean>; drag(phase: "start" | "move" | "end", x?: number, y?: number): void };
    };
  }
}

const listeners = new Set<Listener>();
export const inApp = typeof window !== "undefined" && !!window.sm;
if (inApp) window.sm!.onEvent((ev) => listeners.forEach((fn) => fn(ev)));

export function onEvent(fn: Listener) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export async function call<T = any>(cmd: string, args: object = {}): Promise<T> {
  if (inApp) return window.sm!.call(cmd, args);
  const r = await fetch("/call", { method: "POST", body: JSON.stringify({ cmd, args }) });
  const body = await r.json();
  if (!body.ok) throw new Error(body.error);
  // no push channel in the browser: tell the page to look again after anything that is not a plain read
  if (!/^(ui_(state|item|schema|thumbnail|queue)|lib_(roots|list|thumbs))$/.test(cmd)) setTimeout(() => listeners.forEach((fn) => fn({ event: "changed" })), 0);
  return body.result;
}

export async function connected(): Promise<boolean> {
  if (inApp) return (await window.sm!.status()).connected;
  try { await call("ui_state"); return true; } catch { return false; }
}

export const store = {
  async get<T>(key: string, fallback: T): Promise<T> {
    try {
      const v = inApp ? await window.sm!.store.get(key) : JSON.parse(localStorage.getItem("sm:" + key) || "null");
      return v ?? fallback;
    } catch { return fallback; }
  },
  set(key: string, value: any) {
    if (inApp) window.sm!.store.set(key, value);
    else localStorage.setItem("sm:" + key, JSON.stringify(value));
  },
};
