"""Renderer helpers shared by the M4 render modules.

- which renderer is current (vray / vray_gpu / corona / arnold / other) and switching renderers
- reading and writing renderer properties as JSON-safe values
- snapshot of all renderer properties and the diff against the renderer's defaults

JSON forms for MAXScript values: Color -> {"color": [r, g, b, a]}, Point3 -> {"point3": [x, y, z]},
Name -> {"name": "foo"}. Maps, nodes and arrays are skipped (not JSON-safe).
"""
from pymxs import runtime as rt

# Renderer kind -> words that must appear in the lower-case class name (all) and words that must not.
KINDS = {
    "vray": (("v_ray",), ("gpu", "rt")),
    "vray_gpu": (("v_ray", "gpu"), ()),
    "corona": (("corona",), ()),
    "arnold": (("arnold",), ()),
    "scanline": (("scanline",), ()),
    "art": (("art_renderer",), ()),
}
KIND_LABELS = {"vray": "V-Ray", "vray_gpu": "V-Ray GPU", "corona": "Corona", "arnold": "Arnold",
               "scanline": "Scanline", "art": "ART"}


def kind_of_class(cls_name):
    n = str(cls_name).lower()
    for kind, (need, avoid) in KINDS.items():
        if all(w in n for w in need) and not any(w in n for w in avoid):
            return kind
    return n


def current():
    return rt.renderers.current


def current_kind():
    return kind_of_class(rt.classOf(rt.renderers.current))


def renderer_classes():
    """{kind: class} for every renderer installed. Newest version wins when several exist (V_Ray_6, V_Ray_7)."""
    out = {}
    for c in rt.RendererClass.classes:
        k = kind_of_class(c)
        if k in KINDS and (k not in out or str(c) > str(out[k])):
            out[k] = c
    return out


_installed = None


def installed_kinds(refresh=False):
    """Renderer kinds installed in this 3ds Max, in KINDS order (read once from RendererClass.classes).
    If the list cannot be read, every known kind is returned so nothing is hidden by mistake."""
    global _installed
    if _installed is None or refresh:
        try:
            found = renderer_classes()
        except Exception:
            found = {}
        _installed = [k for k in KINDS if k in found] or list(KINDS)
    return list(_installed)


def is_installed(*kinds):
    """True when at least one of `kinds` is installed (no kinds = not renderer-specific = True)."""
    have = installed_kinds()
    return not kinds or any(k in have for k in kinds)


_instances = {}   # kind -> renderer instance used earlier in this Max session


def set_renderer(kind):
    """Make `kind` the production renderer. Returns True if it changed.
    The renderer we switch away from is kept, so switching back restores its settings in this session.
    A renderer not used yet in this session starts from its defaults (plus what the setup's modules set)."""
    if current_kind() == kind:
        return False
    cls = renderer_classes().get(kind)
    if cls is None:
        raise RuntimeError("renderer '%s' is not installed" % kind)
    _instances[current_kind()] = rt.renderers.current
    inst = _instances.get(kind)
    rt.renderers.current = inst if inst is not None else cls()   # CHECK IN MAX: calling a RendererClass makes an instance
    return True


# ---- values ---------------------------------------------------------------
def _cls(v):
    try:
        return str(rt.classOf(v)).lower()
    except Exception:
        return ""


def to_json(v):
    """(ok, json_value) for a MAXScript value."""
    if v is None or isinstance(v, (bool, int, str)):
        return True, v
    if isinstance(v, float):
        return True, round(v, 6)
    c = _cls(v)
    if c == "color":
        return True, {"color": [round(float(v.r), 3), round(float(v.g), 3), round(float(v.b), 3),
                                round(float(v.a), 3)]}
    if c == "point3":
        return True, {"point3": [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]}
    if c == "name":
        return True, {"name": str(v)}
    return False, None


def from_json(v):
    if isinstance(v, dict):
        if "color" in v:
            c = list(v["color"]) + [255.0] * (4 - len(v["color"]))
            return rt.Color(*c[:4])
        if "point3" in v:
            return rt.Point3(*v["point3"])
        if "name" in v:
            return rt.Name(v["name"])
    return v


def find_prop(obj, names):
    """First name in `names` that exists on obj (property names differ between renderer versions)."""
    if obj is None:
        return None
    if isinstance(names, str):
        names = [names]
    for n in names:
        if rt.isProperty(obj, rt.Name(n)):
            return n
    return None


def read(obj, names):
    p = find_prop(obj, names)
    if p is None:
        return None
    ok, v = to_json(rt.getProperty(obj, rt.Name(p)))
    return v if ok else None


def write(obj, names, value):
    """Set a property; returns the name used, or None if it does not exist."""
    p = find_prop(obj, names)
    if p is None:
        return None
    v = from_json(value)
    cur = rt.getProperty(obj, rt.Name(p))
    if isinstance(cur, bool) and not isinstance(v, bool):
        v = bool(v)
    elif isinstance(cur, int) and not isinstance(cur, bool) and isinstance(v, float):
        v = int(round(v))
    elif isinstance(cur, float) and isinstance(v, int) and not isinstance(v, bool):
        v = float(v)
    rt.setProperty(obj, rt.Name(p), v)
    return p


def prop_names(obj):
    return [str(p) for p in rt.getPropNames(obj)]


def snapshot(obj, include=None):
    """{prop: json_value} for every JSON-safe property of obj. include(name) filters names."""
    out = {}
    for p in prop_names(obj):
        if include and not include(p):
            continue
        try:
            ok, v = to_json(rt.getProperty(obj, rt.Name(p)))
        except Exception:
            continue
        if ok:
            out[p] = v
    return out


_defaults_cache = {}


def defaults(obj=None):
    """Snapshot of a fresh instance of the renderer class (cached per class for this Max session)."""
    obj = obj if obj is not None else current()
    key = str(rt.classOf(obj))
    if key not in _defaults_cache:
        fresh = rt.classOf(obj)()   # CHECK IN MAX: makes an unassigned renderer instance with default values
        _defaults_cache[key] = snapshot(fresh)
    return _defaults_cache[key]


def _same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-5
        except (TypeError, ValueError):
            return False
    return a == b


def diff(current_values, base_values, skip=()):
    """Properties whose value differs from the base."""
    return {p: v for p, v in current_values.items()
            if p not in skip and (p not in base_values or not _same(v, base_values[p]))}


def merge_rows(base, over):
    """Merge {row: {col: value}} dicts: per row, then per column. A row set to None in `over` is removed."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (base or {}).items()}
    for k, v in (over or {}).items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = dict(v) if isinstance(v, dict) else v
    return out


def merge_module(base, over, row_props=(), dict_props=()):
    """Module.merge helper: plain props replace, row props merge per row, dict props merge per key."""
    out = dict(base or {})
    for k, v in (over or {}).items():
        if k in row_props and isinstance(v, dict):
            out[k] = merge_rows((base or {}).get(k), v)
        elif k in dict_props and isinstance(v, dict):
            d = dict((base or {}).get(k) or {})
            for kk, vv in v.items():
                if vv is None:
                    d.pop(kk, None)
                else:
                    d[kk] = vv
            out[k] = d
        else:
            out[k] = v
    return out
