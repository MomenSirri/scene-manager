"""Sun: which sun light, on/off, direction (azimuth/elevation or date/time/location), intensity,
shadows and shadow softness.

Works on targeted or free sun lights (V-Ray Sun, Corona Sun, any light with 'sun' in its class).
A sun driven by a Daylight system or Sun Positioner is reported, not moved.
Renderer property names differ, so each value tries a list of known names (CHECK IN MAX).
"""
import datetime
import json
import math

from pymxs import runtime as rt

from ..core import nodes
from ..env import solar
from ..core.module_base import Module, Prop
from ..core.registry import register

INTENSITY_PROPS = ["intensity_multiplier", "intensity", "multiplier"]   # VRaySun, CoronaSun, generic
SIZE_PROPS = ["size_multiplier", "sizeMultiplier", "size"]               # VRaySun, CoronaSun (check), generic
SHADOW_PROPS = ["shadows", "castShadows", "cast_shadows"]                 # CHECK per renderer
POSITION_MODES = ["angles", "date_time"]
USER_PROP = "sm_sun_position"   # date/time/location written on the sun node, so capture can read it back
LOCATION_KEYS = ("date", "time", "latitude", "longitude", "utc_offset", "north")
LOCATION_DEFAULTS = {"date": "2026-06-21", "time": "12:00", "latitude": 51.51, "longitude": -0.13,
                     "utc_offset": 0.0, "north": 0.0}


def is_sun(node):
    return nodes.is_light(node) and "sun" in str(rt.classOf(node)).lower()


def list_suns():
    return [l for l in nodes.list_lights() if is_sun(l)]


def _prop(node, names):
    for n in names:
        if rt.isProperty(node, rt.Name(n)):
            return n
    return None


def read_location(sun):
    """Date/time/location last applied to this sun by Scene Manager, or None."""
    try:
        raw = rt.getUserProp(sun, USER_PROP)
    except Exception:
        return None
    if not raw or str(raw) == "undefined":
        return None
    try:
        return json.loads(str(raw).replace("'", '"'))
    except ValueError:
        return None


def write_location(sun, loc):
    # single quotes: 3ds Max user properties do not like double quotes
    rt.setUserProp(sun, USER_PROP, json.dumps({k: loc[k] for k in LOCATION_KEYS}).replace('"', "'"))


def solve(loc):
    """Scene (azimuth, elevation) for a location dict."""
    az, el = solar.sun_position(loc["date"], loc["time"], float(loc["latitude"]), float(loc["longitude"]),
                                float(loc.get("utc_offset", 0.0)))
    return round(solar.scene_azimuth(az, loc.get("north", 0.0)), 2), round(el, 2)


def _center(sun):
    if rt.isProperty(sun, rt.Name("target")) and sun.target is not None:
        return sun.target.pos, True
    return rt.Point3(0, 0, 0), False


def get_direction(sun):
    c, _ = _center(sun)
    dx, dy, dz = float(sun.pos.x - c.x), float(sun.pos.y - c.y), float(sun.pos.z - c.z)
    az = math.degrees(math.atan2(dx, dy)) % 360.0
    el = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return round(az, 2), round(el, 2), math.sqrt(dx * dx + dy * dy + dz * dz)


def set_direction(sun, azimuth, elevation, distance=None):
    """Azimuth 0 = north (+Y), 90 = east (+X). Elevation 0 = horizon, 90 = overhead."""
    ctrl = str(rt.classOf(sun.controller)).lower() if sun.controller is not None else ""
    if ctrl and ctrl != "prs":
        raise RuntimeError("%s is driven by %s (Daylight system or Sun Positioner). Change that system instead."
                           % (sun.name, ctrl))
    c, _ = _center(sun)
    if distance is None:
        distance = get_direction(sun)[2] or 10000.0
    az, el = math.radians(azimuth), math.radians(elevation)
    sun.pos = rt.Point3(float(c.x) + distance * math.cos(el) * math.sin(az),
                        float(c.y) + distance * math.cos(el) * math.cos(az),
                        float(c.z) + distance * math.sin(el))


@register
class SunModule(Module):
    key = "sun"
    label = "Sun"
    order = 40
    category = "light"
    column = "Sun"
    props = [
        Prop("light", "Sun light", "sunlight"),
        Prop("on", "On", "bool"),
        Prop("azimuth", "Azimuth", "float", minimum=0, maximum=360, decimals=1, suffix="°",
             tip="0 = north (+Y), 90 = east (+X)"),
        Prop("elevation", "Elevation", "float", minimum=-90, maximum=90, decimals=1, suffix="°"),
        Prop("intensity", "Intensity", "float", minimum=0, maximum=1000, decimals=3, step=0.1),
        Prop("size", "Shadow softness", "float", minimum=0, maximum=1000, decimals=2, step=0.5,
             tip="Sun size multiplier: bigger = softer shadows"),
        Prop("shadows", "Shadows", "bool"),
        Prop("position", "Position by", "enum", options=POSITION_MODES,
             tip="angles: azimuth/elevation above.\ndate_time: computed from date, time and location below."),
        Prop("date", "Date", "text", tip="YYYY-MM-DD"),
        Prop("time", "Time", "text", tip="HH:MM local clock time"),
        Prop("latitude", "Latitude", "float", minimum=-90, maximum=90, decimals=4, suffix="°", tip="North positive"),
        Prop("longitude", "Longitude", "float", minimum=-180, maximum=180, decimals=4, suffix="°", tip="East positive"),
        Prop("utc_offset", "UTC offset", "float", minimum=-14, maximum=14, decimals=2, step=0.5, suffix=" h",
             tip="Time zone incl. daylight saving, e.g. London summer = 1"),
        Prop("north", "North", "float", minimum=-360, maximum=360, decimals=1, suffix="°",
             tip="Where true north points in the scene, degrees clockwise from +Y"),
    ]

    def _find(self, ref=None):
        if ref:
            return nodes.resolve(ref)
        suns = list_suns()
        on = [s for s in suns if not rt.isProperty(s, rt.Name("on")) or s.on]
        return (on or suns or [None])[0]

    def capture(self):
        sun = self._find()
        if sun is None:
            return {"light": None}
        az, el, _ = get_direction(sun)
        ip, sp, shp = _prop(sun, INTENSITY_PROPS), _prop(sun, SIZE_PROPS), _prop(sun, SHADOW_PROPS)
        out = {
            "light": nodes.ref(sun),
            "on": bool(sun.on) if rt.isProperty(sun, rt.Name("on")) else True,
            "azimuth": az,
            "elevation": el,
            "intensity": round(float(rt.getProperty(sun, ip)), 4) if ip else None,
            "size": round(float(rt.getProperty(sun, sp)), 4) if sp else None,
            "shadows": bool(rt.getProperty(sun, shp)) if shp else None,
            "position": "angles",
        }
        loc = read_location(sun)
        out.update({k: (loc or {}).get(k, LOCATION_DEFAULTS[k]) for k in LOCATION_KEYS})
        if loc:
            try:
                saz, sel = solve(out)
                if abs((saz - az + 180) % 360 - 180) < 0.05 and abs(sel - el) < 0.05:
                    out["position"] = "date_time"   # sun still sits where the date/time put it
            except Exception:
                pass
        return out

    def apply(self, values, context):
        if not values.get("light"):
            return
        sun = nodes.resolve(values["light"])
        if sun is None:
            raise RuntimeError("sun '%s' not found" % values["light"].get("name"))
        if rt.isProperty(sun, rt.Name("on")) and values.get("on") is not None:
            sun.on = bool(values["on"])
        if values.get("on", True):
            # one sun per setup: switch the other suns off
            for other in list_suns():
                if other != sun and rt.isProperty(other, rt.Name("on")):
                    other.on = False
        if values.get("position") == "date_time":
            loc = {k: values.get(k, LOCATION_DEFAULTS[k]) for k in LOCATION_KEYS}
            values = dict(values)
            values["azimuth"], values["elevation"] = solve(loc)
            write_location(sun, loc)
        if values.get("azimuth") is not None and values.get("elevation") is not None:
            az, el, _ = get_direction(sun)
            if abs(az - values["azimuth"]) > 0.01 or abs(el - values["elevation"]) > 0.01:
                set_direction(sun, float(values["azimuth"]), float(values["elevation"]))
        for key, names in (("intensity", INTENSITY_PROPS), ("size", SIZE_PROPS)):
            p = _prop(sun, names)
            if p and values.get(key) is not None:
                rt.setProperty(sun, p, float(values[key]))
        p = _prop(sun, SHADOW_PROPS)
        if p and values.get("shadows") is not None:
            rt.setProperty(sun, p, bool(values["shadows"]))

    def summary(self, values):
        if values.get("light") is None and "light" in values:
            return "none"
        if values.get("on") is False:
            return "off"
        if values.get("position") == "date_time":
            try:
                d = solar.parse_date(values.get("date", LOCATION_DEFAULTS["date"]))
                return "%s %s" % (d.strftime("%d %b"), values.get("time", ""))
            except ValueError:
                return "date?"
        if values.get("azimuth") is not None:
            return "%.0f° / %.0f°" % (values["azimuth"], values.get("elevation", 0))
        return ""

    def actions(self):
        def now(v):
            t = datetime.datetime.now()
            return dict(v, position="date_time", date=t.strftime("%Y-%m-%d"), time=t.strftime("%H:%M"))

        def golden(v):
            # about one hour before sunset on the stored date: scan the afternoon for elevation ~6 degrees
            loc = {k: v.get(k, LOCATION_DEFAULTS[k]) for k in LOCATION_KEYS}
            best = None
            for minute in range(12 * 60, 22 * 60, 5):
                loc["time"] = "%02d:%02d" % divmod(minute, 60)
                el = solve(loc)[1]
                if best is None or abs(el - 6.0) < best[0]:
                    best = (abs(el - 6.0), loc["time"])
            return dict(v, position="date_time", time=best[1])

        return [("Sun position: now", now), ("Sun position: golden hour", golden)]
