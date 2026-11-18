import { useEffect, useLayoutEffect, useRef, useState } from "react";

export type MenuItem =
  | { label: string; onClick: () => void; disabled?: boolean; danger?: boolean; hint?: string }
  | { sep: true }
  | { custom: JSX.Element };

export interface MenuState { x: number; y: number; items: MenuItem[] }

/** Popup menu at a screen point; closes on outside click, Escape or after a choice. */
export function Menu({ menu, onClose }: { menu: MenuState; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: menu.x, y: menu.y });
  useLayoutEffect(() => {
    const r = ref.current!.getBoundingClientRect();
    setPos({ x: Math.max(4, Math.min(menu.x, window.innerWidth - r.width - 6)),
             y: Math.max(4, Math.min(menu.y, window.innerHeight - r.height - 6)) });
  }, [menu]);
  useEffect(() => {
    const down = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("mousedown", down, true);
    window.addEventListener("keydown", key);
    window.addEventListener("blur", onClose);
    return () => { window.removeEventListener("mousedown", down, true); window.removeEventListener("keydown", key); window.removeEventListener("blur", onClose); };
  }, [onClose]);
  return (
    <div ref={ref} className="menu" style={{ left: pos.x, top: pos.y }} role="menu">
      {menu.items.map((it, i) =>
        "sep" in it ? <div key={i} className="menu-sep" /> :
        "custom" in it ? <div key={i} className="menu-custom">{it.custom}</div> :
        <button key={i} className={"menu-item" + (it.danger ? " danger" : "")} disabled={it.disabled} role="menuitem"
          onClick={() => { onClose(); it.onClick(); }}>
          <span>{it.label}</span>{it.hint && <kbd>{it.hint}</kbd>}
        </button>)}
    </div>
  );
}
