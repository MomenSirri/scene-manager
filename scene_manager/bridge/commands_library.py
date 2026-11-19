"""Environment / HDRI library for the app's browser: folder tree, thumbnails, apply to a setup.

Reuses the existing library (env/hdri.py): favourite folders in ~/.scene_manager/hdri.json, the team
folder under the presets folder, the recent list, sidecar previews and the thumbnail cache in
~/.scene_manager/hdri_thumbs. Applying goes through the setup modules (environment, dome, env_override),
so the choice is stored on the setup and, for the active setup, applied to the scene as one undo step.
"""
import base64
import os
import time

from ..core.manager import get_manager
from ..env import hdri, renderers
from .commands import log

# target -> (module, values to store for a path). Labels are what the app shows.
TARGETS = {
    "environment": ("environment", "Environment", lambda p: {"mode": "hdri", "hdri": p}),
    "dome": ("dome", "Dome light", lambda p: {"hdri": p, "on": True}),
    "gi": ("env_override", "GI override", lambda p: {"gi_on": True, "gi_hdri": p}),
    "refl": ("env_override", "Reflection override", lambda p: {"refl_on": True, "refl_hdri": p}),
}
PROP_OF = {"environment": "hdri", "dome": "hdri", "gi": "gi_hdri", "refl": "refl_hdri"}


def _targets():
    r = renderers.renderer()
    out = []
    for key, (module, label, _fn) in TARGETS.items():
        why = ""
        if key == "dome" and r == "corona":
            why = "Corona has no dome light. Use Environment."
        elif key in ("gi", "refl") and r == "arnold":
            why = "Arnold has no GI / reflection override."
        out.append({"key": key, "label": label, "module": module, "prop": PROP_OF[key], "available": not why, "why": why})
    return out


def lib_roots():
    """Folders the browser starts from, the recent list and where each pick can go."""
    data = hdri.load()
    recent = [p for p in data.get("recent", []) if os.path.isfile(p)]
    return {"roots": hdri.roots(), "recent": recent, "targets": _targets(), "renderer": renderers.renderer(),
            "exts": list(hdri.EXTS), "image_exts": list(hdri.IMAGE_EXTS)}


def lib_list(folder, search="", images=False):
    """Subfolders and assets of one folder. With search: matching assets in the whole subtree."""
    if folder == "recent":
        s = (search or "").lower()
        files = []
        for p in hdri.load().get("recent", []):
            if os.path.isfile(p) and s in os.path.basename(p).lower():
                st = os.stat(p)
                files.append({"path": p, "name": os.path.splitext(os.path.basename(p))[0],
                              "ext": os.path.splitext(p)[1][1:].lower(), "size": st.st_size,
                              "mtime": int(st.st_mtime), "folder": os.path.dirname(p)})
        return {"folder": "recent", "dirs": [], "files": files, "missing": False, "truncated": False}
    return hdri.list_folder(folder, search=search, images=bool(images))


def _data_url(path):
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    with open(path, "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode("ascii"))


def lib_thumbs(paths, make=True, budget_ms=350):
    """Thumbnails as data URLs. Cached ones come back at once; new ones are made (3ds Max reads the HDRI)
    until the time budget is spent, so 3ds Max stays responsive. The app asks again for "pending"."""
    t0 = time.perf_counter()
    out, pending = {}, []
    for p in paths:
        tp = hdri.thumbnail(p, make=False)
        if tp is None and make and (time.perf_counter() - t0) * 1000 < budget_ms:
            tp = hdri.thumbnail(p, make=True)
            if tp is None:
                out[p] = None     # could not be read: do not ask again
                continue
        if tp is None:
            if make:
                pending.append(p)
            else:
                out[p] = None
            continue
        try:
            out[p] = _data_url(tp)
        except OSError:
            out[p] = None
    return {"thumbs": out, "pending": pending}


def lib_add_folder(path):
    if not path or not os.path.isdir(path):
        raise ValueError("Not a folder: %r" % path)
    return {"favourites": hdri.add_favourite(path)}


def lib_remove_folder(path):
    return {"favourites": hdri.remove_favourite(path)}


def lib_apply(id, target, path, create_dome=True):
    """Put a library asset into a setup's Environment / Dome light / GI / Reflection slot.
    The module is added to the setup first if it is not there (filled from the scene, so rotation and
    intensity stay as they are). On the active setup the scene changes at once."""
    from . import commands_ui
    if target not in TARGETS:
        raise KeyError("Unknown target %r (use %s)" % (target, ", ".join(TARGETS)))
    t = next(x for x in _targets() if x["key"] == target)
    if not t["available"]:
        raise RuntimeError(t["why"])
    if not path or not os.path.isfile(path):
        raise FileNotFoundError("File not found: %s" % path)
    module, label, values_for = TARGETS[target]
    mgr = get_manager()
    item = mgr.require(id)
    if module not in item["modules"]:
        mgr.capture(item["id"], keys=[module])
    values = values_for(path)
    created = None
    if target == "dome" and not mgr.module_state(item, "dome")["values"].get("light"):
        domes = renderers.list_domes()
        if domes:
            node = domes[0]
        elif create_dome:
            from ..core.undo import undo_step
            with undo_step("Scene Manager: create dome light"):
                node = renderers.create_dome()
            created = str(node.name)
        else:
            raise RuntimeError("No dome light in the scene.")
        from ..core import nodes
        values["light"] = nodes.ref(node)
    mgr.set_values(item["id"], module, values)
    errors = commands_ui._live(mgr, item, module)
    hdri.add_recent(path)
    log("%s of %s -> %s" % (label, item["name"], os.path.basename(path)))
    return {"errors": errors, "module": module, "active": item["id"] == mgr.active_id, "created": created}


COMMANDS = {f.__name__: f for f in (lib_roots, lib_list, lib_thumbs, lib_add_folder, lib_remove_folder, lib_apply)}
