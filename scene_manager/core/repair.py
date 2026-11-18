"""Find and repair node references that no longer resolve (M2).

Setups point at cameras, lights and objects by name + handle (core.nodes.ref). Renames are
followed automatically (#nodeRenamed callback). Deleted or replaced nodes leave refs that do not
resolve; list them with find_missing() and point them at another node with repair().
Table rows (Lights, Objects) are keyed by node name as well, so those keys are renamed too.
"""
from pymxs import runtime as rt

from . import nodes

# Messages for the panel status line (e.g. "Camera01 was deleted; used by 2 setups").
NOTICES = []


def _walk_refs(obj, fn, path=()):
    if isinstance(obj, dict):
        if set(obj.keys()) >= {"name", "handle"}:
            fn(obj, path)
            return
        for k, v in obj.items():
            _walk_refs(v, fn, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_refs(v, fn, path + (i,))


def rekey_rows(data, old, new):
    """Rename dict keys equal to `old` whose value holds a ref to `new` (table rows keyed by node name)."""
    count = 0

    def walk(obj):
        nonlocal count
        if isinstance(obj, dict):
            v = obj.get(old)
            if isinstance(v, dict) and isinstance(v.get("ref"), dict) and v["ref"].get("name") == new \
                    and new not in obj:
                obj[new] = obj.pop(old)
                count += 1
            if isinstance(obj.get("node:" + old), dict) and "node:" + new not in obj:  # Objects rules
                obj["node:" + new] = obj.pop("node:" + old)
                count += 1
            for x in list(obj.values()):
                walk(x)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(data)
    return count


def find_missing(mgr):
    """[{"name", "handle", "used_by": [setup/folder paths]}] for refs that do not resolve."""
    found = {}
    cache = {}

    def check(owner):
        def fn(r, path):
            key = (r.get("name"), r.get("handle"))
            if key not in cache:
                try:
                    cache[key] = nodes.resolve(r) is not None
                except Exception:
                    cache[key] = False
            if not cache[key]:
                e = found.setdefault(r.get("name"), {"name": r.get("name"), "handle": r.get("handle"),
                                                     "used_by": []})
                if owner not in e["used_by"]:
                    e["used_by"].append(owner)
        return fn

    for item in mgr.items:
        _walk_refs(item.get("modules", {}), check(mgr.path(item)))
    _walk_refs(mgr.baseline, check("(baseline)"))
    return sorted(found.values(), key=lambda e: str(e["name"]).lower())


def repair(mgr, old_name, new_node_name):
    """Point every ref named `old_name` at node `new_node_name`. Returns the number of refs changed."""
    node = rt.getNodeByName(new_node_name)
    if node is None:
        raise KeyError("No node named %r" % new_node_name)
    new = nodes.ref(node)
    count = 0

    def fn(r, path):
        nonlocal count
        if r.get("name") == old_name:
            r["name"], r["handle"] = new["name"], new["handle"]
            count += 1

    for item in mgr.items:
        _walk_refs(item.get("modules", {}), fn)
    _walk_refs(mgr.data.get("baseline") or {}, fn)
    count += rekey_rows(mgr.data, old_name, new["name"])
    if count:
        mgr.commit()
    return count


def users_of(mgr, name):
    """Paths of setups/folders that reference a node by this name."""
    out = []
    for item in mgr.items:
        hit = []
        _walk_refs(item.get("modules", {}), lambda r, p: hit.append(1) if r.get("name") == name else None)
        if hit:
            out.append(mgr.path(item))
    return out


def on_node_deleted(mgr, name):
    """Called from the #nodePreDelete callback: remember a notice if setups use the node."""
    used = users_of(mgr, name)
    if used:
        msg = "'%s' was deleted; used by %s. Use Repair missing nodes to re-link." % (
            name, ", ".join(used[:3]) + (" and %d more" % (len(used) - 3) if len(used) > 3 else ""))
        NOTICES.append(msg)
        del NOTICES[:-20]
        print("Scene Manager: " + msg)
    return used
