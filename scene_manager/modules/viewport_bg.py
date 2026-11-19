"""Viewport background of the active viewport: gradient, solid colour, environment, or an image.

Viewport-only (does not change the render). The calls used are CHECK items, listed in BG_CALLS.
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register

MODES = ["gradient", "solid", "environment", "image"]

# MAXScript per mode (CHECK in Max 2025+). %s is the image path.
BG_CALLS = {
    "gradient": "viewport.EnableSolidBackgroundColorMode false; viewport.DispBkgImage = false",
    "solid": "viewport.EnableSolidBackgroundColorMode true; viewport.DispBkgImage = false",
    "environment": "viewport.EnableSolidBackgroundColorMode false; backgroundImageFileName = \"\"; "
                   "viewport.DispBkgImage = true",
    "image": "viewport.EnableSolidBackgroundColorMode false; backgroundImageFileName = @\"%s\"; "
             "setBkgImageAspect #output; viewport.DispBkgImage = true",
}


def _ms(expr, default=None):
    try:
        return rt.execute(expr)
    except Exception:
        return default


@register
class ViewportBackgroundModule(Module):
    key = "viewport_bg"
    label = "Viewport background"
    order = 60
    category = "env"
    props = [
        Prop("mode", "Background", "enum", options=MODES),
        Prop("image", "Image", "image", tip="Image file for mode image"),
    ]

    def capture(self):
        shown = bool(_ms("viewport.DispBkgImage", False))
        image = str(_ms("backgroundImageFileName", "") or "")
        if shown:
            mode = "image" if image else "environment"
        else:
            mode = "solid" if bool(_ms("viewport.IsSolidBackgroundColorMode()", False)) else "gradient"
        return {"mode": mode, "image": image}

    def apply(self, values, context):
        mode = values.get("mode") or "gradient"
        if mode not in BG_CALLS:
            raise ValueError("unknown viewport background %r" % mode)
        code = BG_CALLS[mode]
        if mode == "image":
            if not values.get("image"):
                raise RuntimeError("no image file set")
            code = code % values["image"]
        rt.execute(code)
        rt.completeRedraw()

    def summary(self, values):
        return values.get("mode", "")
