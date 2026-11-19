"""Xref Scenes: enable / show each XRef scene per setup (File > Reference > XRef Scene).

Values: {"xrefs": {file_path: {"enabled", "visible"}}}
API (CHECK IN MAX): xrefs.getXRefFileCount(), xrefs.getXRefFile i (1-based) -> XRefScene with
.filename, .disabled, .hidden. Only top-level XRef scenes are listed.
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register
from . import _util

COLUMNS = [Prop("enabled", "Enabled", "bool"), Prop("visible", "Visible", "bool")]


def xref_scenes():
    out = []
    for i in range(1, int(rt.xrefs.getXRefFileCount()) + 1):
        x = rt.xrefs.getXRefFile(i)
        if x is not None:
            out.append(x)
    return out


def key_of(x):
    return str(x.filename)


@register
class XrefScenesModule(Module):
    key = "xref_scenes"
    label = "XRef Scenes"
    order = 65
    category = "scene"
    column = None
    props = [Prop("xrefs", "XRef scenes", "table", columns=COLUMNS,
                  tip="Tick an XRef scene to store it on this setup.")]

    def available(self):
        try:
            return int(rt.xrefs.getXRefFileCount()) > 0
        except Exception:
            return False

    def capture(self):
        return {"xrefs": {key_of(x): {"enabled": not bool(x.disabled), "visible": not bool(x.hidden)}
                          for x in xref_scenes()}}

    def apply(self, values, context):
        by_key = {key_of(x).lower(): x for x in xref_scenes()}
        missing = []
        for k, row in (values.get("xrefs") or {}).items():
            if not isinstance(row, dict):
                continue
            x = by_key.get(k.lower())
            if x is None:
                missing.append(k)
                continue
            if row.get("enabled") is not None and bool(x.disabled) == bool(row["enabled"]):
                x.disabled = not row["enabled"]
            if row.get("visible") is not None and bool(x.hidden) == bool(row["visible"]):
                x.hidden = not row["visible"]
        _util.raise_missing("XRef scenes", missing)

    def summary(self, values):
        rows = [r for r in (values.get("xrefs") or {}).values() if isinstance(r, dict)]
        on = len([r for r in rows if r.get("enabled", True) and r.get("visible", True)])
        return "%d/%d on" % (on, len(rows)) if rows else ""
