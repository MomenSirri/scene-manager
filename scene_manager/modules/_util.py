"""Helpers shared by the M2 modules (not a module itself: files starting with _ are not auto-loaded)."""
from pymxs import runtime as rt


def first_prop(obj, names):
    """First property name in `names` that `obj` has (renderer property names differ), else None."""
    for n in names:
        try:
            if rt.isProperty(obj, rt.Name(n)):
                return n
        except Exception:
            pass
    return None


def color_to_list(c):
    try:
        return [int(round(float(c.r))), int(round(float(c.g))), int(round(float(c.b)))]
    except Exception:
        return None


def list_to_color(v):
    return rt.Color(float(v[0]), float(v[1]), float(v[2]))


def as_jsonable(v):
    """Property value -> JSON-safe (bool/int/float/colour list) or None if unsupported."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    c = color_to_list(v)
    return c


def set_value(obj, name, value):
    """Set a property, converting colour lists back to Color."""
    if isinstance(value, list) and len(value) == 3:
        value = list_to_color(value)
    elif isinstance(value, float) and isinstance(rt.getProperty(obj, name), bool):
        value = bool(value)
    rt.setProperty(obj, name, value)


class MissingNodes(RuntimeError):
    pass


def raise_missing(kind, names):
    if names:
        shown = ", ".join(sorted(names)[:5]) + (" and %d more" % (len(names) - 5) if len(names) > 5 else "")
        raise MissingNodes("%s not found: %s (Repair missing nodes can re-link them)" % (kind, shown))
