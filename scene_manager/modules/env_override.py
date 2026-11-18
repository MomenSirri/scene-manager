"""GI and reflection environment overrides: light the scene or feed reflections with a different
HDRI than the one the camera sees. V-Ray and Corona; Arnold has no such override."""
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..env import renderers


def _read(texmap):
    info = renderers.read_hdri(texmap) if texmap is not None else None
    return (True, info[0], info[1], info[2]) if info else (texmap is not None, "", 0.0, 1.0)


@register
class EnvOverrideModule(Module):
    key = "env_override"
    label = "GI & reflection environment"
    order = 55   # after Environment, which sets the background these sit on
    category = "env"
    props = [
        Prop("gi_on", "GI override", "bool", tip="Light the scene with a different HDRI"),
        Prop("gi_hdri", "GI HDRI", "hdri"),
        Prop("gi_rotation", "GI rotation", "float", minimum=-360, maximum=360, decimals=1, suffix="°"),
        Prop("gi_intensity", "GI intensity", "float", minimum=0, maximum=1000, decimals=3, step=0.1),
        Prop("refl_on", "Reflection override", "bool", tip="Reflections and refractions see a different HDRI"),
        Prop("refl_hdri", "Reflection HDRI", "hdri"),
        Prop("refl_rotation", "Refl. rotation", "float", minimum=-360, maximum=360, decimals=1, suffix="°"),
        Prop("refl_intensity", "Refl. intensity", "float", minimum=0, maximum=1000, decimals=3, step=0.1),
    ]

    def capture(self):
        out = {}
        for pre, getter in (("gi", renderers.get_gi), ("refl", renderers.get_reflection)):
            on, path, rot, mult = _read(getter())
            out.update({pre + "_on": on, pre + "_hdri": path, pre + "_rotation": rot, pre + "_intensity": mult})
        return out

    def apply(self, values, context):
        for pre, setter in (("gi", renderers.set_gi), ("refl", renderers.set_reflection)):
            if values.get(pre + "_on") and values.get(pre + "_hdri"):
                m = renderers.make_hdri("hdri:" + pre, values[pre + "_hdri"], values.get(pre + "_rotation") or 0.0,
                                        1.0 if values.get(pre + "_intensity") is None else values[pre + "_intensity"])
                setter(m)
            elif values.get(pre + "_on") is False:
                setter(None)

    def summary(self, values):
        parts = [n for n, k in (("GI", "gi_on"), ("refl", "refl_on")) if values.get(k)]
        return " + ".join(parts) if parts else "off"
