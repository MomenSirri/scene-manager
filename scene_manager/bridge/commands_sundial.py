"""Backend of the sun dial in the app's Sun card (drag the sun on a dome to set its direction).

ui_sun_path     the sun's path over one day for a date and place (for drawing, no 3ds Max calls)
ui_sun_preview  move the sun while the dial is dragged: no undo record, nothing stored
ui_set_values   store several values of one module at once and apply them as one undo step
                (the drop at the end of a drag: azimuth + elevation, or position + time)
"""
import pymxs
from pymxs import runtime as rt

from ..core import nodes, registry
from ..core.manager import get_manager
from ..env import solar
from ..modules import sun as sun_mod
from .commands_ui import _coerce, _live


def ui_sun_path(date, latitude, longitude, utc_offset=0.0, north=0.0, step=10):
    """Points every `step` minutes from 00:00 to 24:00: {"t": "HH:MM", "az": scene azimuth, "el": elevation}.
    Also sunrise / sunset (first and last minute above the horizon) and the highest point."""
    step = max(1, min(60, int(step)))
    pts = []
    for minute in range(0, 24 * 60 + 1, step):
        t = "%02d:%02d" % divmod(min(minute, 24 * 60 - 1), 60)
        az, el = solar.sun_position(date, t, float(latitude), float(longitude), float(utc_offset))
        pts.append({"t": t, "az": round(solar.scene_azimuth(az, north), 2), "el": round(el, 2)})
    up = [p for p in pts if p["el"] > 0]
    noon = max(pts, key=lambda p: p["el"])
    return {"points": pts, "sunrise": up[0]["t"] if up else None, "sunset": up[-1]["t"] if up else None,
            "noon": noon["t"], "max_elevation": noon["el"]}


def ui_sun_preview(id, azimuth=None, elevation=None, time=None, light=None):
    """Move the sun of the active setup while the dial is dragged. Inactive setups: nothing happens
    (their values only reach the scene when they are activated). Either angles or a time (uses the
    stored date and place)."""
    mgr = get_manager()
    item = mgr.require(id)
    if item["type"] != "setup" or item["id"] != mgr.active_id:
        return {"moved": False, "reason": "not the active setup"}
    state = mgr.module_state(item, "sun")
    if not state["enabled"]:
        return {"moved": False, "reason": "Sun module is off"}
    values = state["values"]
    ref = values.get("light")
    if light:
        n = rt.getNodeByName(str(light))
        ref = nodes.ref(n) if n is not None else None
    sun = nodes.resolve(ref) if ref else sun_mod.SunModule()._find()
    if sun is None:
        return {"moved": False, "reason": "no sun light"}
    if time is not None:
        loc = {k: values.get(k, sun_mod.LOCATION_DEFAULTS[k]) for k in sun_mod.LOCATION_KEYS}
        loc["time"] = str(time)
        azimuth, elevation = sun_mod.solve(loc)
    if azimuth is None or elevation is None:
        raise ValueError("give azimuth and elevation, or a time")
    with pymxs.undo(False):
        sun_mod.set_direction(sun, float(azimuth), float(elevation))
    rt.redrawViews()
    return {"moved": True, "azimuth": azimuth, "elevation": elevation}


def ui_set_values(id, module, values):
    """Like ui_set_value for several properties: one store, one apply, one undo step."""
    mgr = get_manager()
    m = registry.get(module)
    if m is None:
        raise KeyError("Unknown module %r" % module)
    item = mgr.require(id)
    mgr.set_values(item["id"], module, {k: _coerce(m, k, v) for k, v in dict(values).items()})
    return {"errors": _live(mgr, item, module)}


COMMANDS = {f.__name__: f for f in (ui_sun_path, ui_sun_preview, ui_set_values)}
