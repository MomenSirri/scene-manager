"""Environment / HDRI library browser backend against the pymxs stand-in:  python -m tests.test_library

Checks folder listing, team folder, sidecar handling, thumbnail budget and applying a pick to each slot.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("SCENE_MANAGER_HOME", tempfile.mkdtemp())

from tests import standin_pymxs as standin  # noqa: E402
from tests.test_m3 import FAILS, check, fresh  # noqa: E402


def make_library():
    root = tempfile.mkdtemp(prefix="hdri_lib_")
    files = {"Outdoor/clear_sky.hdr": 10, "Outdoor/Sunset/golden.exr": 10, "Outdoor/Sunset/golden_preview.jpg": 10,
             "Studio/softbox.hdr": 10, "Studio/softbox.jpg": 300 * 1024, "Studio/backplate.jpg": 10, "Studio/readme.txt": 1}
    for rel, size in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"x" * size)
    return root


def test_listing():
    fresh("vray")
    from scene_manager import config
    from scene_manager.bridge import commands
    c = commands.COMMANDS
    lib = make_library()
    c["lib_add_folder"](lib)
    team = tempfile.mkdtemp(prefix="presets_")
    os.makedirs(os.path.join(team, "HDRI"))
    config.update(presets_folder=team)
    roots = c["lib_roots"]()
    kinds = [r["kind"] for r in roots["roots"]]
    check(kinds == ["favourite", "team"], "roots: favourite + team HDRI folder %s" % kinds)
    top = c["lib_list"](lib)
    check([d["name"] for d in top["dirs"]] == ["Outdoor", "Studio"] and not top["files"], "list: top level folders only")
    check(top["dirs"][0]["has_dirs"] and not top["dirs"][1]["has_dirs"], "list: has_dirs flags")
    st = c["lib_list"](os.path.join(lib, "Studio"))
    check([f["name"] for f in st["files"]] == ["softbox"], "list: HDRIs only, sidecar and txt hidden")
    st = c["lib_list"](os.path.join(lib, "Studio"), images=True)
    check([f["name"] for f in st["files"]] == ["backplate", "softbox"], "list: images on, sidecar still hidden %s" % [f["name"] for f in st["files"]])
    s = c["lib_list"](lib, search="GOLD")
    check(len(s["files"]) == 1 and s["files"][0]["folder"] == os.path.join("Outdoor", "Sunset"), "list: search in subtree")
    check(c["lib_list"](os.path.join(lib, "nope"))["missing"], "list: missing folder flagged")
    # thumbnails: small sidecar returned as is; big sidecar needs 3ds Max (stand-in has no openBitmap -> None, not pending)
    t = c["lib_thumbs"]([os.path.join(lib, "Outdoor/Sunset/golden.exr")])
    check(t["thumbs"][os.path.join(lib, "Outdoor/Sunset/golden.exr")].startswith("data:image/jpeg;base64,"), "thumbs: sidecar as data URL")
    t = c["lib_thumbs"]([os.path.join(lib, "Outdoor/clear_sky.hdr")], make=False)
    check(t["thumbs"][os.path.join(lib, "Outdoor/clear_sky.hdr")] is None and not t["pending"], "thumbs: make=False does not render")
    t = c["lib_thumbs"]([os.path.join(lib, "Outdoor/clear_sky.hdr"), os.path.join(lib, "Studio/softbox.hdr")], budget_ms=0)
    check(len(t["pending"]) == 2, "thumbs: budget spent -> pending")
    return lib


def test_apply(lib):
    rt = fresh("vray")
    from scene_manager.core.manager import get_manager
    from scene_manager.bridge import commands
    c = commands.COMMANDS
    mgr = get_manager()
    day = mgr.add_setup("Day", keys=["camera"])
    night = mgr.add_setup("Night", keys=["camera"])
    mgr.apply(day["id"])
    sky = os.path.join(lib, "Outdoor/clear_sky.hdr")
    r = c["lib_apply"](day["id"], "environment", sky)
    check(not r["errors"] and r["active"], "apply env: no errors %s" % r["errors"])
    check(mgr.module_state(mgr.require(day["id"]), "environment")["values"]["hdri"] == sky, "apply env: stored on setup")
    check(rt.environmentMap is not None and c["environment_info"]()["environment"]["hdri"] == sky, "apply env: in the scene")
    gold = os.path.join(lib, "Outdoor/Sunset/golden.exr")
    r = c["lib_apply"](night["id"], "environment", gold)
    check(not r["active"] and c["environment_info"]()["environment"]["hdri"] == sky, "apply env on inactive setup: scene unchanged")
    mgr.apply(night["id"])
    check(c["environment_info"]()["environment"]["hdri"] == gold, "activate Night: its HDRI comes in")
    r = c["lib_apply"](night["id"], "dome", gold)
    check(r["created"] == "SM Dome" and not r["errors"], "apply dome: dome created %s" % r)
    check(c["environment_info"]()["dome"]["hdri"] == gold, "apply dome: dome has the HDRI")
    r = c["lib_apply"](night["id"], "gi", sky)
    info = c["environment_info"]()["env_override"]
    check(info["gi_on"] and info["gi_hdri"] == sky and not info["refl_on"], "apply gi override")
    check(c["lib_roots"]()["recent"][0] == sky, "recent list updated")
    try:
        c["lib_apply"](night["id"], "environment", os.path.join(lib, "missing.hdr"))
        check(False, "apply: missing file refused")
    except FileNotFoundError:
        check(True, "apply: missing file refused")


def test_targets():
    fresh("corona")
    from scene_manager.bridge import commands
    t = {x["key"]: x for x in commands.COMMANDS["lib_roots"]()["targets"]}
    check(not t["dome"]["available"] and t["gi"]["available"], "corona: no dome target")


if __name__ == "__main__":
    lib = test_listing()
    test_apply(lib)
    test_targets()
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)
