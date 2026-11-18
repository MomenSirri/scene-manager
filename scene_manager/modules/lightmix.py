"""LightMix baked into the scene: per light group on/off and an intensity multiplier.

Groups come from the light-select render elements (V-Ray VRayLightSelect, Corona LightSelect);
lights not in any light-select element get a group of their own. The multiplier is applied to each
light's intensity at capture time ("base"), so the render matches the mix in every renderer,
batch render and farm, without the frame buffer. V-Ray's interactive VFB LightMix is stored by
Post-production (VFB layers) instead. LightMix applies after Lights (M2), so for lights in a group it wins.

CHECK IN MAX: light list property on light-select elements (tried: lights, includedNodes, nodes) and
light intensity property (tried: multiplier, intensity).
"""
from pymxs import runtime as rt

from ..core import nodes
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops
from . import render_elements

INTENSITY = ["multiplier", "intensity"]
MEMBER_PROPS = ["lights", "includedNodes", "nodes", "includeList"]


def _is_light_select(el):
    c = str(rt.classOf(el)).lower()
    return "lightselect" in c or "light_select" in c


def groups():
    """{group name: [light nodes]}"""
    out, grouped = {}, set()
    try:
        els = render_elements.elements()
    except Exception:
        els = []
    for _, el in els:
        if not _is_light_select(el):
            continue
        p = rprops.find_prop(el, MEMBER_PROPS)
        members = [n for n in (rt.getProperty(el, rt.Name(p)) or [])] if p else []
        members = [n for n in members if n is not None and nodes.is_light(n)]
        out[render_elements.element_name(el)] = members
        grouped.update(str(n.name) for n in members)
    for l in nodes.list_lights():
        if str(l.name) not in grouped:
            out[str(l.name)] = [l]
    return out


def _intensity(light):
    return rprops.read(light, INTENSITY)


@register
class LightMixModule(Module):
    key = "lightmix"
    label = "LightMix"
    order = 70
    category = "light"
    props = [
        Prop("groups", "Groups", "lmgroups",
             tip="Per light group: on, and a multiplier on the light intensity stored in Base"),
        Prop("base", "Base intensity", "rdiff",
             tip="Light intensities when the mix was fetched. Multipliers scale these values."),
    ]

    def available(self):
        return False   # add with + Module

    def capture_baseline(self, mgr):
        return None   # not in the scene baseline: would re-apply every light's on/intensity and undo the Lights module

    def capture(self):
        g = groups()
        base, rows = {}, {}
        for name, members in g.items():
            on = any(bool(l.on) for l in members if rt.isProperty(l, rt.Name("on"))) if members else True
            rows[name] = {"on": on, "mult": 1.0}
            for l in members:
                v = _intensity(l)
                if v is not None:
                    base[str(l.name)] = v
        return {"groups": rows, "base": base}

    def merge(self, base, over):
        return rprops.merge_module(base, over, row_props=("groups",), dict_props=("base",))

    def apply(self, values, context):
        rows = values.get("groups") or {}
        base = values.get("base") or {}
        missing = []
        g = groups()
        for name, row in rows.items():
            if name not in g:
                missing.append(name)
                continue
            for l in g[name]:
                if row.get("on") is not None and rt.isProperty(l, rt.Name("on")):
                    l.on = bool(row["on"])
                b = base.get(str(l.name))
                if b is not None and row.get("mult") is not None:
                    rprops.write(l, INTENSITY, float(b) * float(row["mult"]))
        if missing:
            raise RuntimeError("groups not found: %s" % ", ".join(missing))

    def summary(self, values):
        rows = values.get("groups") or {}
        changed = [n for n, r in rows.items() if r.get("on") is False or abs(float(r.get("mult", 1)) - 1) > 1e-6]
        return "%d of %d changed" % (len(changed), len(rows)) if rows else ""
