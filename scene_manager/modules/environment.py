"""Environment: what the camera sees behind the scene. Modes None / Sky / HDRI / Custom.

sky    renderer sky map (V-Ray Sky, Corona Sky, Arnold Physical Sky) linked to the active sun
hdri   an HDRI file with rotation and intensity (VRayBitmap for V-Ray, Bitmaptexture elsewhere)
custom any map you built yourself; it is kept alive in the scene under its name
GI and reflection overrides are a separate module (env_override) so they can be switched alone.
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register
from ..env import mapstore, renderers
from . import sun as sun_mod

MODES = ["none", "sky", "hdri", "custom"]


def active_sun():
    suns = sun_mod.list_suns()
    on = [s for s in suns if not rt.isProperty(s, rt.Name("on")) or s.on]
    return (on or suns or [None])[0]


def describe_map(texmap):
    """(mode, hdri, rotation, intensity, custom_name) for a background map."""
    if texmap is None:
        return "none", "", 0.0, 1.0, ""
    if renderers.is_sky(texmap):
        return "sky", "", 0.0, 1.0, ""
    info = renderers.read_hdri(texmap)
    key = mapstore.key_of(texmap) or ""
    if info and (key.startswith("hdri:") or not key):
        return "hdri", info[0], info[1], info[2], ""
    return "custom", "", 0.0, 1.0, str(texmap.name)


def sky_for_scene():
    sun = active_sun()
    az = el = None
    if sun is not None:
        az, el, _ = sun_mod.get_direction(sun)
    return renderers.make_sky(sun, az, el)


@register
class EnvironmentModule(Module):
    key = "environment"
    label = "Environment"
    order = 50
    category = "env"
    column = "Env"
    props = [
        Prop("mode", "Mode", "enum", options=MODES),
        Prop("hdri", "HDRI", "hdri", tip="HDRI file (mode hdri). Browse opens the HDRI library."),
        Prop("rotation", "Rotation", "float", minimum=-360, maximum=360, decimals=1, suffix="°"),
        Prop("intensity", "Intensity", "float", minimum=0, maximum=1000, decimals=3, step=0.1),
        Prop("custom_map", "Custom map", "text",
             tip="Name of the map used in mode custom. Put a map in the Environment slot and Fetch."),
    ]

    def capture(self):
        mode, hdri, rot, mult, custom = describe_map(renderers.get_background())
        if mode == "custom":
            m = renderers.get_background()
            if mapstore.get("custom:" + custom) is None:
                mapstore.put("custom:" + custom, m)   # keep it alive for setups that use it
        return {"mode": mode, "hdri": hdri, "rotation": rot, "intensity": mult, "custom_map": custom}

    def apply(self, values, context):
        mode = values.get("mode") or "none"
        if mode == "none":
            renderers.set_background(None)
        elif mode == "sky":
            renderers.set_background(sky_for_scene())
        elif mode == "hdri":
            m = renderers.make_hdri("hdri:env", values.get("hdri"), values.get("rotation") or 0.0,
                                    1.0 if values.get("intensity") is None else values["intensity"])
            renderers.set_background(m)
        elif mode == "custom":
            name = values.get("custom_map") or ""
            m = mapstore.get("custom:" + name)
            if m is None:
                raise RuntimeError("custom map '%s' is not in the scene any more" % name)
            renderers.set_background(m)
        else:
            raise ValueError("unknown environment mode %r" % mode)

    def summary(self, values):
        mode = values.get("mode")
        if mode == "hdri":
            import os
            return os.path.splitext(os.path.basename(values.get("hdri") or ""))[0] or "hdri"
        if mode == "custom":
            return values.get("custom_map") or "custom"
        return mode or ""

    def actions(self):
        return [("Use sky", lambda v: dict(v, mode="sky")),
                ("Rotate HDRI +90°", lambda v: dict(v, rotation=((v.get("rotation") or 0) + 90) % 360)),
                ("Rotate HDRI -90°", lambda v: dict(v, rotation=((v.get("rotation") or 0) - 90) % 360))]
