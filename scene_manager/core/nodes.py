"""Node references that survive save/load and renames (name + handle)."""
from pymxs import runtime as rt


def ref(node):
    if node is None:
        return None
    return {"name": str(node.name), "handle": int(node.inode.handle)}


def resolve(r):
    """Return the node for a ref: by handle if the name still matches, else by name."""
    if not r:
        return None
    h = r.get("handle")
    if h is not None:
        n = rt.maxOps.getNodeByHandle(h)
        if n is not None and str(n.name) == r.get("name"):
            return n
    n = rt.getNodeByName(r.get("name", ""))
    if n is None and h is not None:
        n = rt.maxOps.getNodeByHandle(h)  # renamed while the tool was not running
    return n


def rename_refs(obj, old, new):
    """Walk setup data and rename every node ref named `old`. Returns count."""
    count = 0
    if isinstance(obj, dict):
        if set(obj.keys()) >= {"name", "handle"} and obj.get("name") == old:
            obj["name"] = new
            count += 1
        for v in obj.values():
            count += rename_refs(v, old, new)
    elif isinstance(obj, list):
        for v in obj:
            count += rename_refs(v, old, new)
    return count


def is_camera(node):
    return str(rt.superClassOf(node)).lower() == "camera"


def is_light(node):
    return str(rt.superClassOf(node)).lower() == "light"


def list_cameras():
    return [c for c in rt.cameras if is_camera(c)]


def list_lights():
    return [l for l in rt.lights if is_light(l)]
