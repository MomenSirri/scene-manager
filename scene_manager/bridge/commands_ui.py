"""Commands for the Scene Manager app (the separate Electron window). Each runs on the 3ds Max main thread.

The app holds no scene logic: it shows what `ui_state` / `ui_item` return and sends edits back. After every
change 3ds Max pushes a "changed" event (see max_server) and the app asks again.
"""
import pymxs
from pymxs import runtime as rt

from .. import thumbnails
from ..core import nodes, registry
from ..core.manager import get_manager
from ..ui import groups

NODE_KINDS = ("camera", "sunlight", "light")


def _renderer():
    try:
        return str(rt.classOf(rt.renderers.current))
    except Exception:
        return "?"


def _prop_schema(p):
    opts = p.options
    if callable(opts):
        try:
            opts = list(opts())
        except Exception:
            opts = []
    d = {"key": p.key, "label": p.label, "kind": p.kind, "options": list(opts or []), "tip": p.tip,
         "suffix": p.suffix, "decimals": p.decimals, "step": p.step}
    if p.kind in ("int", "float"):
        d["min"], d["max"] = p.minimum, p.maximum
    if p.columns:
        d["columns"] = [_prop_schema(c) for c in p.columns]
    return d


def ui_schema():
    """Static description of groups and modules (asked once per connection)."""
    mods = []
    for m in registry.modules():
        try:
            available = bool(m.available())
        except Exception:
            available = True
        mods.append({"key": m.key, "label": m.label, "group": groups.group_of(m), "column": m.column,
                     "available": available, "touches_scene": bool(getattr(m, "touches_scene", True)),
                     "props": [_prop_schema(p) for p in m.props]})
    return {"groups": [{"key": k, "label": l, "icon": i, "tint": t} for k, l, i, t in groups.GROUPS],
            "modules": mods}


def ui_state():
    """The setup tree and scene status. Small on purpose: thumbnails and cards are asked for separately."""
    mgr = get_manager()
    cols = [m for m in registry.modules() if m.column]
    items = []
    for it in mgr.items:
        d = {"id": it["id"], "type": it["type"], "name": it["name"], "parent": it.get("parent"),
             "color": it.get("color"), "tags": it.get("tags") or [], "description": it.get("description") or "",
             "thumb": bool(it.get("thumbnail"))}
        if it["type"] == "setup":
            d["summary"] = {m.key: mgr.summary(it, m.key) for m in cols}
        items.append(d)
    from ..core import repair
    from . import commands
    return {"file": str(rt.maxFileName or ""), "renderer": _renderer(), "active": mgr.active_id,
            "baseline": bool(mgr.baseline), "items": items, "last_apply_ms": mgr.last_apply_ms,
            "notice": repair.NOTICES[-1] if repair.NOTICES else "",
            "columns": [{"key": m.key, "label": m.column} for m in cols], "log": list(commands.LOG[-50:])}


def _names(fn):
    try:
        return [str(n.name) for n in fn()]
    except Exception:
        return []


def ui_item(id):
    """Cards of one setup or folder: per module its rows with the value shown and where it comes from."""
    mgr = get_manager()
    item = mgr.require(id)
    cards = []
    for m in registry.modules():
        state = mgr.module_state(item, m.key)
        if m.key not in item["modules"] and not state["enabled"]:
            continue
        own = (item["modules"].get(m.key) or {}).get("values") or {}
        try:
            scene = m.capture()
        except Exception:
            scene = {}
        differs = set()
        if item["type"] == "setup" and state["enabled"] and getattr(m, "touches_scene", True) and scene:
            try:
                differs = set(m.differs(state["values"], scene))
            except Exception:
                differs = set()
        rows = []
        for p in m.props:
            own_set = p.key in own
            inherited = p.key in state["values"] and not own_set
            value = own[p.key] if own_set else state["values"][p.key] if inherited else scene.get(p.key)
            src = mgr.get(state["source"].get(p.key)) if inherited else None
            row = {"key": p.key, "value": value, "own": own_set, "inherited": inherited,
                   "differs": p.key in differs, "from": src["name"] if src else ""}
            if p.kind in ("table", "checklist"):  # these show scene, folder and own entries side by side
                row.update(scene=scene.get(p.key), effective=state["values"].get(p.key), own_value=own.get(p.key))
            rows.append(row)
        srcs = {s for s in state["source"].values() if s != item["id"]}
        origin = ", ".join(sorted(mgr.get(s)["name"] for s in srcs if mgr.get(s)))
        cards.append({"key": m.key, "enabled": state["enabled"], "origin": origin, "rows": rows,
                      "actions": [label for label, _fn in m.actions()]})
    from ..modules import sun as sun_mod
    parent = mgr.get(item.get("parent"))
    return {"id": item["id"], "type": item["type"], "name": item["name"], "path": mgr.path(item),
            "folder": mgr.path(parent) if parent else "", "description": item.get("description") or "",
            "tags": item.get("tags") or [], "color": item.get("color"), "active": item["id"] == mgr.active_id,
            "setups_inside": len([d for d in mgr.descendants(item["id"]) if d["type"] == "setup"]),
            "cards": cards,
            "nodes": {"camera": _names(nodes.list_cameras), "light": _names(nodes.list_lights),
                      "sunlight": _names(lambda: sun_mod.list_suns() or nodes.list_lights())}}


def ui_thumbnail(id):
    return {"id": id, "data": get_manager().require(id).get("thumbnail")}


# ---- edits -------------------------------------------------------------------
def _coerce(module, prop_key, value):
    """The app sends node pickers as a name; the setup stores a node reference."""
    p = module.prop(prop_key)
    if p is not None and p.kind in NODE_KINDS and not isinstance(value, dict):
        if not value or value == "(none)":
            return None
        n = rt.getNodeByName(str(value))
        return nodes.ref(n) if n is not None else {"name": str(value), "handle": None}
    return value


def _live(mgr, item, module_key):
    """Edits on the active setup go to the scene at once, as one undo step."""
    if item["type"] == "setup" and item["id"] == mgr.active_id:
        m = registry.get(module_key)
        return mgr.apply(item["id"], only=[module_key], undo="Scene Manager: %s" % (m.label if m else module_key))
    return []


def ui_set_value(id, module, prop, value):
    mgr = get_manager()
    m = registry.get(module)
    if m is None:
        raise KeyError("Unknown module %r" % module)
    item = mgr.require(id)
    mgr.set_values(item["id"], module, {prop: _coerce(m, prop, value)})
    return {"errors": _live(mgr, item, module)}


def ui_clear_value(id, module, prop):
    mgr = get_manager()
    item = mgr.require(id)
    mgr.clear_value(item["id"], module, prop)
    return {"errors": _live(mgr, item, module)}


def ui_set_enabled(id, module, enabled):
    mgr = get_manager()
    item = mgr.require(id)
    mgr.set_enabled(item["id"], module, bool(enabled))
    return {"errors": _live(mgr, item, module)}


def ui_add_module(id, module):
    get_manager().capture(id, keys=[module])
    return {"ok": True}


def ui_remove_module(id, module):
    get_manager().remove_module(id, module)
    return {"ok": True}


def ui_fetch(id, module=None):
    """Read the scene into the item again (one module, or every module it uses)."""
    get_manager().capture(id, keys=[module] if module else None)
    return {"ok": True}


def ui_clear_module(id, module):
    mgr = get_manager()
    entry = mgr.require(id)["modules"].get(module)
    if entry:
        entry["values"] = {}
        mgr.commit()
    return {"ok": True}


def ui_action(id, module, label):
    """Run one of the module's own card actions (Module.actions())."""
    mgr = get_manager()
    item = mgr.require(id)
    m = registry.get(module)
    fn = dict(m.actions()).get(label)
    if fn is None:
        raise KeyError("No action %r on %s" % (label, module))
    values = dict(m.capture())
    values.update(mgr.module_state(item, module)["values"])
    new = fn(values)
    mgr.set_values(item["id"], module, {k: v for k, v in new.items() if values.get(k) != v})
    return {"errors": _live(mgr, item, module)}


def ui_activate(id):
    mgr = get_manager()
    item = mgr.require(id)
    errors = mgr.apply(item["id"], undo="Scene Manager: activate %s" % item["name"])
    return {"errors": errors, "ms": mgr.last_apply_ms}


def _thumb():
    try:
        return thumbnails.capture_viewport()
    except Exception:
        return None


def ui_new_setup(parent=None, name=None):
    s = get_manager().add_setup(name, parent=parent, thumbnail=_thumb())
    return {"id": s["id"]}


def ui_new_folder(parent=None, name="Folder"):
    return {"id": get_manager().add_folder(name, parent=parent)["id"]}


def ui_update(id, name=None, description=None, tags=None, color=None, clear_color=False):
    fields = {k: v for k, v in (("name", name), ("description", description), ("tags", tags), ("color", color))
              if v is not None}
    if clear_color:
        fields["color"] = None
    get_manager().update_item(id, **fields)
    return {"ok": True}


def ui_grab_thumbnail(id):
    get_manager().update_item(id, thumbnail=_thumb())
    return {"ok": True}


def ui_duplicate(id):
    return {"id": get_manager().duplicate(id)["id"]}


def ui_delete(id):
    get_manager().delete(id)
    return {"ok": True}


def ui_move(id, parent=None, index=None):
    """Move into a folder (None = top level) at a position among its children."""
    get_manager().move(id, parent, index)
    return {"ok": True}


def ui_baseline(action):
    """action: capture | restore | clear"""
    mgr = get_manager()
    if action == "capture":
        return {"modules": mgr.capture_baseline()}
    if action == "restore":
        with pymxs.undo(True, "Scene Manager: restore baseline"):
            return {"errors": mgr.restore_baseline()}
    mgr.clear_baseline()
    return {"ok": True}


def ui_render(ids):
    from ..render import batch
    return [{"setup": n, "status": st} for n, st in batch.render_setups(get_manager(), ids)]


def ui_queue(ids):
    """What a render of these setups/folders would produce (for the queue page)."""
    from ..render import batch
    mgr = get_manager()
    return [{"id": s["id"], "path": mgr.path(s), "camera": mgr.summary(s, "camera"), "size": mgr.summary(s, "output"),
             "frames": mgr.summary(s, "time"), "output": batch.planned_output(mgr, s)} for s in batch.expand(mgr, ids)]


COMMANDS = {f.__name__: f for f in (
    ui_schema, ui_state, ui_item, ui_thumbnail, ui_set_value, ui_clear_value, ui_set_enabled, ui_add_module,
    ui_remove_module, ui_fetch, ui_clear_module, ui_action, ui_activate, ui_new_setup, ui_new_folder, ui_update,
    ui_grab_thumbnail, ui_duplicate, ui_delete, ui_move, ui_baseline, ui_render, ui_queue)}
