"""M2 stand-in test (no 3ds Max): python tests/test_m2.py from the repo root.
Uses tests/standin_m2/pymxs.py, a tiny fake of the pymxs API. Prints what each step did."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "standin_m2"), os.path.dirname(HERE)]
os.environ.setdefault("SCENE_MANAGER_HOME", os.path.join(HERE, ".smhome"))
from pymxs import runtime as rt
from scene_manager.core import registry, manager as M, repair
rt.add("Cam01", "Targetcamera", "camera", keys=[10, 80])
rt.add("Cam02", "Physical", "camera")
key = rt.add("Key", "VRayLight", "light", on=True, multiplier=30.0, color=rt.Color(255, 240, 220))
fill = rt.add("Fill", "VRayLight", "light", on=True, multiplier=5.0, color=rt.Color(200, 220, 255))
lamp = rt.add("Lamp", "CoronaLight", "light", on=True, intensity=2.0)
sun = rt.add("Sun001", "VRaySun", "light", on=True, intensity_multiplier=1.0, size_multiplier=1.0)
for i in range(30):
    rt.add("Tree_%02d" % i, "Editable_Poly", "geometry", layer="Vegetation")
car = rt.add("Car", "Editable_Poly", "geometry", layer="Cars")
rt.selsets["Furniture"] = [rt.add("Chair%d" % i, "Editable_Poly", "geometry", layer="Interior") for i in range(3)]
from pymxs import XRef
rt.xrefs.files.append(XRef("C:/x/site.max"))
rt.viewport.setCamera(rt.getNodeByName("Cam01"))

print("modules:", [m.key for m in registry.modules()])
mgr = M.get_manager()
day = mgr.add_setup("Day")
print("Day stores:", sorted(day["modules"]))
print("baseline:", mgr.capture_baseline())

# Night: key off, others off -> only Fill on; hide Vegetation layer; objects rules
night = mgr.add_setup("Night", capture=False)
mgr.set_values(night["id"], "lights", {"lights": {"Fill": {"on": True, "intensity": 8.0}}, "others": "off"})
mgr.set_values(night["id"], "layers", {"layers": {"Vegetation": {"on": False}}})
mgr.set_values(night["id"], "objects", {"rules": {"pattern:tree_*": {"visible": False}, "node:Tree_07": {"visible": True},
                                                   "set:Furniture": {"renderable": False}}})
mgr.set_values(night["id"], "camera", {"camera": {"name": "Cam02", "handle": None}, "lock": True})
mgr.set_values(night["id"], "time", {"mode": "camera"})
mgr.set_values(night["id"], "notes", {"text": "Client wants warmer\nline2"})
mgr.set_values(night["id"], "todo", {"items": [{"text": "check glass", "done": True}, {"text": "fix fog", "done": False}]})
mgr.set_values(night["id"], "xref_scenes", {"xrefs": {"C:/x/site.max": {"visible": False}}})
print("night errors", mgr.apply("Night"))
print(" lights", key.on, fill.on, fill.multiplier, lamp.on, "sun", sun.on)
print(" layer veg on", rt.LayerManager.getLayerFromName("Vegetation").on)
print(" trees hidden", sum(rt.getNodeByName("Tree_%02d" % i).isHidden for i in range(30)), "Tree_07 hidden", rt.getNodeByName("Tree_07").isHidden)
print(" chairs renderable", [c.renderable for c in rt.selsets["Furniture"]])
print(" cam", rt.viewport.getCamera(), "locked", rt.getNodeByName("Cam02").lockflags != set())
print(" time", rt.rendTimeType, rt.rendStart, rt.rendEnd, "(Cam02 has no keys -> single)")
print(" xref hidden", rt.xrefs.files[0].hidden)
for k in ("lights", "layers", "objects", "todo", "notes", "camera", "time", "xref_scenes"):
    print("  summary", k, "=", mgr.summary(night, k), "| differs", mgr.differs_from_scene(night, k))

print("day errors", mgr.apply("Day"))
print(" lights", key.on, fill.on, fill.multiplier, lamp.on)
print(" layer veg on", rt.LayerManager.getLayerFromName("Vegetation").on)
print(" trees hidden", sum(rt.getNodeByName("Tree_%02d" % i).isHidden for i in range(30)))
print(" chairs renderable", [c.renderable for c in rt.selsets["Furniture"]])
print(" cam", rt.viewport.getCamera(), "xref hidden", rt.xrefs.files[0].hidden)
for k in ("lights", "layers", "camera"):
    print("  differs", k, mgr.differs_from_scene(day, k))

# folder inheritance of tables
f = mgr.add_folder("Interior")
mgr.set_values(f["id"], "lights", {"lights": {"Key": {"on": False}, "Fill": {"on": False}}})
s = mgr.add_setup("Interior A", parent=f["id"], capture=False)
mgr.set_values(s["id"], "lights", {"lights": {"Fill": {"on": True}}})
st = mgr.module_state(s, "lights")
print("inherit:", {k: v.get("on") for k, v in st["values"]["lights"].items()}, st["source"])

# objects without baseline: session restore
mgr.clear_baseline()
print("night2", mgr.apply("Night"), sum(rt.getNodeByName("Tree_%02d" % i).isHidden for i in range(30)))
print("day2 (no baseline, objects not on Day -> reset)", mgr.apply("Day"), sum(rt.getNodeByName("Tree_%02d" % i).isHidden for i in range(30)))

# camera key range action
rt.viewport.setCamera(rt.getNodeByName("Cam01"))
tm = registry.get("time")
print("cam keys action:", tm.actions()[0][1]({"mode": "single"}))

# rename + repair
rt.getNodeByName("Fill").name = "Fill_Light"
mgr.on_node_renamed("Fill", "Fill_Light")
print("rekeyed:", list(night["modules"]["lights"]["values"]["lights"]))
rt.delete(rt.getNodeByName("Cam02"))
print("deleted users:", repair.on_node_deleted(mgr, "Cam02"))
print("missing:", repair.find_missing(mgr))
print("repair:", repair.repair(mgr, "Cam02", "Cam01"), repair.find_missing(mgr))
print("recapture keeps notes:", mgr.capture(night["id"]) and night["modules"]["notes"])
print("json size", len(rt.rootNode.sm_json))
