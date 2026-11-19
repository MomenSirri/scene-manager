"""Renderer adapters for sky, HDRI maps, dome lights and GI / reflection environment overrides.

One place for every renderer-specific name. Each property tries a list of candidate names and the
first one that exists is used, so a renamed property fails soft. Names marked CHECK are not
verified in Max yet: run inspect_node / showProperties to confirm.

Background / GI / reflection model (renderer neutral):
  background  what the camera sees
  gi          what lights the scene (None = same as background)
  reflection  what reflections and refractions see (None = same as background)
V-Ray:  background = Environment slot, gi = environment_gi_map, reflection = environment_rr_map.
Corona: Environment slot lights the scene; with a GI override the slot holds the GI map and the
        background goes into the Direct visibility override (bg_overrideDirect).
Arnold: only the Environment slot; GI / reflection overrides are not available.
"""
from pymxs import runtime as rt

from ..core import tokens
from . import mapstore

HDRI_EXTS = (".hdr", ".exr", ".hdri", ".tif", ".tiff", ".png", ".jpg", ".jpeg")

SKY_CLASSES = {
    "vray": ["VRaySky"],
    "corona": ["CoronaSky"],
    "arnold": ["ai_physical_sky", "Physical_Sky"],   # CHECK: MAXtoA class name
}

# HDRI bitmap per renderer. Generic Bitmaptexture works everywhere and is the fallback.
HDRI_CLASSES = {
    "vray": ["VRayBitmap", "VRayHDRI"],   # VRayHDRI was renamed VRayBitmap in V-Ray 5
}
HDRI_FILE = ["HDRIMapName", "filename", "fileName"]                # VRayBitmap: HDRIMapName (CHECK)
HDRI_ROT = ["horizontalRotation", "horizontal_rotation"]           # VRayBitmap (CHECK)
HDRI_MULT = ["overall_mult", "renderMultiplier", "multiplier"]     # VRayBitmap (CHECK)
HDRI_MAPTYPE = ["mapType"]                                         # VRayBitmap 2 = spherical (CHECK)

LIGHT_MULT = ["multiplier", "intensity"]
LIGHT_TEX = ["texmap"]
LIGHT_TEX_ON = ["texmap_on", "use_texmap", "useTexmap"]   # V-Ray, ?, Arnold_Light
ARNOLD_SHAPE = ["shapeType", "type"]
ARNOLD_SKYDOME = 6


def renderer():
    return tokens.renderer_name()


# ---- small property helpers ---------------------------------------------
def has(obj, name):
    try:
        return bool(rt.isProperty(obj, rt.Name(name)))
    except Exception:
        return False


def first(obj, names):
    for n in names:
        if has(obj, n):
            return n
    return None


def get(obj, names, default=None):
    n = first(obj, names)
    if n is None:
        return default
    return rt.getProperty(obj, n)


def put(obj, names, value):
    n = first(obj, names)
    if n is not None:
        rt.setProperty(obj, n, value)
    return n


def class_name(obj):
    return str(rt.classOf(obj)) if obj is not None else ""


def make(class_names):
    for n in class_names:
        c = getattr(rt, n, None)
        if c is not None:
            try:
                return c()
            except Exception:
                continue
    return None


# ---- sky ------------------------------------------------------------------
def is_sky(texmap):
    return texmap is not None and "sky" in class_name(texmap).lower()


def make_sky(sun=None, azimuth=None, elevation=None):
    """Renderer sky map, reused per renderer, linked to the sun."""
    r = renderer()
    names = SKY_CLASSES.get(r)
    if not names:
        raise RuntimeError("No sky map known for renderer '%s' (V-Ray, Corona and Arnold are supported)." % r)
    key = "sky:" + r
    m = mapstore.get(key)
    if m is None or class_name(m) not in names:
        m = make(names)
        if m is None:
            raise RuntimeError("Could not create %s. Is the renderer installed?" % " / ".join(names))
        try:
            m.name = "SM Sky"
        except Exception:
            pass
        mapstore.put(key, m)
    if r == "vray" and sun is not None:
        put(m, ["manual_sun_node"], True)          # CHECK
        put(m, ["sun_node"], sun)                  # CHECK
    elif r == "arnold" and azimuth is not None:
        put(m, ["use_degrees"], True)              # CHECK
        put(m, ["azimuth"], float(azimuth))        # CHECK: Arnold azimuth convention
        put(m, ["elevation"], float(elevation))    # CHECK
    # Corona Sky follows the Corona Sun by itself.
    return m


# ---- HDRI maps -------------------------------------------------------------
def is_hdri(texmap):
    return texmap is not None and read_hdri(texmap) is not None


def read_hdri(texmap):
    """(path, rotation, intensity) or None if the map is not a file-based map."""
    if texmap is None:
        return None
    path = get(texmap, HDRI_FILE)
    if not path:
        return None
    if first(texmap, HDRI_ROT):
        rot = float(get(texmap, HDRI_ROT, 0.0))
    elif has(texmap, "coords"):
        rot = float(texmap.coords.U_Offset) * 360.0
    else:
        rot = 0.0
    if first(texmap, HDRI_MULT):
        mult = float(get(texmap, HDRI_MULT, 1.0))
    elif has(texmap, "output"):
        mult = float(texmap.output.output_amount)
    else:
        mult = 1.0
    return str(path), round(rot % 360.0, 2), round(mult, 4)


def make_hdri(key, path, rotation=0.0, intensity=1.0):
    """File map set up for spherical environment use. Reused under `key`."""
    if not path:
        raise RuntimeError("No HDRI file set.")
    native = HDRI_CLASSES.get(renderer(), [])
    m = mapstore.get(key)
    ok_classes = native + ["Bitmaptexture", "BitmapTexture"]
    if m is None or class_name(m) not in ok_classes:
        m = make(native) or rt.Bitmaptexture()
        try:
            m.name = "SM " + key.split(":")[-1].upper()
        except Exception:
            pass
        mapstore.put(key, m)
    if first(m, HDRI_ROT):  # native renderer bitmap
        put(m, HDRI_MAPTYPE, 2)
        if str(get(m, HDRI_FILE) or "") != path:
            put(m, HDRI_FILE, path)
        put(m, HDRI_ROT, float(rotation))
        put(m, HDRI_MULT, float(intensity))
    else:  # Bitmaptexture
        if str(m.filename or "") != path:
            m.filename = path
        m.coords.mappingType = 1   # environment
        m.coords.mapping = 0       # spherical
        m.coords.U_Offset = float(rotation) / 360.0
        m.output.output_amount = float(intensity)
    return m


# ---- background / GI / reflection ---------------------------------------
def _corona_direct_on(r):
    return bool(get(r, ["bg_overrideDirect"], False))


def get_background():
    if renderer() == "corona":
        r = rt.renderers.current
        if _corona_direct_on(r):
            return get(r, ["bg_texmapDirect"])
    return rt.environmentMap if rt.useEnvironmentMap else None


def set_background(texmap):
    if renderer() == "corona":
        r = rt.renderers.current
        if _corona_direct_on(r):
            put(r, ["bg_texmapDirect"], texmap)
            return
    rt.environmentMap = texmap
    rt.useEnvironmentMap = texmap is not None


def get_gi():
    r, rend = renderer(), rt.renderers.current
    if r == "vray":
        if get(rend, ["environment_gi_on"], False):
            return get(rend, ["environment_gi_map"])
        return None
    if r == "corona":
        return rt.environmentMap if _corona_direct_on(rend) else None
    return None


def set_gi(texmap):
    """texmap None = GI uses the background."""
    r, rend = renderer(), rt.renderers.current
    if r == "vray":
        put(rend, ["environment_gi_on"], texmap is not None)
        if texmap is not None:
            put(rend, ["environment_gi_map"], texmap)
            put(rend, ["environment_gi_map_on"], True)
        return
    if r == "corona":
        bg = get_background()
        if texmap is not None:
            put(rend, ["bg_overrideDirect"], True)
            put(rend, ["bg_texmapDirect"], bg)
            rt.environmentMap = texmap
            rt.useEnvironmentMap = True
        elif _corona_direct_on(rend):
            put(rend, ["bg_overrideDirect"], False)
            rt.environmentMap = bg
            rt.useEnvironmentMap = bg is not None
        return
    if texmap is not None:
        raise RuntimeError("GI environment override is not available for %s." % r)


def get_reflection():
    r, rend = renderer(), rt.renderers.current
    if r == "vray" and get(rend, ["environment_rr_on"], False):
        return get(rend, ["environment_rr_map"])
    if r == "corona" and get(rend, ["bg_overrideReflect"], False):
        return get(rend, ["bg_texmapReflect"])
    return None


def set_reflection(texmap):
    r, rend = renderer(), rt.renderers.current
    if r == "vray":
        put(rend, ["environment_rr_on"], texmap is not None)
        if texmap is not None:
            put(rend, ["environment_rr_map"], texmap)
            put(rend, ["environment_rr_map_on"], True)
    elif r == "corona":
        for flag, slot in (("bg_overrideReflect", "bg_texmapReflect"), ("bg_overrideRefract", "bg_texmapRefract")):
            put(rend, [flag], texmap is not None)
            if texmap is not None:
                put(rend, [slot], texmap)
    elif texmap is not None:
        raise RuntimeError("Reflection environment override is not available for %s." % r)


# ---- dome lights ------------------------------------------------------------
def is_dome(node):
    if node is None or str(rt.superClassOf(node)).lower() != "light":
        return False
    c = class_name(node).lower()
    if c == "vraylight":
        return int(get(node, ["type"], -1)) == 1           # 0 plane, 1 dome, 2 sphere, 3 mesh, 4 disc
    if c == "arnold_light":
        # MAXtoA names it shapeType (there is no "type"): 0 point, 1 distant, 2 spot, 3 quad, 4 disc,
        # 5 cylinder, 6 skydome, ... (CHECK the skydome index in your MAXtoA version)
        return int(get(node, ARNOLD_SHAPE, -1)) == ARNOLD_SKYDOME
    return "dome" in str(node.name).lower()


def list_domes():
    return [l for l in rt.lights if is_dome(l)]


def create_dome(name="SM Dome"):
    r = renderer()
    if r == "vray":
        n = rt.VRayLight()
        n.type = 1
    elif r == "arnold":
        n = rt.Arnold_Light()
        put(n, ARNOLD_SHAPE, ARNOLD_SKYDOME)
    elif r == "corona":
        raise RuntimeError("Corona has no dome light: use the Environment module with an HDRI instead.")
    else:
        raise RuntimeError("No dome light for renderer '%s'." % r)
    n.name = name
    n.pos = rt.Point3(0, 0, 0)
    return n


def dome_read(node):
    tex = get(node, LIGHT_TEX)
    if tex is not None and get(node, LIGHT_TEX_ON, True) is False:
        tex = None  # map present but switched off: no HDRI
    info = read_hdri(tex) if tex is not None else None
    vis = None
    if has(node, "invisible"):
        vis = not bool(node.invisible)
    elif has(node, "camera"):
        vis = float(node.camera) > 0                          # CHECK: Arnold camera contribution
    return {
        "on": bool(node.on) if has(node, "on") else True,
        "hdri": info[0] if info else "",
        "rotation": mapstore.get_z_rotation(node),
        "intensity": round(float(get(node, LIGHT_MULT, 1.0)), 4),
        "visible": vis,
    }


def dome_write(node, values):
    if values.get("on") is not None and has(node, "on"):
        node.on = bool(values["on"])
    if values.get("intensity") is not None:
        put(node, LIGHT_MULT, float(values["intensity"]))
    if values.get("hdri"):
        tex = make_hdri("hdri:dome:%s" % node.name, values["hdri"], 0.0, 1.0)
        put(node, LIGHT_TEX, tex)
        put(node, LIGHT_TEX_ON, True)
    elif "hdri" in values:
        # setup stores "no HDRI": switch an HDRI map off (kept on the light). A non-HDRI map
        # (procedural, colour) is not something this module captured, so it is left alone.
        tex = get(node, LIGHT_TEX)
        if tex is not None and read_hdri(tex) is not None:
            put(node, LIGHT_TEX_ON, False)
    if values.get("rotation") is not None:
        if abs(mapstore.get_z_rotation(node) - float(values["rotation"]) % 360.0) > 0.01:
            mapstore.set_z_rotation(node, float(values["rotation"]))
    if values.get("visible") is not None:
        if has(node, "invisible"):
            node.invisible = not bool(values["visible"])
        elif has(node, "camera"):
            node.camera = 1.0 if values["visible"] else 0.0


# ---- suns -------------------------------------------------------------------
SUN_CLASSES = {"vray": ["VRaySun"], "corona": ["CoronaSun"]}


def create_sun(name="SM Sun"):
    r = renderer()
    names = SUN_CLASSES.get(r)
    if not names:
        raise RuntimeError("Creating a sun for '%s' is not supported; add a Sun Positioner or a light by hand." % r)
    n = make(names)
    if n is None:
        raise RuntimeError("Could not create %s." % names[0])
    n.name = name
    n.pos = rt.Point3(0, -10000, 10000)
    return n
