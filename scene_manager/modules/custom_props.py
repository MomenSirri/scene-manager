"""Custom properties: any property of any node, material, modifier, the renderer or the environment.

Each row stores where the value lives and the value:
    {"target": "node" | "renderer" | "environment" | "maxscript",
     "node": node ref (target node), "path": "material.diffuse_map" (optional, dot path from the target)
             or a MAXScript expression (target maxscript, e.g. sceneMaterials["Glass"]),
     "prop": "glossiness", "value": 0.5}
Row keys are readable addresses like "Box001.material.glossiness". Applied last, so a custom
property overrides every other module.
"""
from pymxs import runtime as rt

from ..core import nodes
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops


def resolve_target(row):
    t = row.get("target", "node")
    if t == "renderer":
        obj = rt.renderers.current
    elif t == "environment":
        obj = rt.environmentMap
    elif t == "maxscript":
        return rt.execute(row.get("path") or "undefined")
    else:
        obj = nodes.resolve(row.get("node"))
        if obj is None:
            raise RuntimeError("node '%s' not found" % (row.get("node") or {}).get("name"))
    for part in [p for p in (row.get("path") or "").split(".") if p]:
        if obj is None:
            break
        if part.isdigit() and hasattr(obj, "__getitem__"):
            obj = obj[int(part)]   # e.g. modifiers.1
        else:
            obj = rt.getProperty(obj, rt.Name(part))
    if obj is None:
        raise RuntimeError("nothing at %s" % address(row))
    return obj


def address(row):
    t = row.get("target", "node")
    head = (row.get("node") or {}).get("name", "?") if t == "node" else t
    if t == "maxscript":
        return "%s.%s" % (row.get("path"), row.get("prop"))
    return ".".join(x for x in (head, row.get("path"), row.get("prop")) if x)


def make_row(target, prop, path="", node_name=None, value=None):
    """Build a row; reads the current value when value is None."""
    row = {"target": target, "path": path or "", "prop": prop}
    if target == "node":
        n = rt.getNodeByName(node_name or "")
        if n is None:
            raise KeyError("No node named %r" % node_name)
        row["node"] = nodes.ref(n)
    obj = resolve_target(row)
    if rprops.find_prop(obj, [prop]) is None:
        raise KeyError("%s has no property %r" % (address(dict(row, prop="")).rstrip("."), prop))
    row["value"] = value if value is not None else rprops.read(obj, [prop])
    return address(row), row


@register
class CustomPropsModule(Module):
    key = "custom_props"
    label = "Custom properties"
    order = 95
    category = "render"
    props = [Prop("rows", "Properties", "cprops",
                  tip="Any property of any object. Add rows with + (node, property) or ask Claude (add_custom_property).")]

    def available(self):
        return False

    def capture_baseline(self, mgr):
        return None   # not in the scene baseline: rows are chosen per setup; nothing to restore

    def capture(self):
        return {}   # which properties to keep is chosen per setup; use "Refresh values" to re-read them

    def merge(self, base, over):
        return rprops.merge_module(base, over, row_props=("rows",))

    def apply(self, values, context):
        errors = []
        for key, row in (values.get("rows") or {}).items():
            if not isinstance(row, dict) or row.get("value") is None:
                continue
            try:
                obj = resolve_target(row)
                if rprops.write(obj, [row["prop"]], row["value"]) is None:
                    errors.append("%s: no such property" % key)
            except Exception as e:
                errors.append("%s: %s" % (key, e))
        if errors:
            raise RuntimeError("; ".join(errors))

    def differs(self, values, scene):
        for row in (values.get("rows") or {}).values():
            try:
                now = rprops.read(resolve_target(row), [row["prop"]])
            except Exception:
                return {"rows"}
            if not rprops._same(now, row.get("value")):
                return {"rows"}
        return set()

    def summary(self, values):
        n = len(values.get("rows") or {})
        return "%d properties" % n if n else ""

    def actions(self):
        def refresh(v):
            rows = {}
            for k, row in (v.get("rows") or {}).items():
                row = dict(row)
                try:
                    row["value"] = rprops.read(resolve_target(row), [row["prop"]])
                except Exception:
                    pass
                rows[k] = row
            return dict(v, rows=rows)
        return [("Refresh values from scene", refresh)]
