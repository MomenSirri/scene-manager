"""M3 tests against the pymxs stand-in. Run from the repo folder:  python -m tests.test_m3

Checks logic (solar maths, capture/apply round trips, renderer routing, bridge commands),
not real 3ds Max API names.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("SCENE_MANAGER_HOME", tempfile.mkdtemp())

from tests import standin_pymxs as standin  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def close(a, b, tol=0.15):
    return abs(a - b) <= tol


def fresh(renderer):
    """New fake scene, and drop cached scene_manager modules so they bind to it."""
    for m in [m for m in sys.modules if m.startswith("scene_manager")]:
        del sys.modules[m]
    return standin.install(renderer)


def test_solar():
    from scene_manager.env import solar
    # London, summer solstice, 13:00 BST: noon sun ~62 degrees, due south
    az, el = solar.sun_position("2026-06-21", "13:00", 51.51, -0.13, 1)
    check(close(el, 61.9, 0.3) and close(az, 180, 2.0), "solar: London solstice noon %.1f/%.1f" % (az, el))
    # Winter solstice noon London: ~15 degrees
    az, el = solar.sun_position("2026-12-21", "12:00", 51.51, -0.13, 0)
    check(close(el, 15.1, 0.3), "solar: London winter noon elevation %.1f" % el)
    # Equinox sunrise at the equator: east, on the horizon
    az, el = solar.sun_position("2026-03-20", "06:10", 0, 0, 0)
    check(close(az, 90, 1.0) and abs(el) < 1.5, "solar: equator equinox sunrise east %.1f/%.1f" % (az, el))
    # Southern hemisphere noon: sun in the north
    az, el = solar.sun_position("2026-06-21", "12:00", -33.87, 151.21, 10)
    check(az > 350 or az < 10, "solar: Sydney noon sun is north (%.1f)" % az)
    # Afternoon sun is west in the northern hemisphere
    az, el = solar.sun_position("2026-06-21", "18:00", 40.71, -74.01, -4)
    check(240 < az < 310, "solar: New York evening sun west (%.1f)" % az)
    check(close(solar.scene_azimuth(350, 20), 10), "solar: north offset wraps")


def test_sun_module(renderer):
    rt = fresh(renderer)
    from scene_manager.core import registry
    sun_cls = rt.VRaySun if renderer == "vray" else rt.CoronaSun
    s = sun_cls(name="Sun001", pos=standin.Point3(0, -100, 100))
    m = registry.get("sun")
    cap = m.capture()
    check(cap["position"] == "angles" and close(cap["azimuth"], 180) and close(cap["elevation"], 45),
          "%s sun: capture angles %s/%s" % (renderer, cap["azimuth"], cap["elevation"]))
    vals = dict(cap, position="date_time", date="2026-06-21", time="18:00", latitude=51.51,
                longitude=-0.13, utc_offset=1, north=0, shadows=False, size=4.0)
    m.apply(vals, {})
    cap2 = m.capture()
    from scene_manager.env import solar
    az, el = solar.sun_position("2026-06-21", "18:00", 51.51, -0.13, 1)
    check(cap2["position"] == "date_time" and close(cap2["azimuth"], az) and close(cap2["elevation"], el),
          "%s sun: date/time applied and read back (%s/%s)" % (renderer, cap2["azimuth"], cap2["elevation"]))
    check(cap2["shadows"] is False and cap2["size"] == 4.0, "%s sun: shadows off, softness 4" % renderer)
    diff = {k for k, v in vals.items() if cap2.get(k) != v and k not in ("azimuth", "elevation")}
    check(not diff, "%s sun: no false 'differs from scene' after apply %s" % (renderer, diff))
    # moving the sun by hand turns the reading back to angles
    m.apply(dict(cap2, position="angles", azimuth=90, elevation=10), {})
    check(m.capture()["position"] == "angles", "%s sun: manual move reads as angles" % renderer)
    # north offset rotates the scene azimuth
    m.apply(dict(vals, north=90), {})
    check(close(m.capture()["azimuth"], (az + 90) % 360), "%s sun: north offset applied" % renderer)
    gold = dict(m.actions())["Sun position: golden hour"](dict(vals))
    check(gold["position"] == "date_time" and gold["time"] > "19:00",
          "%s sun: golden hour action -> %s" % (renderer, gold["time"]))


def test_environment(renderer):
    rt = fresh(renderer)
    from scene_manager.core import registry
    from scene_manager.env import renderers
    sun_cls = rt.VRaySun if renderer == "vray" else rt.CoronaSun
    sun = sun_cls(name="Sun001", pos=standin.Point3(0, -100, 100))
    env = registry.get("environment")
    check(env.capture()["mode"] == "none", "%s env: empty scene -> none" % renderer)
    env.apply({"mode": "sky"}, {})
    cap = env.capture()
    check(cap["mode"] == "sky" and rt.useEnvironmentMap, "%s env: sky in environment slot" % renderer)
    if renderer == "vray":
        check(rt.environmentMap.sun_node is sun and rt.environmentMap.manual_sun_node, "vray env: sky linked to sun")
    sky = rt.environmentMap
    env.apply({"mode": "sky"}, {})
    check(rt.environmentMap is sky, "%s env: sky map reused, not duplicated" % renderer)
    env.apply({"mode": "hdri", "hdri": "D:/hdri/sunset.exr", "rotation": 120, "intensity": 1.5}, {})
    cap = env.capture()
    check(cap["mode"] == "hdri" and cap["hdri"] == "D:/hdri/sunset.exr" and close(cap["rotation"], 120)
          and close(cap["intensity"], 1.5), "%s env: hdri round trip %s" % (renderer, cap))
    expected = "VRayBitmap" if renderer == "vray" else "Bitmaptexture"
    check(str(rt.classOf(rt.environmentMap)) == expected, "%s env: uses %s" % (renderer, expected))
    # custom map: user puts their own map in the slot
    chk = rt.Checker(name="MyGradient")
    rt.environmentMap = chk
    cap = env.capture()
    check(cap["mode"] == "custom" and cap["custom_map"] == "MyGradient", "%s env: custom map detected" % renderer)
    env.apply({"mode": "none"}, {})
    env.apply({"mode": "custom", "custom_map": "MyGradient"}, {})
    check(rt.environmentMap is chk, "%s env: custom map restored after none" % renderer)
    env.apply({"mode": "none"}, {})
    check(not rt.useEnvironmentMap, "%s env: none clears slot" % renderer)

    # GI / reflection overrides
    env.apply({"mode": "hdri", "hdri": "D:/hdri/bg.exr", "rotation": 0, "intensity": 1}, {})
    ov = registry.get("env_override")
    ov.apply({"gi_on": True, "gi_hdri": "D:/hdri/gi.hdr", "gi_rotation": 30, "gi_intensity": 2,
              "refl_on": True, "refl_hdri": "D:/hdri/refl.hdr", "refl_rotation": 0, "refl_intensity": 1}, {})
    oc = ov.capture()
    check(oc["gi_on"] and oc["gi_hdri"] == "D:/hdri/gi.hdr" and close(oc["gi_rotation"], 30),
          "%s override: GI round trip" % renderer)
    check(oc["refl_on"] and oc["refl_hdri"] == "D:/hdri/refl.hdr", "%s override: reflection round trip" % renderer)
    check(env.capture()["hdri"] == "D:/hdri/bg.exr", "%s override: background still bg.exr" % renderer)
    if renderer == "corona":
        check(rt.renderers.current.bg_overrideDirect and rt.environmentMap is not renderers.get_background(),
              "corona override: GI in env slot, background in direct override")
    # switching environment while GI override is on keeps the GI
    env.apply({"mode": "hdri", "hdri": "D:/hdri/bg2.exr", "rotation": 0, "intensity": 1}, {})
    check(env.capture()["hdri"] == "D:/hdri/bg2.exr" and ov.capture()["gi_hdri"] == "D:/hdri/gi.hdr",
          "%s override: new background keeps GI override" % renderer)
    ov.apply({"gi_on": False, "refl_on": False}, {})
    oc = ov.capture()
    check(not oc["gi_on"] and not oc["refl_on"] and env.capture()["hdri"] == "D:/hdri/bg2.exr",
          "%s override: off restores plain background" % renderer)


def test_arnold_env():
    rt = fresh("arnold")
    from scene_manager.core import registry
    ov = registry.get("env_override")
    try:
        ov.apply({"gi_on": True, "gi_hdri": "x.hdr"}, {})
        check(False, "arnold: GI override should raise")
    except RuntimeError as e:
        check("not available" in str(e), "arnold: GI override gives a clear error")


def test_dome():
    rt = fresh("vray")
    from scene_manager.core import registry, nodes
    d = registry.get("dome")
    check(d.capture() == {"light": None}, "dome: none in scene")
    v = dict(d.actions())["Create dome light"]({})
    check(v["light"]["name"] == "SM Dome" and rt.getNodeByName("SM Dome").type == 1, "dome: create action")
    d.apply(dict(v, on=True, hdri="D:/hdri/studio.hdr", rotation=45, intensity=2.0, visible=False), {})
    cap = d.capture()
    check(cap["hdri"] == "D:/hdri/studio.hdr" and close(cap["rotation"], 45) and cap["intensity"] == 2.0
          and cap["visible"] is False and cap["on"], "dome: round trip %s" % cap)
    other = rt.VRayLight(name="Dome old", type=1)
    d.apply(dict(cap, light=nodes.ref(rt.getNodeByName("SM Dome"))), {})
    check(other.on is False, "dome: other domes switched off")
    try:
        fresh("corona")
        from scene_manager.env import renderers
        renderers.create_dome()
        check(False, "corona dome should raise")
    except RuntimeError as e:
        check("Corona has no dome" in str(e), "dome: Corona explains to use Environment")


def test_atmosphere_and_viewport():
    rt = fresh("vray")
    from scene_manager.core import registry
    standin.atmospheric("Fog", True)
    standin.atmospheric("Aerial", False)
    a = registry.get("atmosphere")
    check(a.capture() == {"effects": {"Fog": True, "Aerial": False}}, "atmosphere: capture")
    a.apply({"effects": {"Fog": False, "Aerial": True}}, {})
    check(a.capture() == {"effects": {"Fog": False, "Aerial": True}}, "atmosphere: apply")
    try:
        a.apply({"effects": {"Gone": True}}, {})
        check(False, "atmosphere: missing should raise")
    except RuntimeError as e:
        check("Gone" in str(e), "atmosphere: missing effect reported")
    v = registry.get("viewport_bg")
    for mode, extra in (("solid", {}), ("gradient", {}), ("image", {"image": "D:/ref/plan.jpg"}), ("environment", {})):
        v.apply(dict(mode=mode, **extra), {})
        check(v.capture()["mode"] == mode, "viewport bg: %s round trip" % mode)


def test_bridge():
    rt = fresh("vray")
    rt.VRaySun(name="Sun001", pos=standin.Point3(0, -100, 100))
    from scene_manager.bridge import commands
    for name in ("set_sun", "sun_position", "set_environment", "set_dome", "environment_info", "list_hdris",
                 "set_env_overrides", "set_atmosphere", "create_sun"):
        check(name in commands.COMMANDS, "bridge: %s registered" % name)
    r = commands.COMMANDS["sun_position"](date="2026-06-21", time="13:00", city="London", utc_offset=1)
    check(close(r["elevation"], 61.9, 0.3), "bridge: sun_position by city")
    r = commands.COMMANDS["set_sun"](city="Dubai", date="2026-12-01", time="16:30", softness=3, shadows=True)
    check(r["position"] == "date_time" and r["latitude"] == 25.2 and r["size"] == 3, "bridge: set_sun by city")
    r = commands.COMMANDS["set_sun"](azimuth=200, elevation=12)
    check(close(r["azimuth"], 200) and r["position"] == "angles", "bridge: set_sun by angles")
    r = commands.COMMANDS["set_environment"](mode="hdri", hdri_path="D:/h/a.exr", rotation=90)
    check(r["mode"] == "hdri" and close(r["rotation"], 90), "bridge: set_environment hdri")
    r = commands.COMMANDS["set_dome"](hdri_path="D:/h/b.exr", create=True)
    check(r["hdri"] == "D:/h/b.exr", "bridge: set_dome create")
    info = commands.COMMANDS["environment_info"]()
    check(info["renderer"] == "vray" and info["environment"]["mode"] == "hdri" and info["domes"] == ["SM Dome"],
          "bridge: environment_info")
    # HDRI library
    d = tempfile.mkdtemp()
    for f in ("Sunset_4k.exr", "studio.hdr", "notes.txt"):
        open(os.path.join(d, f), "w").close()
    open(os.path.join(d, "studio.jpg"), "w").close()
    from scene_manager.env import hdri
    hdri.add_favourite(d)
    r = commands.COMMANDS["list_hdris"](search="sun")
    check(r["count"] == 1 and r["hdris"][0].endswith("Sunset_4k.exr"), "hdri: library search")
    check(hdri.thumbnail(os.path.join(d, "studio.hdr"), make=False).endswith("studio.jpg"), "hdri: sidecar preview")


def test_manager_switch():
    """Two setups through the real SetupManager: switching restores sun date/time and environment."""
    rt = fresh("vray")
    rt.VRaySun(name="Sun001", pos=standin.Point3(0, -100, 100))
    from scene_manager.core.manager import get_manager
    from scene_manager.bridge import commands
    mgr = get_manager()
    c = commands.COMMANDS
    c["set_sun"](city="London", date="2026-06-21", time="09:00", utc_offset=1)
    c["set_environment"](mode="sky")
    c["capture_setup"](name="Morning", modules=["sun", "environment"], thumbnail=False)
    c["set_sun"](time="20:30", softness=6)
    c["set_environment"](mode="hdri", hdri_path="D:/h/dusk.exr", rotation=200)
    c["capture_setup"](name="Dusk", modules=["sun", "environment"], thumbnail=False)
    errs = mgr.apply("Morning")
    sun = mgr.effective(mgr.get("Morning"))["sun"]
    from scene_manager.core import registry
    now = registry.get("sun").capture()
    check(not errs and now["time"] == "09:00" and now["position"] == "date_time"
          and registry.get("environment").capture()["mode"] == "sky", "manager: Morning restored %s" % errs)
    errs = mgr.apply("Dusk")
    now = registry.get("sun").capture()
    env = registry.get("environment").capture()
    check(not errs and now["time"] == "20:30" and now["size"] == 6 and env["hdri"] == "D:/h/dusk.exr"
          and close(env["rotation"], 200), "manager: Dusk restored")
    check(not mgr.differs_from_scene(mgr.get("Dusk"), "sun") and not mgr.differs_from_scene(mgr.get("Dusk"), "environment"),
          "manager: active setup shows no differences")
    # set_sun with setup= stores the values on that setup
    c["set_sun"](time="07:00", setup="Morning")
    check(mgr.effective(mgr.get("Morning"))["sun"]["time"] == "07:00", "manager: set_sun(setup=) stores value")


def test_ui_kinds():
    try:
        from PySide6 import QtWidgets
    except ImportError:
        print("skip UI kinds (no PySide6)")
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    rt = fresh("vray")
    rt.VRayLight(name="Dome A", type=1)
    rt.Omnilight(name="Omni")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from scene_manager.core.module_base import Prop
    from scene_manager.ui import kinds_env, prop_kinds  # noqa: F401
    hits = []
    w = prop_kinds.KINDS["light"](Prop("light", "Dome", "light", options=["dome"]), None, lambda: hits.append(1), {})
    items = [w.itemText(i) for i in range(w.count())]
    check(items[:3] == ["(none)", "Dome A", "Omni"], "ui: light picker lists domes first %s" % items)
    w.setCurrentIndex(1)
    check(w.value()["name"] == "Dome A", "ui: light picker value")
    c = prop_kinds.KINDS["checklist"](Prop("effects", "Effects", "checklist"), {"Fog": False},
                                      lambda: hits.append(2), {"scene": {"Fog": True, "Aerial": True}})
    check(c.value() == {"Fog": False, "Aerial": True}, "ui: checklist value %s" % c.value())
    f = prop_kinds.KINDS["hdri"](Prop("hdri", "HDRI", "hdri"), "D:/a.exr", lambda: None, {})
    check(f.value() == "D:/a.exr", "ui: hdri field value")
    from scene_manager.ui import hdri_browser
    dlg = hdri_browser.HdriBrowser(None, "")
    check(dlg.folders.count() >= 2, "ui: HDRI browser opens")
    dlg.close()


if __name__ == "__main__":
    test_solar()
    for r in ("vray", "corona"):
        test_sun_module(r)
        test_environment(r)
    test_arnold_env()
    test_dome()
    test_atmosphere_and_viewport()
    test_bridge()
    test_manager_switch()
    test_ui_kinds()
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)
