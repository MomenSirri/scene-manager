"""Render preset: load a .rps file first; every other module then overrides it.

Max API (CHECK IN MAX): renderPresets.LoadAll <index> <file>, renderPresets.Load <index> <file> <bitArray>,
renderPresets.LoadCategories <file> -> array of category names, renderPresets.SaveAll <index> <file>.
Index 0 = production renderer.
"""
import os

from pymxs import runtime as rt

from ..core import tokens
from ..core.module_base import Module, Prop
from ..core.registry import register


def load(path, keep_common=True):
    if not os.path.isfile(path):
        raise RuntimeError("preset not found: %s" % path)
    if not keep_common:
        rt.renderPresets.LoadAll(0, path)
        return
    cats = [str(c) for c in (rt.renderPresets.LoadCategories(path) or [])]
    idx = [i + 1 for i, c in enumerate(cats) if c.lower() != "common"]   # bitArray is 1-based
    if not idx:
        return
    bits = rt.execute("#{%s}" % ",".join(str(i) for i in idx))
    rt.renderPresets.Load(0, path, bits)


def save(path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    rt.renderPresets.SaveAll(0, path)
    return path


@register
class RenderPresetModule(Module):
    key = "render_preset"
    label = "Render preset"
    order = 5     # first: everything after it overrides the preset
    category = "render"
    props = [
        Prop("file", "Preset (.rps)", "rps", tip="Loaded before the other modules. Tokens like {project} work."),
        Prop("keep_common", "Keep Common tab", "bool",
             tip="On: load every category except Common, so resolution, output and frames stay as set"),
    ]

    def available(self):
        return False   # add with + Module

    def capture(self):
        return {"keep_common": True}   # the loaded preset cannot be read back from the scene

    def apply(self, values, context):
        f = (values.get("file") or "").strip()
        if f:
            load(tokens.resolve(f, context), values.get("keep_common", True) is not False)

    def differs(self, values, scene):
        return set()

    def summary(self, values):
        return os.path.splitext(os.path.basename(values.get("file") or ""))[0]
