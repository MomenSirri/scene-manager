"""Dome light: which dome, on/off, HDRI, rotation, intensity, seen by camera.

V-Ray: VRayLight type Dome. Arnold: Arnold_Light type Skydome (CHECK index). Corona has no dome
light; use the Environment module in HDRI mode.
"""
from pymxs import runtime as rt

from ..core import nodes
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..env import renderers


@register
class DomeModule(Module):
    key = "dome"
    label = "Dome light"
    order = 45
    category = "light"
    column = "Dome"
    props = [
        Prop("light", "Dome light", "light", options=["dome"]),
        Prop("on", "On", "bool"),
        Prop("hdri", "HDRI", "hdri"),
        Prop("rotation", "Rotation", "float", minimum=-360, maximum=360, decimals=1, suffix="°",
             tip="Turns the dome light node around Z"),
        Prop("intensity", "Intensity", "float", minimum=0, maximum=10000, decimals=3, step=0.1),
        Prop("visible", "Seen by camera", "bool"),
    ]

    def capture(self):
        domes = renderers.list_domes()
        if not domes:
            return {"light": None}
        on = [d for d in domes if not rt.isProperty(d, rt.Name("on")) or d.on]
        node = (on or domes)[0]
        out = {"light": nodes.ref(node)}
        out.update(renderers.dome_read(node))
        return out

    def apply(self, values, context):
        if not values.get("light"):
            return
        node = nodes.resolve(values["light"])
        if node is None:
            raise RuntimeError("dome light '%s' not found" % values["light"].get("name"))
        renderers.dome_write(node, values)
        if values.get("on"):
            for other in renderers.list_domes():   # one dome per setup
                if other != node and rt.isProperty(other, rt.Name("on")):
                    other.on = False

    def summary(self, values):
        if not values.get("light"):
            return "none" if "light" in values else ""
        if values.get("on") is False:
            return "off"
        import os
        return os.path.splitext(os.path.basename(values.get("hdri") or ""))[0] or values["light"].get("name", "")

    def actions(self):
        def create(v):
            n = renderers.create_dome()
            return dict(v, light=nodes.ref(n), on=True)
        return [("Create dome light", create)]
