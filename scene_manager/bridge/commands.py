"""Commands the Claude bridge exposes. Each runs on the 3ds Max main thread."""
import contextlib
import datetime
import io
import json

import pymxs
from pymxs import runtime as rt

from ..core import nodes, registry, tokens
from ..core.manager import get_manager
from ..modules import sun as sun_mod
from ..render import batch

# Recent Claude actions, shown in the panel's Claude page.
LOG = []
_log_listeners = []


def log(text):
    LOG.append("%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S"), text))
    del LOG[:-200]
    for fn in list(_log_listeners):
        try:
            fn()
        except Exception:
            pass


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        if isinstance(v, (list, tuple)):
            return [_jsonable(x) for x in v]
        return str(v)


def _frame(expr):
    return int(rt.execute("((%s) as integer) / TicksPerFrame" % expr))


def ping():
    return {"max_version": int(rt.maxVersion()[0]), "file": str(rt.maxFilePath) + str(rt.maxFileName)}


def scene_info():
    cam = rt.viewport.getCamera()
    layers = []
    for i in range(rt.LayerManager.count):
        l = rt.LayerManager.getLayer(i)
        layers.append({"name": str(l.name), "on": bool(l.on), "renderable": bool(l.renderable)})
    lights = []
    for l in nodes.list_lights():
        info = {"name": str(l.name), "class": str(rt.classOf(l)),
                "position": [round(float(x), 3) for x in (l.pos.x, l.pos.y, l.pos.z)]}
        if rt.isProperty(l, rt.Name("on")):
            info["on"] = bool(l.on)
        if sun_mod.is_sun(l):
            az, el, _ = sun_mod.get_direction(l)
            info.update(azimuth=az, elevation=el)
        lights.append(info)
    mgr = get_manager()
    return {
        "file": str(rt.maxFilePath) + str(rt.maxFileName),
        "max_version": int(rt.maxVersion()[0]),
        "renderer": str(rt.classOf(rt.renderers.current)),
        "renderer_short": tokens.renderer_name(),
        "units": str(rt.units.SystemType),
        "active_camera": str(cam.name) if cam is not None else None,
        "cameras": [str(c.name) for c in nodes.list_cameras()],
        "lights": lights,
        "layers": layers,
        "resolution": [int(rt.renderWidth), int(rt.renderHeight)],
        "output": str(rt.rendOutputFilename or ""),
        "frame": _frame("sliderTime"),
        "environment_map": str(rt.environmentMap) if rt.environmentMap is not None else None,
        "active_setup": mgr.path(mgr.get(mgr.active_id)) if mgr.get(mgr.active_id) else None,
        "setups": [mgr.path(s) for s in mgr.setups()],
        "modules": {m.key: [p.key for p in m.props] for m in registry.modules()},
    }


def inspect_node(name):
    n = rt.getNodeByName(name)
    if n is None:
        raise KeyError("No node named %r" % name)
    out = {"name": str(n.name), "class": str(rt.classOf(n)), "superclass": str(rt.superClassOf(n)),
           "position": [float(n.pos.x), float(n.pos.y), float(n.pos.z)],
           "transform_controller": str(rt.classOf(n.controller)) if n.controller is not None else None,
           "target": str(n.target.name) if rt.isProperty(n, rt.Name("target")) and n.target is not None else None,
           "properties": {}}
    for p in rt.getPropNames(n):
        try:
            out["properties"][str(p)] = str(rt.getProperty(n, p))
        except Exception as e:
            out["properties"][str(p)] = "<%s>" % e
    return out


def list_setups():
    mgr = get_manager()
    out = []
    for i in mgr.items:
        out.append({"path": mgr.path(i), "type": i["type"], "active": i["id"] == mgr.active_id,
                    "tags": i.get("tags", []), "description": i.get("description", ""),
                    "modules": mgr.describe(i)})
    return out


def get_setup(name):
    mgr = get_manager()
    i = mgr.require(name)
    return {"path": mgr.path(i), "type": i["type"], "description": i.get("description", ""),
            "tags": i.get("tags", []),
            "own_overrides": i["modules"],
            "effective": mgr.effective(i)}


def apply_setup(name):
    mgr = get_manager()
    errors = mgr.apply(name)
    log("Activated %s" % name)
    return {"applied": name, "errors": errors, "ms": mgr.last_apply_ms}


def capture_setup(name, modules=None, folder=None, thumbnail=True):
    """Create the setup from the current scene (inside `folder` if given), or re-capture it."""
    mgr = get_manager()
    thumb = None
    if thumbnail:
        try:
            from .. import thumbnails
            thumb = thumbnails.capture_viewport()
        except Exception:
            thumb = None
    s = mgr.get(name)
    if s is None:
        parent = None
        if folder:
            f = mgr.get(folder) or mgr.add_folder(folder)
            parent = f["id"]
        s = mgr.add_setup(name, parent=parent, keys=modules, thumbnail=thumb)
        log("Created setup %s" % mgr.path(s))
        return {"created": mgr.path(s)}
    mgr.capture(s["id"], keys=modules)
    if thumb:
        mgr.update_item(s["id"], thumbnail=thumb)
    log("Re-captured %s" % mgr.path(s))
    return {"updated": mgr.path(s)}


def create_folder(name, parent=None):
    mgr = get_manager()
    f = mgr.add_folder(name, parent=mgr.require(parent)["id"] if parent else None)
    log("Created folder %s" % mgr.path(f))
    return {"created": mgr.path(f)}


def move_item(name, folder=None):
    mgr = get_manager()
    mgr.move(name, mgr.require(folder)["id"] if folder else None)
    return {"moved": name, "to": folder or "(top)"}


def set_module_values(name, module, values=None, enabled=None):
    """Override properties of a module on a setup or folder; enabled=False switches the module off there."""
    mgr = get_manager()
    if values:
        mgr.set_values(name, module, values)
    if enabled is not None:
        mgr.set_enabled(name, module, bool(enabled))
    log("Set %s on %s: %s" % (module, name, values if values else "enabled=%s" % enabled))
    return {"ok": True}


def update_setup_info(name, new_name=None, description=None, tags=None):
    fields = {k: v for k, v in (("name", new_name), ("description", description), ("tags", tags)) if v is not None}
    get_manager().update_item(name, **fields)
    return {"ok": True}


def delete_setup(name):
    get_manager().delete(name)
    log("Deleted %s" % name)
    return {"deleted": name}


def render_setups(names):
    mgr = get_manager()
    log("Rendering %s" % ", ".join(names))
    return [{"setup": n, "status": st} for n, st in batch.render_setups(mgr, names)]


def set_sun_direction(azimuth, elevation, sun_name=None, distance=None):
    """Place a sun light by compass angles. Azimuth 0 = +Y (north), 90 = +X (east)."""
    sun = rt.getNodeByName(sun_name) if sun_name else None
    if sun is None:
        suns = sun_mod.list_suns()
        if not suns:
            raise RuntimeError("No sun light found. Pass sun_name.")
        sun = suns[0]
    with pymxs.undo(True, "Claude: sun direction"):
        sun_mod.set_direction(sun, float(azimuth), float(elevation), distance)
    rt.redrawViews()
    log("Sun %s -> azimuth %.1f, elevation %.1f" % (sun.name, azimuth, elevation))
    return {"sun": str(sun.name), "position": [float(sun.pos.x), float(sun.pos.y), float(sun.pos.z)]}


def run_python(code):
    """Run Python in 3ds Max. Globals: rt, pymxs, sm (setup manager). Set `result` to return data."""
    g = {"rt": rt, "pymxs": pymxs, "sm": get_manager(), "result": None, "__name__": "__claude__"}
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pymxs.undo(True, "Claude"):
        exec(compile(code, "<claude>", "exec"), g)
    rt.redrawViews()
    first = code.strip().splitlines()[0] if code.strip() else ""
    log("Python: %s%s" % (first[:80], " ..." if len(code.strip().splitlines()) > 1 else ""))
    return {"stdout": out.getvalue(), "result": _jsonable(g.get("result"))}


def run_maxscript(code):
    with pymxs.undo(True, "Claude"):
        r = rt.execute(code)
    rt.redrawViews()
    log("MAXScript: %s" % code.strip()[:80])
    return {"result": str(r)}


COMMANDS = {f.__name__: f for f in (
    ping, scene_info, inspect_node, list_setups, get_setup, apply_setup, capture_setup, create_folder,
    move_item, set_module_values, update_setup_info, delete_setup, render_setups, set_sun_direction,
    run_python, run_maxscript)}


def _load_extra_commands():
    """Merge COMMANDS from bridge/commands_*.py files (one per module group), so groups add
    bridge commands without editing this file."""
    import importlib
    import os
    import pkgutil
    import traceback
    here = os.path.dirname(__file__)
    for info in sorted(pkgutil.iter_modules([here]), key=lambda i: i.name):
        if not info.name.startswith("commands_"):
            continue
        try:
            mod = importlib.import_module(__package__ + "." + info.name)
            COMMANDS.update(getattr(mod, "COMMANDS", {}))
        except Exception:
            print("Scene Manager: bridge command file '%s' failed to load:" % info.name)
            traceback.print_exc()


_load_extra_commands()
