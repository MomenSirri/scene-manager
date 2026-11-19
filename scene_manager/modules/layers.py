"""Layers: visible / renderable / frozen per layer.

Values: {"layers": {layer_name: {"on", "renderable", "frozen"}}, "others": "keep" | "hide"}
API: LayerManager.count, LayerManager.getLayer(i) (0-based), LayerManager.getLayerFromName(name),
     LayerProperties .on (= not hidden), .renderable, .isFrozen. Nested layers are listed by their own
     name (layer names are unique in Max); a child stays hidden while its parent is hidden.
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register
from . import _util

COLUMNS = [
    Prop("on", "Visible", "bool"),
    Prop("renderable", "Render", "bool"),
    Prop("frozen", "Frozen", "bool"),
]
_PROPS = {"on": "on", "renderable": "renderable", "frozen": "isFrozen"}


def all_layers():
    return [rt.LayerManager.getLayer(i) for i in range(rt.LayerManager.count)]


def read_layer(l):
    return {c: bool(rt.getProperty(l, p)) for c, p in _PROPS.items()}


@register
class LayersModule(Module):
    key = "layers"
    label = "Layers"
    order = 60
    category = "scene"
    column = "Layers"
    props = [
        Prop("layers", "Layers", "table", columns=COLUMNS,
             tip="Tick a layer to store it on this setup. Unticked layers inherit."),
        Prop("others", "Layers not listed", "enum", options=["keep", "hide"],
             tip="keep = leave other layers as they are; hide = hide every layer not listed"),
    ]

    def capture(self):
        return {"layers": {str(l.name): read_layer(l) for l in all_layers()}, "others": "keep"}

    def merge(self, base, over):
        out = super().merge(base, over)
        if (over or {}).get("others") == "hide" and isinstance((base or {}).get("layers"), dict):
            listed = set(((over or {}).get("layers") or {}).keys())
            rows = dict(out.get("layers") or {})
            for name, row in base["layers"].items():
                if name not in listed and isinstance(row, dict):
                    rows[name] = dict(row, on=False)
            out["layers"] = rows
        return out

    def differs(self, values, scene):
        return super().differs({k: v for k, v in values.items() if k != "others"}, scene)

    def apply(self, values, context):
        missing = []
        for name, row in (values.get("layers") or {}).items():
            if not isinstance(row, dict):
                continue
            l = rt.LayerManager.getLayerFromName(name)
            if l is None:
                missing.append(name)
                continue
            for col, p in _PROPS.items():
                if row.get(col) is not None and bool(rt.getProperty(l, p)) != bool(row[col]):
                    rt.setProperty(l, p, bool(row[col]))
        _util.raise_missing("Layers", missing)

    def summary(self, values):
        rows = [r for r in (values.get("layers") or {}).values() if isinstance(r, dict)]
        if not rows:
            return ""
        hidden = len([r for r in rows if r.get("on") is False])
        return "%d hidden" % hidden if hidden else "all visible"

    def actions(self):
        def show_all(v):
            return dict(v, layers={k: dict(r, on=True) for k, r in (v.get("layers") or {}).items()})

        def only_current(v):
            cur = str(rt.LayerManager.current.name) if getattr(rt.LayerManager, "current", None) else None
            return dict(v, layers={k: dict(r, on=(k == cur or k == "0")) for k, r in (v.get("layers") or {}).items()})

        def selection_layers(v):
            used = {str(n.layer.name) for n in rt.selection}
            return dict(v, layers={k: dict(r, on=k in used) for k, r in (v.get("layers") or {}).items()})
        return [("Show all layers", show_all), ("Only layers of the selection", selection_layers),
                ("Only the current layer (and 0)", only_current)]
