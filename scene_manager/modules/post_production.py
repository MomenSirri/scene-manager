"""Post-production: V-Ray frame buffer layers (incl. LightMix layer) and Corona tone mapping, per setup.

V-Ray 5+ (CHECK IN MAX):  lm = (vfbControl #getLayerMgr)[1];  lm.saveLayersToJSON() -> string;
lm.loadLayersFromJSON <string>.  The whole layer tree is stored as JSON text inside the setup.
Corona: every JSON-safe renderer property whose name starts with colorMap_ / bloomGlare_ or contains
"tonemap". The Corona 8+ tone-mapping operator stack itself is a MAXScript object, not a plain value:
if your Corona keeps its operators only in that stack, this card stores the scalar values only (CHECK).
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops

CORONA_PREFIXES = ("colorMap_", "colormap_", "bloomGlare_", "bloomglare_")


def vfb_layer_manager():
    try:
        r = rt.execute("(vfbControl #getLayerMgr)[1]")
    except Exception:
        return None
    return r


def vfb_layers_json():
    lm = vfb_layer_manager()
    if lm is None:
        return None
    s = lm.saveLayersToJSON()
    return str(s) if s else None


def load_vfb_layers(text):
    lm = vfb_layer_manager()
    if lm is None:
        raise RuntimeError("V-Ray frame buffer layer manager not available")
    if not lm.loadLayersFromJSON(text):
        raise RuntimeError("V-Ray did not accept the stored VFB layers")


def corona_values():
    r = rprops.current()
    return rprops.snapshot(r, include=lambda n: n.startswith(CORONA_PREFIXES) or "tonemap" in n.lower())


@register
class PostProductionModule(Module):
    key = "post"
    label = "Post-production"
    order = 65
    category = "render"
    props = [
        Prop("vfb_layers", "V-Ray VFB layers", "blob",
             tip="V-Ray layer tree (colour corrections, LightMix, etc.). Fetch from scene to store the current VFB."),
        Prop("corona_tonemap", "Corona tone mapping", "rdiff",
             tip="Corona tone mapping values. Fetch from scene to store the current ones."),
    ]
    props[0].kinds = ("vray", "vray_gpu")
    props[1].kinds = ("corona",)

    def installed(self):
        return any(p.installed() for p in self.props)

    def available(self):
        return False   # add with + Module, then Fetch

    def capture_baseline(self, mgr):
        return None   # not in the scene baseline: VFB layer JSON is large and reloading the VFB on every activation is slow

    def capture(self):
        kind = rprops.current_kind()
        if kind in ("vray", "vray_gpu"):
            v = vfb_layers_json()
            return {"vfb_layers": v} if v else {}
        if kind == "corona":
            return {"corona_tonemap": corona_values()}
        return {}

    def apply(self, values, context):
        kind = rprops.current_kind()
        if kind in ("vray", "vray_gpu") and values.get("vfb_layers"):
            if values["vfb_layers"] != vfb_layers_json():
                load_vfb_layers(values["vfb_layers"])
        elif kind == "corona" and values.get("corona_tonemap"):
            r = rprops.current()
            for p, v in values["corona_tonemap"].items():
                rprops.write(r, [p], v)

    def summary(self, values):
        bits = []
        if values.get("vfb_layers"):
            bits.append("VFB layers")
        if values.get("corona_tonemap"):
            bits.append("tone mapping")
        return ", ".join(bits)

    def actions(self):
        return [("Clear stored post-production", lambda v: dict(v, vfb_layers="", corona_tonemap={}))]
