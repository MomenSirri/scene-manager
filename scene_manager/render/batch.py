"""Local batch render: activate each setup and run a production render (same as Render / F9)."""
import os
from dataclasses import dataclass, field

from pymxs import runtime as rt

from ..core import nodes, tokens


@dataclass
class QueueEntry:
    setup: dict
    output: str = ""
    issues: list[str] = field(default_factory=list)


def _stored_values(mgr, setup, module):
    state = mgr.module_state(setup, module)
    baseline = mgr.baseline.get(module) or {}
    return {**baseline, **state["values"]} if state["enabled"] else baseline


def planned_output(mgr, setup):
    out = _stored_values(mgr, setup, "output")
    if out.get("save_file") and out.get("path"):
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


def preflight(mgr, keys):
    """Preview stored camera references and main output paths without activating setups."""
    entries = []
    by_output = {}
    for setup in expand(mgr, keys):
        entry = QueueEntry(setup)
        entries.append(entry)
        camera = _stored_values(mgr, setup, "camera").get("camera")
        if camera:
            node = nodes.resolve(camera)
            if node is None or not nodes.is_camera(node):
                entry.issues.append("Stored camera unavailable")
        try:
            entry.output = planned_output(mgr, setup)
        except (ValueError, KeyError, IndexError, AttributeError, TypeError):
            entry.issues.append("Invalid output template")
        if entry.output:
            by_output.setdefault(os.path.normcase(entry.output), []).append(entry)

    for matching_entries in by_output.values():
        if len(matching_entries) > 1:
            for entry in matching_entries:
                entry.issues.append("Shared output path")
        if os.path.isfile(matching_entries[0].output):
            for entry in matching_entries:
                entry.issues.append("Output file already exists")
    return entries


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
