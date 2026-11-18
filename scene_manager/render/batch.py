"""Local batch render: activate each setup and run a production render (same as Render / F9)."""
import os

from pymxs import runtime as rt

from ..core import tokens


def planned_output(mgr, setup):
    out = mgr.effective(setup).get("output")
    if out and out.get("save_file") and out.get("path"):
        return tokens.resolve(out["path"], mgr.context(setup))
    return ""


def expand(mgr, keys):
    """Setups for the given keys; a folder expands to every setup inside it."""
    seen, out = set(), []
    for k in keys:
        item = mgr.get(k)
        if item is None:
            continue
        targets = [item] if item["type"] == "setup" else [i for i in mgr.descendants(item["id"]) if i["type"] == "setup"]
        for t in targets:
            if t["id"] not in seen:
                seen.add(t["id"])
                out.append(t)
    return out


def duplicate_outputs(mgr, keys):
    seen, dups = {}, []
    for s in expand(mgr, keys):
        p = planned_output(mgr, s).lower()
        if p:
            if p in seen:
                dups.append((seen[p], s["name"], p))
            seen[p] = s["name"]
    return dups


def render_setups(mgr, keys, on_progress=None, should_cancel=None):
    """Render setups in order. Returns a list of (name, status)."""
    setups = expand(mgr, keys)
    results = []
    for i, s in enumerate(setups):
        if should_cancel and should_cancel():
            results.append((s["name"], "cancelled"))
            break
        if on_progress:
            on_progress(i, len(setups), mgr.path(s))
        errors = mgr.apply(s["id"])
        try:
            out = str(rt.rendOutputFilename or "")
            if out and rt.rendSaveFile:
                os.makedirs(os.path.dirname(out), exist_ok=True)
            rt.renderSceneDialog.close()
            rt.execute("max quick render")
            results.append((mgr.path(s), "ok" if not errors else "rendered with errors: " + "; ".join(errors)))
        except Exception as e:
            results.append((mgr.path(s), "failed: %s" % e))
    if on_progress:
        on_progress(len(setups), len(setups), "")
    return results
