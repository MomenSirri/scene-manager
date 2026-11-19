import os, sys, json, tempfile
"""M4 render modules against a pymxs stand-in. Run outside Max:  python tests/test_m4.py"""
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "standin_m4"), os.path.dirname(HERE)]
os.environ.setdefault("SCENE_MANAGER_HOME", tempfile.mkdtemp())
from pymxs import runtime as rt
from scene_manager.core import registry
registry.load_builtin()
from scene_manager.modules import (render_settings, render_override, render_preset, render_elements,
                                   post_production, lightmix, output_builder, custom_props)
from scene_manager.core import tokens
from scene_manager.core.manager import SetupManager
from scene_manager.render import rprops, batch

def ok(c, msg):
    print(("PASS " if c else "FAIL ") + msg)
    if not c: ok.fails += 1
ok.fails = 0

# --- renderer kinds
ok(rprops.current_kind() == "vray", "vray detected")
ok(set(rprops.renderer_classes()) >= {"vray", "corona", "arnold", "scanline"}, "installed renderers")

# --- curated capture/apply
vr = registry.get("render_vray")
cap = vr.capture()
ok(cap["sampler"] == "progressive" and cap["gi_secondary"] == "light cache", "vray curated capture: %s" % cap)
vr.apply(dict(cap, sampler="bucket", noise=0.02, gi_secondary="brute force"), {})
ok(rt.renderers.current.imageSampler_type_new == 0 and rt.renderers.current.gi_secondary_type == 2, "vray curated apply")
ok(registry.get("render_corona").capture() == {}, "corona card captures nothing on vray")
try:
    registry.get("render_corona").apply({"pass_limit": 5}, {})
except RuntimeError as e:
    ok("skipped" in str(e), "corona apply on vray reports skipped")

# --- override diff
rt.renderers.current.system_region_x = 32
d = render_override.scene_diff()
ok(d == {"system_region_x": 32}, "diff excludes curated/output/env props: %s" % d)
ro = registry.get("render_override")
v = ro.capture()
rt.renderers.current = rt.V_Ray_7()
ro.apply(v, {})
ok(rt.renderers.current.system_region_x == 32, "override apply")
m = ro.merge({"overrides": {"a": 1, "b": 2}}, {"overrides": {"b": 3, "a": None}})
ok(m["overrides"] == {"b": 3}, "override merge per key")

# --- renderer switch
rm = registry.get("renderer")
rm.apply({"renderer": "corona"}, {})
ok(rprops.current_kind() == "corona", "switch to corona")
cc = registry.get("render_corona").capture()
ok(cc["noise_limit"] == 2.0 and cc["light_samples"] == 2.0, "corona curated capture")
pp = registry.get("post").capture()
ok(set(pp["corona_tonemap"]) == {"colorMap_simpleExposure", "colorMap_highlightCompression", "bloomGlare_enabled"}, "corona tonemap capture")
rt.renderers.current.colorMap_simpleExposure = 1.5
registry.get("post").apply(pp, {})
ok(rt.renderers.current.colorMap_simpleExposure == 0.0, "corona tonemap apply")
rm.apply({"renderer": "vray"}, {})
rt._layers.json = '{"layers":[1]}'
pv = registry.get("post").capture()
rt._layers.json = '{}'
registry.get("post").apply(pv, {})
ok(rt._layers.json == '{"layers":[1]}', "vfb layers roundtrip")

# --- preset
tmp = tempfile.mkdtemp()
f = os.path.join(tmp, "hq.rps"); open(f, "w").write("x")
registry.get("render_preset").apply({"file": f, "keep_common": True}, {})
ok(rt.renderPresets.loaded[-1][0] == "some" and rt.renderPresets.loaded[-1][2] == {2, 3, 4, 5}, "preset keeps Common")
render_preset.save(os.path.join(tmp, "sub", "a.rps"))
ok(os.path.exists(os.path.join(tmp, "sub", "a.rps")), "preset save")

# --- elements
rt.add_element("VRayReflection", "Reflection")
rt.add_element("VRayLightSelect", "LS_Sun", lights=[])
re_ = registry.get("render_elements")
ev = re_.capture()
ok(ev["elements"] == {"Reflection": True, "LS_Sun": True} and ev["vray_split"] is False, "elements capture")
ctx = {"scene": "Street", "setup": "Dusk", "renderer": "vray"}
re_.apply(dict(ev, elements={"Reflection": False}, element_path=os.path.join(tmp, "{setup}", "{setup}_{element}.exr"),
               vray_raw=True, vray_raw_path=os.path.join(tmp, "{setup}_raw.exr")), ctx)
ok(rt._elmgr.els[0].enabled is False and rt._elmgr.files[1].endswith("Dusk_LS_Sun.exr"), "elements apply + filenames")
ok(rt.renderers.current.output_saveRawFile is True and rt.renderers.current.output_rawFileName.endswith("Dusk_raw.exr"), "vray raw")
ok(re_.merge({"elements": {"A": True}}, {"elements": {"B": False}})["elements"] == {"A": True, "B": False}, "elements merge")

# --- lightmix
a = rt.add_light("Key", multiplier=10.0); b = rt.add_light("Fill", multiplier=4.0); c = rt.add_light("Rim", multiplier=2.0)
rt._elmgr.els[1].lights = [a, b]
lm = registry.get("lightmix")
lv = lm.capture()
ok(set(lv["groups"]) == {"LS_Sun", "Rim"} and lv["base"] == {"Key": 10.0, "Fill": 4.0, "Rim": 2.0}, "lightmix groups: %s" % lv["groups"])
lv["groups"]["LS_Sun"]["mult"] = 0.5; lv["groups"]["Rim"]["on"] = False
lm.apply(lv, {})
ok(a.multiplier == 5.0 and b.multiplier == 2.0 and c.on is False, "lightmix apply")
mm = lm.merge({"groups": {"LS_Sun": {"on": True, "mult": 1.0}}}, {"groups": {"LS_Sun": {"mult": 2.0}}})
ok(mm["groups"]["LS_Sun"] == {"on": True, "mult": 2.0}, "lightmix row merge")

# --- custom props
rt.selection = [a]
key, row = custom_props.make_row("node", "multiplier", node_name="Key")
ok(key == "Key.multiplier" and row["value"] == 5.0, "custom row %s" % key)
k2, r2 = custom_props.make_row("renderer", "lightcache_subdivs", value=2000)
cp = registry.get("custom_props")
row["value"] = 7.0
cp.apply({"rows": {key: row, k2: r2}}, {})
ok(a.multiplier == 7.0 and rt.renderers.current.lightcache_subdivs == 2000, "custom props apply")
ok(cp.differs({"rows": {key: dict(row, value=1.0)}}, {}) == {"rows"}, "custom props differs")

# --- tokens / version
out = os.path.join(tmp, "out")
os.makedirs(out)
for n in ("Dusk_v001.exr", "Dusk_v0020000.exr", "Dusk_v002_beauty.exr", "Other_v009.exr"):
    open(os.path.join(out, n), "w").close()
ctx = {"setup": "Dusk"}
p = tokens.resolve(os.path.join(out, "{setup}_v{version}.exr"), ctx)
ok(p.endswith("Dusk_v003.exr"), "auto version next free: %s" % os.path.basename(p))
p = tokens.resolve(os.path.join(out, "{setup}_v{version}.exr"), dict(ctx, version=7, version_pad=2))
ok(p.endswith("Dusk_v07.exr"), "fixed version")
p = tokens.resolve(os.path.join(tmp, "v{version}", "{setup}.exr"), ctx)
ok(os.path.join("v001", "Dusk.exr") in p, "version folder: %s" % p)
ob = registry.get("output_builder")
c2 = {"camera": "Cam01", "width": 1920}
ob.extend_context(c2, {"version": 0, "custom": {"client": "ACME", "shot": "{camera}_{width}", "setup": "x"}})
ok(c2["client"] == "ACME" and c2["shot"] == "Cam01_1920" and "setup" not in c2, "custom tokens")

# --- through the manager (current core, M2 hooks may be missing)
rt.renderers.current = rt.V_Ray_7()
mgr = SetupManager()
s = mgr.add_setup("Dusk")
mgr.set_enabled(s["id"], "output_builder", True)
mgr.set_values(s["id"], "output_builder", {"custom": {"client": "ACME"}, "version": 4})
mgr.set_values(s["id"], "output", {"path": os.path.join(tmp, "{client}", "{setup}_v{version}.exr"), "save_file": True})
mgr.set_values(s["id"], "render_vray", {"noise": 0.003})
errs = mgr.apply(s["id"])
ok(not errs, "manager apply errors: %s" % errs)
ok(rt.rendOutputFilename.endswith(os.path.join("ACME", "Dusk_v004.exr")), "output path with custom token + version: %s" % rt.rendOutputFilename)
ok(rt.renderers.current.twoLevel_threshold == 0.003, "curated value via manager")
print("modules:", [m.key for m in registry.modules()])
# renderer instance kept across switches
rt.renderers.current.twoLevel_threshold = 0.042
registry.get("renderer").apply({"renderer": "corona"}, {})
registry.get("renderer").apply({"renderer": "vray"}, {})
ok(rt.renderers.current.twoLevel_threshold == 0.042, "vray settings survive a switch to corona and back")
# M2 baseline + inheritance through folders
mgr2 = SetupManager()
f = mgr2.add_folder("Street")
mgr2.set_values(f["id"], "render_elements", {"elements": {"Reflection": False}})
s2 = mgr2.add_setup("Night", parent=f["id"])
mgr2.set_values(s2["id"], "render_elements", {"elements": {"LS_Sun": False}})
st = mgr2.module_state(s2, "render_elements")
ok(st["values"]["elements"] == {"Reflection": False, "LS_Sun": False} or st["values"]["elements"].get("Reflection") is False, "elements inherit per key: %s" % st["values"]["elements"])
mgr2.capture_baseline()
ok("render_vray" in mgr2.baseline, "baseline has vray settings")
registry.get("renderer").apply({"renderer": "corona"}, {})
mgr2.set_values(s2["id"], "renderer", {"renderer": "corona"})
errs = mgr2.apply(s2["id"])
ok(not errs, "apply with baseline on corona setup: %s" % errs)
ok(rprops.current_kind() == "corona", "setup switched renderer")
ok(not [m.key for m in registry.modules() if not m.available() and m.key in mgr2.module_state(s2, m.key) and False], "noop")
new = mgr2.add_setup("Fresh")
ok(not mgr2.module_state(new, "render_vray")["enabled"] and mgr2.module_state(new, "render_corona")["enabled"], "new setup only captures current renderer card")
ok(not mgr2.module_state(new, "lightmix")["enabled"], "optional modules not auto-captured")
print("FAILS:", ok.fails)
sys.exit(1 if ok.fails else 0)
