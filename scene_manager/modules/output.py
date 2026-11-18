"""Resolution and output: size, pixel aspect, output path with tokens."""
import os

from pymxs import runtime as rt

from ..core import tokens
from ..core.module_base import Module, Prop
from ..core.registry import register


@register
class OutputModule(Module):
    key = "output"
    label = "Resolution & Output"
    order = 20
    category = "camera"
    column = "Size"
    props = [
        Prop("width", "Width", "int", minimum=1, maximum=32768, suffix=" px"),
        Prop("height", "Height", "int", minimum=1, maximum=32768, suffix=" px"),
        Prop("pixel_aspect", "Pixel aspect", "float", minimum=0.01, maximum=100, decimals=3, step=0.1),
        Prop("save_file", "Save file", "bool"),
        Prop("path", "Output", "path",
             tip="Tokens:\n" + "\n".join("{%s}  %s" % kv for kv in tokens.TOKENS.items())),
    ]

    def capture(self):
        return {
            "width": int(rt.renderWidth),
            "height": int(rt.renderHeight),
            "pixel_aspect": round(float(rt.renderPixelAspect), 3),
            "save_file": bool(rt.rendSaveFile),
            "path": str(rt.rendOutputFilename or ""),
        }

    def apply(self, values, context):
        rt.renderWidth = int(values["width"])
        rt.renderHeight = int(values["height"])
        rt.renderPixelAspect = float(values.get("pixel_aspect", 1.0))
        path = tokens.resolve(values.get("path", ""), context)
        if path and values.get("save_file"):
            folder = os.path.dirname(path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder, exist_ok=True)
        rt.rendOutputFilename = path
        rt.rendSaveFile = bool(values.get("save_file")) and bool(path)

    def differs(self, values, scene):
        """A path with tokens is stored unresolved and applied resolved, so compare it as a pattern
        (each {token} matches any text) instead of flagging every token path as changed."""
        out = super().differs(values, scene)
        if "path" in out and tokens.matches(values.get("path"), scene.get("path")):
            out.discard("path")
        return out

    def summary(self, values):
        if "width" in values and "height" in values:
            return "%sx%s" % (values["width"], values["height"])
        return ""

    def actions(self):
        def scale(f):
            return lambda v: dict(v, width=max(1, int(v["width"] * f)), height=max(1, int(v["height"] * f)))
        return [("Double size", scale(2.0)), ("Half size", scale(0.5)),
                ("Swap width/height", lambda v: dict(v, width=v["height"], height=v["width"]))]
