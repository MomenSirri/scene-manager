"""Bridge commands for the M4 render modules (merged into bridge/commands.py COMMANDS)."""
import pymxs
from pymxs import runtime as rt

from ..core import registry
from ..core.manager import get_manager
from ..modules import custom_props, lightmix, render_elements, render_override, render_preset
from ..render import rprops
from ..core.undo import undo_step


def _log(text):
    from . import commands
    commands.log(text)


def render_info():
    """Current renderer, installed renderers, curated settings, render elements, overrides and light groups."""
    kind = rprops.current_kind()
    curated = {}
    for m in registry.modules():
        if m.category == "render" and getattr(m, "kinds", None) and kind in m.kinds:
            curated = {"module": m.key, "values": m.capture(), "props": [p.key for p in m.props]}
    els = [{"name": render_elements.element_name(el), "class": str(rt.classOf(el)), "enabled": bool(el.enabled)}
           for _, el in render_elements.elements()]
    return {
        "renderer": kind,
        "renderer_class": str(rt.classOf(rprops.current())),
        "installed": sorted(rprops.renderer_classes().keys()),
        "curated": curated,
        "elements_active": bool(render_elements.manager().GetElementsActive()),
        "elements": els,
        "changed_vs_defaults": len(render_override.scene_diff()),
        "light_groups": {g: [str(n.name) for n in ms] for g, ms in lightmix.groups().items()},
    }


def render_props(filter=None, changed_only=False):
    """Renderer properties with current values (and defaults). filter = substring of the name."""
    r = rprops.current()
    f = (filter or "").lower()
    cur = rprops.snapshot(r, include=lambda n: f in n.lower())
    base = rprops.defaults(r)
    if changed_only:
        cur = rprops.diff(cur, base)
    return {p: {"value": v, "default": base.get(p)} for p, v in sorted(cur.items())}


def set_render_props(values):
    """Set renderer properties in the scene now (not stored in a setup). One undo step."""
    r = rprops.current()
    done, missing = {}, []
    with undo_step("Claude: render settings"):
        for p, v in values.items():
            old = rprops.read(r, [p])
            if rprops.write(r, [p], v) is None:
                missing.append(p)
            else:
                done[p] = [old, v]
    _log("Render settings: %s" % ", ".join("%s %s -> %s" % (k, a, b) for k, (a, b) in done.items()))
    return {"changed": done, "missing": missing}


def fetch_render_overrides(name):
    """Store every renderer property that differs from the defaults on a setup or folder."""
    m = registry.get("render_override")
    values = m.capture()
    get_manager().set_values(name, m.key, values)
    _log("Fetched %d render overrides into %s" % (len(values["overrides"]), name))
    return {"stored": len(values["overrides"]), "renderer": values["renderer"]}


def fetch_post_production(name):
    """Store the current V-Ray VFB layers or Corona tone mapping on a setup or folder."""
    m = registry.get("post")
    values = m.capture()
    if not values:
        raise RuntimeError("nothing to store for renderer %s" % rprops.current_kind())
    get_manager().set_values(name, m.key, values)
    _log("Stored post-production on %s" % name)
    return {"stored": sorted(values.keys())}


def save_render_preset(path):
    """Save the current render settings as a .rps file."""
    render_preset.save(path)
    _log("Saved render preset %s" % path)
    return {"saved": path}


def add_custom_property(name, prop, target="node", node=None, path=None, value=None):
    """Store any property on a setup/folder. target: node | renderer | environment | maxscript.
    path: dot path from the target (e.g. "material", "modifiers.1") or, for maxscript, an expression.
    value None = keep the current scene value."""
    key, row = custom_props.make_row(target, prop, path or "", node, value)
    mgr = get_manager()
    own = ((mgr.require(name)["modules"].get("custom_props") or {}).get("values") or {}).get("rows") or {}
    mgr.set_values(name, "custom_props", {"rows": dict(own, **{key: row})})
    _log("Custom property %s = %s on %s" % (key, row["value"], name))
    return {"stored": key, "value": row["value"]}


COMMANDS = {f.__name__: f for f in (
    render_info, render_props, set_render_props, fetch_render_overrides, fetch_post_production,
    save_render_preset, add_custom_property)}
