import { useEffect, useRef, useState } from "react";
import { call } from "./api";
import type { CardData } from "./types";

/* Sun dial: the sky seen from above, as in the 3ds Max top view (+Y up, +X right).
   The rim is the horizon, the centre is straight overhead; rings at 30° and 60° elevation.
   Angles mode: drag the sun anywhere (Shift keeps the elevation, Ctrl keeps the azimuth).
   Time & place mode: the day's sun path is drawn and the sun slides along it (drag sets the time).
   While dragging, the sun in 3ds Max follows (active setup only, no undo record); letting go stores the
   values on the setup or folder and applies them as one undo step. */

const R = 92;                       // horizon radius in SVG units (viewBox is 220 x 220, centre 0,0)
const CARDINAL = ["N", "E", "S", "W"];
type PathPt = { t: string; az: number; el: number };
type SunPath = { points: PathPt[]; sunrise: string | null; sunset: string | null; noon: string; max_elevation: number };

const rad = (d: number) => (d * Math.PI) / 180;
const norm = (a: number) => ((a % 360) + 360) % 360;
/** Equidistant projection: elevation 90 at the centre, 0 on the rim; below the horizon stays on the rim. */
function toXY(az: number, el: number): [number, number] {
  const r = (R * (90 - Math.max(0, Math.min(90, el)))) / 90;
  return [r * Math.sin(rad(az)), -r * Math.cos(rad(az))];
}
const minutes = (t: string) => { const [h, m] = t.split(":").map(Number); return (h || 0) * 60 + (m || 0); };
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.round(m % 60)).padStart(2, "0")}`;

/** Sends the latest value only, one request in flight at a time, so a fast drag never queues up. */
function useLatest(send: (args: any) => Promise<any>) {
  const busy = useRef(false), next = useRef<any>(null);
  const pump = () => {
    if (busy.current || next.current === null) return;
    const a = next.current; next.current = null; busy.current = true;
    send(a).catch(() => {}).finally(() => { busy.current = false; pump(); });
  };
  return (a: any) => { next.current = a; pump(); };
}

export function SunDial({ itemId, card, onSet }: { itemId: string; card: CardData; onSet: (values: Record<string, any>) => void }) {
  const v: Record<string, any> = Object.fromEntries(card.rows.map((r) => [r.key, r.value]));
  const byTime = v.position === "date_time";
  const north = Number(v.north) || 0;
  const disabled = !card.enabled;
  const [drag, setDrag] = useState<{ az: number; el: number; t?: string } | null>(null);
  const [path, setPath] = useState<SunPath | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);
  const preview = useLatest((a) => call("ui_sun_preview", { id: itemId, ...a }));

  const placeKey = [v.date, v.latitude, v.longitude, v.utc_offset, north].join("|");
  useEffect(() => {
    if (!byTime) { setPath(null); return; }
    let live = true;
    call<SunPath>("ui_sun_path", { date: v.date, latitude: v.latitude, longitude: v.longitude, utc_offset: v.utc_offset ?? 0, north, step: 5 })
      .then((p) => { if (live) setPath(p); }).catch(() => { if (live) setPath(null); });
    return () => { live = false; };
  }, [byTime, placeKey]);   // eslint-disable-line react-hooks/exhaustive-deps

  const time = drag?.t ?? String(v.time ?? "12:00");
  // by time: the stored azimuth/elevation are whatever the angles were last; the sun sits on the path
  let onPath: PathPt | null = null;
  if (byTime && path && !drag) {
    const m = minutes(time);
    for (const p of path.points) if (!onPath || Math.abs(minutes(p.t) - m) < Math.abs(minutes(onPath.t) - m)) onPath = p;
  }
  const az = drag?.az ?? onPath?.az ?? Number(v.azimuth ?? 0), el = drag?.el ?? onPath?.el ?? Number(v.elevation ?? 0);

  const point = (e: React.PointerEvent): [number, number] => {
    const b = svg.current!.getBoundingClientRect();
    const s = 220 / b.width;
    return [(e.clientX - b.left) * s - 110, (e.clientY - b.top) * s - 110];
  };
  const fromPointer = (e: React.PointerEvent) => {
    const [x, y] = point(e);
    if (byTime && path) {
      let best: PathPt | null = null, bd = Infinity;
      for (const p of path.points) {
        if (p.el < -1) continue;
        const [px, py] = toXY(p.az, p.el), d = (px - x) ** 2 + (py - y) ** 2;
        if (d < bd) { bd = d; best = p; }
      }
      return best ? { az: best.az, el: best.el, t: best.t } : null;
    }
    let a = norm((Math.atan2(x, -y) * 180) / Math.PI), h = 90 * (1 - Math.min(1, Math.hypot(x, y) / R));
    if (e.shiftKey) h = Number(v.elevation ?? h);
    if (e.ctrlKey) a = Number(v.azimuth ?? a);
    return { az: Math.round(a * 2) / 2, el: Math.round(h * 2) / 2 };
  };
  const move = (d: { az: number; el: number; t?: string } | null) => {
    if (!d) return;
    setDrag(d);
    preview(d.t ? { time: d.t } : { azimuth: d.az, elevation: d.el });
  };
  const commit = (d: { az: number; el: number; t?: string } | null) => {
    if (!d) return;
    onSet(d.t ? { position: "date_time", time: d.t } : { position: "angles", azimuth: d.az, elevation: d.el });
  };
  // keep the dragged position on screen until 3ds Max reports the stored values back
  useEffect(() => { if (drag && !dragging.current) setDrag(null); }, [v.azimuth, v.elevation, v.time]);   // eslint-disable-line react-hooks/exhaustive-deps

  const onKey = (e: React.KeyboardEvent) => {
    if (disabled) return;
    const step = e.shiftKey ? 10 : 1;
    let d: { az: number; el: number; t?: string } | null = null;
    if (byTime && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      const m = Math.max(0, Math.min(1439, minutes(time) + (e.key === "ArrowRight" ? 5 : -5) * step));
      d = { az, el, t: hhmm(m) };
    } else if (!byTime) {
      if (e.key === "ArrowLeft") d = { az: norm(az - step), el };
      else if (e.key === "ArrowRight") d = { az: norm(az + step), el };
      else if (e.key === "ArrowUp") d = { az, el: Math.min(90, el + step) };
      else if (e.key === "ArrowDown") d = { az, el: Math.max(-90, el - step) };
    }
    if (d) { e.preventDefault(); commit(d); setDrag(d); }
  };

  // day path: split into pieces above the horizon
  const segs: string[] = [];
  if (path) {
    let cur: string[] = [];
    for (const p of path.points) {
      if (p.el >= 0) { const [x, y] = toXY(p.az, p.el); cur.push(`${x.toFixed(1)},${y.toFixed(1)}`); }
      else if (cur.length) { segs.push(cur.join(" ")); cur = []; }
    }
    if (cur.length) segs.push(cur.join(" "));
  }
  const hours = path ? path.points.filter((p) => p.t.endsWith(":00") && p.el >= 0) : [];
  const [sx, sy] = toXY(az, el);
  const below = el < 0;

  return (
    <div className={"sundial" + (disabled ? " disabled" : "")}>
      <svg ref={svg} viewBox="-110 -110 220 220" tabIndex={disabled ? -1 : 0} onKeyDown={onKey}
        aria-label={`Sun direction: azimuth ${az.toFixed(1)}°, elevation ${el.toFixed(1)}°`}
        onPointerDown={(e) => {
          if (disabled || e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId); e.currentTarget.focus();
          dragging.current = true; move(fromPointer(e));
        }}
        onPointerMove={(e) => { if (dragging.current) move(fromPointer(e)); }}
        onPointerUp={(e) => { if (!dragging.current) return; dragging.current = false; commit(fromPointer(e) ?? drag); }}
        onPointerCancel={() => { dragging.current = false; setDrag(null); }}>
        <defs>
          <radialGradient id="sd-sky" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(100,180,255,.20)" /><stop offset="100%" stopColor="rgba(42,212,196,.05)" />
          </radialGradient>
          <radialGradient id="sd-sun"><stop offset="0%" stopColor="#fff6d0" /><stop offset="45%" stopColor="#ffc94a" /><stop offset="100%" stopColor="rgba(255,159,10,0)" /></radialGradient>
        </defs>
        <circle r={R} className="sd-horizon" fill="url(#sd-sky)" />
        <circle r={(R * 2) / 3} className="sd-ring" /><circle r={R / 3} className="sd-ring" />
        {Array.from({ length: 24 }, (_, i) => {
          const a = rad(i * 15 + north), long = i % 6 === 0;
          return <line key={i} className="sd-tick" x1={Math.sin(a) * R} y1={-Math.cos(a) * R}
            x2={Math.sin(a) * (R + (long ? 7 : 4))} y2={-Math.cos(a) * (R + (long ? 7 : 4))} />;
        })}
        {CARDINAL.map((c, i) => {
          const a = rad(i * 90 + north);
          return <text key={c} className={"sd-card" + (c === "N" ? " n" : "")} x={Math.sin(a) * (R + 13)} y={-Math.cos(a) * (R + 13)}>{c}</text>;
        })}
        {segs.map((s, i) => <polyline key={i} className="sd-path" points={s} />)}
        {hours.map((p) => { const [x, y] = toXY(p.az, p.el); const h = Number(p.t.slice(0, 2));
          return <g key={p.t}><circle className="sd-hour" cx={x} cy={y} r={1.6} />
            {h % 3 === 0 && <text className="sd-hlabel" x={x} y={y - 4}>{h}</text>}</g>; })}
        <line className="sd-ray" x1={0} y1={0} x2={sx} y2={sy} />
        <line className="sd-shadow" x1={0} y1={0} x2={-sx * 0.35} y2={-sy * 0.35} />
        <circle className="sd-centre" r={2} />
        <g className={"sd-sun" + (below ? " below" : "") + (drag ? " active" : "")} transform={`translate(${sx},${sy})`}>
          <circle r={14} fill="url(#sd-sun)" /><circle r={5.5} className="sd-core" />
        </g>
      </svg>
      <div className="sd-read">
        <span title="0 = +Y (scene north), 90 = +X">Azimuth <b>{az.toFixed(1)}°</b></span>
        <span>Elevation <b className={below ? "warn" : ""}>{el.toFixed(1)}°</b></span>
        {byTime && <span>Time <b>{time}</b></span>}
      </div>
      {byTime && (
        <div className="sd-time">
          <input type="range" min={0} max={1435} step={5} value={minutes(time)} disabled={disabled}
            title={path ? `Sunrise ${path.sunrise ?? "–"} · sunset ${path.sunset ?? "–"}` : "Time of day"}
            onPointerDown={() => { dragging.current = true; }}
            onChange={(e) => { const t = hhmm(Number(e.target.value)); setDrag({ az, el, t }); preview({ time: t }); }}
            onPointerUp={(e) => { dragging.current = false; onSet({ position: "date_time", time: hhmm(Number((e.target as HTMLInputElement).value)) }); }}
            onKeyUp={(e) => onSet({ position: "date_time", time: hhmm(Number((e.target as HTMLInputElement).value)) })} />
          {path && <div className="sd-sunrise muted"><span>↑ {path.sunrise ?? "–"}</span><span>max {path.max_elevation.toFixed(0)}° at {path.noon}</span><span>↓ {path.sunset ?? "–"}</span></div>}
        </div>)}
      <div className="seg sd-mode">
        <button className={!byTime ? "on" : ""} disabled={disabled} onClick={() => byTime && onSet({ position: "angles", azimuth: az, elevation: el })}>Angles</button>
        <button className={byTime ? "on" : ""} disabled={disabled} onClick={() => !byTime && onSet({ position: "date_time" })}>Time &amp; place</button>
      </div>
    </div>
  );
}
