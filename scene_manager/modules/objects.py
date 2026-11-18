"""Objects: visibility and render properties by rule, so it scales past a handful of objects.

Values: {"rules": {target: {column: True | False | None}}}   None = leave that property alone.
Targets:
  set:Name        a named selection set (Create Selection Set in the main toolbar)
  layer:Name      every object on a layer
  pattern:Tree_*  object names matching a wildcard (* and ?), case-insensitive
  node:Name       one object (the row also keeps a name+handle ref so renames are followed)
Rules apply from broad to specific: pattern, layer, set, node. So "pattern:Tree_*" hidden plus
"node:Tree_07" visible shows only Tree_07.

Determinism: before applying, objects changed by the previous setup are put back. With a scene
baseline (Setups menu > Capture scene baseline) the original state of every rule target is
stored in the .max; without it the module remembers the state for this 3ds Max session only.

Node properties (CHECK IN MAX, all standard INode properties): isHidden, renderable, xray,
castShadows, primaryVisibility, secondaryVisibility, isFrozen. Named selection sets:
getNumNamedSelSets(), getNamedSelSetName(i), getNamedSelSetItemCount(i), getNamedSelSetItem(i, j) (1-based).
"""
import fnmatch

from pymxs import runtime as rt

from ..core import nodes
from ..core.module_base import Module, Prop
from ..core.registry import register
from . import _util

COLUMNS = [
    Prop("visible", "Visible", "tristate"),
    Prop("renderable", "Render", "tristate"),
    Prop("camera", "To camera", "tristate", tip="Visible to camera (primary visibility)"),
    Prop("reflections", "In reflections", "tristate", tip="Visible to reflections/refractions (secondary visibility)"),
    Prop("cast_shadows", "Shadows", "tristate", tip="Cast shadows"),
    Prop("see_through", "See-through", "tristate", tip="Viewport X-ray"),
    Prop("frozen", "Frozen", "tristate"),
]
# column -> (node property, inverted)
_PROPS = {
    "visible": ("isHidden", True),
    "renderable": ("renderable", False),
    "camera": ("primaryVisibility", False),
    "reflections": ("secondaryVisibility", False),
    "cast_shadows": ("castShadows", False),
    "see_through": ("xray", False),
    "frozen": ("isFrozen", False),
}
PRECEDENCE = {"pattern": 0, "layer": 1, "set": 2, "node": 3}

# node name -> state before a setup changed it (this session only; see module doc)
_touched = {}


def split_target(target):
    if ":" in target:
        kind, _, rest = target.partition(":")
        if kind in PRECEDENCE:
            return kind, rest.strip()
    return "node", target.strip()


def selection_sets():
    out = {}
    for i in range(1, int(rt.getNumNamedSelSets()) + 1):
        name = str(rt.getNamedSelSetName(i))
        out[name] = [rt.getNamedSelSetItem(i, j) for j in range(1, int(rt.getNamedSelSetItemCount(i)) + 1)]
    return out


def resolve_target(target, row=None, _sets=None):
    kind, name = split_target(target)
    if kind == "node":
        n = nodes.resolve(row.get("ref")) if isinstance(row, dict) and row.get("ref") else None
        n = n or rt.getNodeByName(name)
        return [n] if n is not None else None
    if kind == "set":
        sets = _sets if _sets is not None else selection_sets()
        return list(sets[name]) if name in sets else None
    if kind == "layer":
        if rt.LayerManager.getLayerFromName(name) is None:
            return None
        return [o for o in rt.objects if str(o.layer.name) == name]
    pat = name.lower()
    return [o for o in rt.objects if fnmatch.fnmatchcase(str(o.name).lower(), pat)]


def read_state(node):
    out = {}
    for col, (p, inv) in _PROPS.items():
        try:
            v = bool(rt.getProperty(node, p))
            out[col] = (not v) if inv else v
        except Exception:
            pass
    return out


def write_state(node, state):
    for col, v in state.items():
        if v is None or col not in _PROPS:
            continue
        p, inv = _PROPS[col]
        want = (not v) if inv else bool(v)
        try:
            if bool(rt.getProperty(node, p)) != want:
                rt.setProperty(node, p, want)
        except Exception:
            pass


def sorted_rules(rules):
    return sorted(((t, r) for t, r in (rules or {}).items() if isinstance(r, dict)),
                  key=lambda tr: PRECEDENCE[split_target(tr[0])[0]])


def suggest_targets():
    out = ["set:%s" % s for s in selection_sets()]
    out += ["layer:%s" % rt.LayerManager.getLayer(i).name for i in range(rt.LayerManager.count)]
    return out + ["pattern:*"]


def _restore(state_by_name):
    for name, st in state_by_name.items():
        n = rt.getNodeByName(name)
        if n is not None:
            write_state(n, st)


@register
class ObjectsModule(Module):
    key = "objects"
    label = "Objects"
    order = 70  # after Layers
    category = "scene"
    column = None
    props = [
        Prop("rules", "Rules", "table", columns=COLUMNS, options=suggest_targets,
             tip="Target: set:Name, layer:Name, pattern:Tree_* or node:Name.\n"
                 "Ticked = store here. Square = leave that property alone."),
    ]
    props[0].add_selection = "node:"
    props[0].new_row = {"visible": False}

    def available(self):
        return False  # added by hand (+ Add Module): a new setup has no rules yet

    def capture(self):
        return {}  # rules are authored, not read from the scene; re-capture never wipes them

    def capture_baseline(self, mgr):
        """Original state of every object any setup or folder targets."""
        rules = {}
        for item in mgr.items:
            entry = (item.get("modules") or {}).get(self.key) or {}
            rules.update((entry.get("values") or {}).get("rules") or {})
        sets = selection_sets()
        state = {}
        for target, row in rules.items():
            for n in resolve_target(target, row, sets) or []:
                state.setdefault(str(n.name), read_state(n))
        return {"rules": {}, "state": state}

    def reset(self):
        _restore(_touched)
        _touched.clear()

    def apply(self, values, context):
        state = values.get("state") or {}
        _restore(state)
        _restore({k: v for k, v in _touched.items() if k not in state})
        _touched.clear()
        sets = selection_sets()
        missing = []
        for target, row in sorted_rules(values.get("rules")):
            hits = resolve_target(target, row, sets)
            if hits is None:
                missing.append(target)
                continue
            cols = {c: v for c, v in row.items() if c in _PROPS and v is not None}
            for n in hits:
                name = str(n.name)
                if name not in state and name not in _touched:
                    _touched[name] = read_state(n)
                write_state(n, cols)
        _util.raise_missing("Object targets", missing)

    def differs(self, values, scene):
        if not values.get("rules"):
            return set()
        sets = selection_sets()
        expected = {}  # later (more specific) rules win, as in apply()
        for target, row in sorted_rules(values.get("rules")):
            for n in resolve_target(target, row, sets) or []:
                expected.setdefault(str(n.name), [n, {}])[1].update(
                    {c: v for c, v in row.items() if c in _PROPS and v is not None})
        for name, (n, cols) in expected.items():
            cur = read_state(n)
            if any(cur.get(c) != v for c, v in cols.items()):
                return {"rules"}
        return set()

    def summary(self, values):
        rules = values.get("rules") or {}
        return "%d rule%s" % (len(rules), "" if len(rules) == 1 else "s") if rules else ""
