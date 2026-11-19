"""Bridge commands for the M2 scene modules (baseline, lights, layers, objects, notes, to-dos, repair).

Loaded by bridge/commands.py (_load_extra_commands). Each runs on the 3ds Max main thread.
"""
from pymxs import runtime as rt

from ..core import nodes, registry, repair
from ..core.manager import get_manager
from ..core.module_base import merge_table
from ..modules import layers as layers_mod
from ..modules import lights as lights_mod
from ..modules import objects as objects_mod
from ..modules import time_range
from .commands import log


def _own(item, module):
    return ((item["modules"].get(module) or {}).get("values") or {})


def _set_rows(name, module, prop, rows, extra=None):
    """Merge rows into the table stored on a setup/folder (None removes a row)."""
    mgr = get_manager()
    item = mgr.require(name)
    table = merge_table(_own(item, module).get(prop) or {}, rows or {})
    values = {prop: table}
    values.update({k: v for k, v in (extra or {}).items() if v is not None})
    mgr.set_values(item["id"], module, values)
    return mgr.path(item), table


# ---- baseline ---------------------------------------------------------------
def capture_baseline(modules=None):
    """Record the current scene as the baseline every setup starts from (deterministic activation)."""
    keys = get_manager().capture_baseline(modules)
    log("Captured scene baseline (%s)" % ", ".join(keys))
    return {"baseline_modules": keys}


def clear_baseline(modules=None):
    get_manager().clear_baseline(modules)
    log("Cleared scene baseline%s" % (" for " + ", ".join(modules) if modules else ""))
    return {"ok": True}


def get_baseline():
    b = get_manager().baseline
    out = {}
    for k, v in b.items():
        m = registry.get(k)
        try:
            out[k] = m.summary(v) if m else ""
        except Exception:
            out[k] = "?"
    return {"modules": out, "values": b}


def restore_baseline():
    errors = get_manager().restore_baseline()
    log("Restored scene baseline")
    return {"errors": errors}


# ---- lights / layers / objects -----------------------------------------------
def set_lights(name, lights, others=None):
    """lights = {light_name: {"on": bool, "intensity": float, "color": [r, g, b]}} (None removes the row)."""
    rows = {}
    for lname, row in (lights or {}).items():
        if row is None:
            rows[lname] = None
            continue
        n = rt.getNodeByName(lname)
        if n is None:
            raise KeyError("No light named %r" % lname)
        rows[lname] = dict({k: v for k, v in row.items() if k in ("on", "intensity", "color")}, ref=nodes.ref(n))
    path, table = _set_rows(name, "lights", "lights", rows, {"others": others})
    log("Lights on %s: %s" % (path, ", ".join("%s %s" % (k, v) for k, v in (lights or {}).items())))
    return {"setup": path, "lights": table}


def set_layers(name, layers, others=None):
    """layers = {layer_name: {"on": bool, "renderable": bool, "frozen": bool}} (None removes the row)."""
    for lname, row in (layers or {}).items():
        if row is not None and rt.LayerManager.getLayerFromName(lname) is None:
            raise KeyError("No layer named %r" % lname)
    path, table = _set_rows(name, "layers", "layers", layers, {"others": others})
    log("Layers on %s: %s" % (path, ", ".join(layers or {})))
    return {"setup": path, "layers": table}


def set_object_rule(name, target, visible=None, renderable=None, camera=None, reflections=None,
                    cast_shadows=None, see_through=None, frozen=None, remove=False):
    """Add/replace (or remove) one Objects rule. target: set:Name | layer:Name | pattern:Tree_* | node:Name."""
    if remove:
        row = None
    else:
        row = {"visible": visible, "renderable": renderable, "camera": camera, "reflections": reflections,
               "cast_shadows": cast_shadows, "see_through": see_through, "frozen": frozen}
        hits = objects_mod.resolve_target(target)
        if hits is None:
            raise KeyError("Target %r not found (selection set, layer or node)" % target)
        row = {k: v for k, v in row.items() if v is not None}
        kind, nm = objects_mod.split_target(target)
        if kind == "node":
            row["ref"] = nodes.ref(hits[0])
            target = "node:" + nm
    mgr = get_manager()
    item = mgr.require(name)
    rules = dict(_own(item, "objects").get("rules") or {})
    if row is None:
        rules.pop(target, None)
    else:
        rules[target] = row
    mgr.set_values(item["id"], "objects", {"rules": rules})
    log("Objects rule on %s: %s %s" % (mgr.path(item), target, "removed" if remove else
                                       {k: v for k, v in row.items() if v is not None and k != "ref"}))
    return {"setup": mgr.path(item), "rules": rules,
            "matches": None if remove else len(objects_mod.resolve_target(target, row) or [])}


def list_targets():
    """Selection sets (with object counts), layers, and non-sun lights, for Objects/Lights/Layers rules."""
    return {"selection_sets": {k: len(v) for k, v in objects_mod.selection_sets().items()},
            "layers": {str(l.name): layers_mod.read_layer(l) for l in layers_mod.all_layers()},
            "lights": {str(l.name): {k: v for k, v in lights_mod.read_light(l).items() if k != "ref"}
                       for l in lights_mod.managed_lights()}}


# ---- notes / to-dos -----------------------------------------------------------
def set_notes(name, text, append=False):
    mgr = get_manager()
    item = mgr.require(name)
    if append:
        old = _own(item, "notes").get("text") or ""
        text = (old + "\n" + text).strip() if old else text
    mgr.set_values(item["id"], "notes", {"text": text})
    log("Notes on %s" % mgr.path(item))
    return {"setup": mgr.path(item), "text": text}


def todo(name, add=None, done=None, undone=None, remove=None):
    """Edit a setup's to-do list. add: text; done/undone/remove: item text or 1-based index."""
    mgr = get_manager()
    item = mgr.require(name)
    items = [dict(i) for i in (mgr.module_state(item, "todo")["values"].get("items") or [])]

    def find(x):
        if isinstance(x, int) or (isinstance(x, str) and x.isdigit()):
            return int(x) - 1
        for i, it in enumerate(items):
            if it["text"].lower() == str(x).lower():
                return i
        raise KeyError("No to-do %r" % x)
    if add:
        items.append({"text": add, "done": False})
    for x, flag in ((done, True), (undone, False)):
        if x is not None:
            items[find(x)]["done"] = flag
    if remove is not None:
        del items[find(remove)]
    mgr.set_values(item["id"], "todo", {"items": items})
    log("To-do on %s" % mgr.path(item))
    return {"setup": mgr.path(item), "items": items}


# ---- repair / camera keys -----------------------------------------------------
def find_missing_nodes():
    """Node references in setups that no longer resolve (deleted or replaced cameras, lights, objects)."""
    return repair.find_missing(get_manager())


def repair_node(old_name, new_name):
    """Point every setup reference to node `old_name` at node `new_name`."""
    n = repair.repair(get_manager(), old_name, new_name)
    log("Repaired %s -> %s (%d refs)" % (old_name, new_name, n))
    return {"changed": n}


def camera_key_range(camera=None):
    """First and last key frame of a camera (default: the active viewport camera)."""
    cam = rt.getNodeByName(camera) if camera else None
    r = time_range.camera_key_range(cam)
    return {"camera": camera or (str(rt.viewport.getCamera().name) if rt.viewport.getCamera() else None),
            "range": list(r) if r else None}


COMMANDS = {f.__name__: f for f in (
    capture_baseline, clear_baseline, get_baseline, restore_baseline, set_lights, set_layers,
    set_object_rule, list_targets, set_notes, todo, find_missing_nodes, repair_node, camera_key_range)}
