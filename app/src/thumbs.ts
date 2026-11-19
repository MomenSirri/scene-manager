// HDRI / environment thumbnails from the library (3ds Max makes and caches them in ~/.scene_manager/hdri_thumbs).
// One shared cache for the browser grid and the small previews on the cards. Only what is on screen is asked for,
// a few at a time, so a big library never stalls 3ds Max.
import { useEffect, useState } from "react";
import { call } from "./api";

type Thumb = string | null;  // data URL, or null when 3ds Max could not read the file
const cache = new Map<string, Thumb>();
const waiting = new Map<string, Set<(t: Thumb) => void>>();
let queue: string[] = [];
let running = false;

async function pump() {
  if (running) return;
  running = true;
  try {
    while (queue.length) {
      const batch = queue.splice(0, 8).filter((p) => !cache.has(p) && waiting.has(p));
      if (!batch.length) continue;
      let r: { thumbs: Record<string, Thumb>; pending: string[] };
      try { r = await call("lib_thumbs", { paths: batch }); }
      catch { batch.forEach((p) => waiting.delete(p)); continue; }   // offline: ask again next time it is shown
      for (const [p, t] of Object.entries(r.thumbs)) {
        cache.set(p, t);
        waiting.get(p)?.forEach((fn) => fn(t));
        waiting.delete(p);
      }
      queue = [...r.pending, ...queue];   // budget spent in 3ds Max: these come first next round
    }
  } finally { running = false; }
}

/** Ask for a thumbnail; returns an unsubscribe function. Already cached ones answer at once. */
export function wantThumb(path: string, fn: (t: Thumb) => void): () => void {
  if (cache.has(path)) { fn(cache.get(path)!); return () => {}; }
  let set = waiting.get(path);
  if (!set) { set = new Set(); waiting.set(path, set); queue.push(path); }
  set.add(fn);
  pump();
  return () => {
    const s = waiting.get(path);
    if (!s) return;
    s.delete(fn);
    if (!s.size) { waiting.delete(path); queue = queue.filter((p) => p !== path); }   // scrolled away before it came
  };
}

export function useThumb(path: string | null | undefined, visible = true): Thumb | undefined {
  const [t, setT] = useState<Thumb | undefined>(() => (path && cache.has(path) ? cache.get(path) : undefined));
  useEffect(() => {
    if (!path) { setT(undefined); return; }
    if (cache.has(path)) { setT(cache.get(path)); return; }
    setT(undefined);
    if (!visible) return;
    return wantThumb(path, setT);
  }, [path, visible]);
  return t;
}

export function baseName(p: string) {
  const f = p.split(/[\\/]/).pop() || p;
  return f.replace(/\.[^.]+$/, "");
}
