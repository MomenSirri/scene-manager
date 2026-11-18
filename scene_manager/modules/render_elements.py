"""Render elements on/off per setup, element file names from tokens, V-Ray channels and raw output.

Max API: maxOps.GetCurRenderElementMgr() -> NumRenderElements(), GetRenderElement i, .elementName, .enabled,
SetRenderElementFilename i path, GetElementsActive(), SetElementsActive bool.
V-Ray renderer properties (CHECK IN MAX): output_splitgbuffer, output_splitfilename, output_saveRawFile, output_rawFileName.
"""
import os

from pymxs import runtime as rt

from ..core import tokens
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops

VRAY_PROPS = {
    "vray_split": ["output_splitgbuffer"],
    "vray_split_path": ["output_splitfilename", "output_splitFileName"],
    "vray_raw": ["output_saveRawFile"],
    "vray_raw_path": ["output_rawFileName", "output_rawfilename"],
}


def manager():
    return rt.maxOps.GetCurRenderElementMgr()


def elements():
    """[(index, element)] for the production renderer."""
    re = manager()
    return [(i, re.GetRenderElement(i)) for i in range(int(re.NumRenderElements()))]


def element_name(el):
    return str(el.elementName)


def _is_vray():
    return rprops.current_kind() in ("vray", "vray_gpu")


def _ensure_folder(path):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)


@register
class RenderElementsModule(Module):
    key = "render_elements"
    label = "Render elements"
    order = 60
    category = "render"
    column = None
    props = [
        Prop("active", "Elements active", "bool", tip="Master switch: render elements at all"),
        Prop("elements", "Elements", "toggles", tip="On/off per element. Elements not listed are left alone."),
        Prop("element_path", "Element files", "path",
             tip="Optional file name for every element. Tokens as in Output plus {element}, e.g.\n"
                 "D:/renders/{scene}/{setup}/{setup}_{element}.exr"),
        Prop("vray_split", "V-Ray separate channels", "bool", tip="V-Ray only: save render channels as separate files"),
        Prop("vray_split_path", "V-Ray channels file", "path", tip="V-Ray only. Tokens work"),
        Prop("vray_raw", "V-Ray raw image", "bool", tip="V-Ray only: save the raw image file (e.g. multichannel .exr)"),
        Prop("vray_raw_path", "V-Ray raw file", "path", tip="V-Ray only. Tokens work"),
    ]

    def capture(self):
        re = manager()
        out = {"active": bool(re.GetElementsActive()),
               "elements": {element_name(el): bool(el.enabled) for _, el in elements()}}
        if _is_vray():
            r = rprops.current()
            for k, names in VRAY_PROPS.items():
                v = rprops.read(r, names)
                if v is not None:
                    out[k] = v
        return out

    def merge(self, base, over):
        return rprops.merge_module(base, over, dict_props=("elements",))

    def apply(self, values, context):
        re = manager()
        if values.get("active") is not None:
            re.SetElementsActive(bool(values["active"]))
        wanted = values.get("elements") or {}
        template = (values.get("element_path") or "").strip()
        missing = set(wanted)
        for i, el in elements():
            name = element_name(el)
            if name in wanted:
                el.enabled = bool(wanted[name])
                missing.discard(name)
            if template:
                path = tokens.resolve(template, dict(context, element=name))
                if el.enabled:
                    _ensure_folder(path)
                re.SetRenderElementFilename(i, path)
        if _is_vray():
            r = rprops.current()
            for k in ("vray_split", "vray_raw"):
                if values.get(k) is not None:
                    rprops.write(r, VRAY_PROPS[k], bool(values[k]))
            for k, flag in (("vray_split_path", "vray_split"), ("vray_raw_path", "vray_raw")):
                if values.get(k):
                    path = tokens.resolve(values[k], context)
                    if values.get(flag):
                        _ensure_folder(path)
                    rprops.write(r, VRAY_PROPS[k], path)
        if missing:
            raise RuntimeError("not in the scene: %s" % ", ".join(sorted(missing)))

    def summary(self, values):
        els = values.get("elements") or {}
        if values.get("active") is False:
            return "off"
        return "%d/%d on" % (sum(1 for v in els.values() if v), len(els)) if els else ""

    def actions(self):
        def all_to(on):
            return lambda v: dict(v, elements={k: on for k in (v.get("elements") or {})})
        return [("All elements on", all_to(True)), ("All elements off", all_to(False))]
