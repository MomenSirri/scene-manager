"""Persist the setup tree as one JSON string in a custom attribute on the scene root node.

Saved with the .max file; the scene still opens without the tool.
File > Merge and Xref do not carry rootNode data: use Export/Import presets for that.
"""
import json
import uuid

from pymxs import runtime as rt

SCHEMA = 2

_CA_DEF = r"""
global SM_SceneManagerDataCA
SM_SceneManagerDataCA = attributes SceneManagerData attribID:#(0x5a3c1e01, 0x1b7d4f02)
(
    parameters main
    (
        sm_json type:#string default:""
    )
)
"""
_defined = False


def empty():
    return {"schema": SCHEMA, "items": [], "active": None}


def _has_ca():
    return bool(rt.isProperty(rt.rootNode, rt.Name("sm_json")))


def _ensure_ca():
    global _defined
    if not _defined:
        rt.execute(_CA_DEF)
        _defined = True
    if not _has_ca():
        rt.custAttributes.add(rt.rootNode, rt.SM_SceneManagerDataCA)


def new_item(kind, name, parent=None):
    return {"id": uuid.uuid4().hex, "type": kind, "name": name, "parent": parent,
            "description": "", "tags": [], "color": None, "thumbnail": None,
            "notes": "", "modules": {}}


def migrate(data):
    if data.get("schema", 1) < 2:
        items = []
        for s in data.get("setups", []):
            it = new_item("setup", s.get("name", "Setup"))
            it.update(id=s["id"], thumbnail=s.get("thumbnail"), notes=s.get("notes", ""))
            it["modules"] = {k: {"enabled": True, "values": v} for k, v in s.get("modules", {}).items()}
            items.append(it)
        data = {"schema": SCHEMA, "items": items, "active": data.get("active")}
    data.setdefault("items", [])
    data.setdefault("active", None)
    data["schema"] = SCHEMA
    return data


def load():
    if not _has_ca():
        return empty()
    raw = rt.rootNode.sm_json or ""
    if not raw:
        return empty()
    try:
        return migrate(json.loads(raw))
    except ValueError:
        print("Scene Manager: stored data is corrupt, starting empty.")
        return empty()


def save(data):
    _ensure_ca()
    rt.rootNode.sm_json = json.dumps(data, separators=(",", ":"))
    rt.setSaveRequired(True)
