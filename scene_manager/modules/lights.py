"""Lights: per setup on/off, intensity and colour of every light (suns and dome lights are left to
the Sun and Dome light modules).

Values: {"lights": {light_name: {"ref", "on", "intensity", "color"}}, "others": "keep" | "off"}
- Rows are merged per light and per column, so a folder can set every light and a setup only
  the few that differ.
- others = "off": every light the setup (with its folders) does not list is switched off.
Renderer property names differ; each column tries a list (CHECK IN MAX):
  on:        on                                   (Standard, Photometric, VRayLight, CoronaLight, Arnold_Light)
  intensity: multiplier | intensity               (VRayLight/Standard: multiplier; CoronaLight/Arnold/Photometric: intensity)
  colour:    color | rgb | colorDirect            (VRayLight/Arnold: color; Standard: rgb; CoronaLight: colorDirect? unsure)
"""
from pymxs import runtime as rt

from ..core import nodes
from ..core.module_base import Module, Prop
from ..core.registry import register
from . import _util

ON_PROPS = ["on"]
INTENSITY_PROPS = ["multiplier", "intensity"]
COLOR_PROPS = ["color", "rgb", "colorDirect"]

COLUMNS = [
    Prop("on", "On", "bool"),
    Prop("intensity", "Intensity", "float", minimum=0, maximum=1e7, decimals=3, step=0.1),
    Prop("color", "Colour", "color"),
]
_PROPS = {"on": ON_PROPS, "intensity": INTENSITY_PROPS, "color": COLOR_PROPS}


def is_sun(node):
    return "sun" in str(rt.classOf(node)).lower()


def _domes():
    """Dome lights belong to the Dome light module (M3), like suns belong to the Sun module."""
    try:
        from ..env import renderers
        return list(renderers.list_domes())
    except Exception:
        return []


def managed_lights():
    domes = _domes()
    return [l for l in nodes.list_lights() if not is_sun(l) and l not in domes]


def read_light(l):
    row = {"ref": nodes.ref(l)}
    for col, names in _PROPS.items():
        p = _util.first_prop(l, names)
        row[col] = _util.as_jsonable(rt.getProperty(l, p)) if p else None
    if row.get("on") is not None:
        row["on"] = bool(row["on"])
    return row


def find(name, row):
    n = nodes.resolve(row.get("ref")) if isinstance(row, dict) and row.get("ref") else None
    return n if n is not None else rt.getNodeByName(name)


@register
class LightsModule(Module):
    key = "lights"
    label = "Lights"
    order = 45  # after Sun (40), so the sun's "other suns off" is not undone
    category = "light"
    column = "Lights"
    props = [
        Prop("lights", "Lights", "table", columns=COLUMNS,
             tip="Tick a light to store it on this setup. Unticked lights inherit from the folder "
                 "(or the baseline / current scene)."),
        Prop("others", "Lights not listed", "enum", options=["keep", "off"],
             tip="keep = leave other lights as they are; off = switch every light not listed off"),
    ]

    def capture(self):
        return {"lights": {str(l.name): read_light(l) for l in managed_lights()}, "others": "keep"}

    def merge(self, base, over):
        out = super().merge(base, over)
        if (over or {}).get("others") == "off" and isinstance((base or {}).get("lights"), dict):
            listed = set(((over or {}).get("lights") or {}).keys())
            rows = dict(out.get("lights") or {})
            for name, row in (base.get("lights") or {}).items():
                if name not in listed and isinstance(row, dict):
                    rows[name] = dict(row, on=False)
            out["lights"] = rows
        return out

    def differs(self, values, scene):
        return super().differs({k: v for k, v in values.items() if k != "others"}, scene)

    def apply(self, values, context):
        missing = []
        for name, row in (values.get("lights") or {}).items():
            if not isinstance(row, dict):
                continue
            l = find(name, row)
            if l is None:
                missing.append(name)
                continue
            for col, names in _PROPS.items():
                v = row.get(col)
                p = _util.first_prop(l, names) if v is not None else None
                if p:
                    _util.set_value(l, p, bool(v) if col == "on" else v)
        _util.raise_missing("Lights", missing)

    def summary(self, values):
        rows = [r for r in (values.get("lights") or {}).values() if isinstance(r, dict)]
        if not rows:
            return ""
        on = len([r for r in rows if r.get("on")])
        return "%d/%d on" % (on, len(rows)) + (" (others off)" if values.get("others") == "off" else "")

    def actions(self):
        def all_on(v):
            return dict(v, lights={k: dict(r, on=True) for k, r in (v.get("lights") or {}).items()})

        def all_off(v):
            return dict(v, lights={k: dict(r, on=False) for k, r in (v.get("lights") or {}).items()})

        def only_selected(v):
            sel = {str(n.name) for n in rt.selection}
            return dict(v, lights={k: dict(r, on=k in sel) for k, r in (v.get("lights") or {}).items()})
        return [("All lights on", all_on), ("All lights off", all_off),
                ("Only selected lights on", only_selected)]
