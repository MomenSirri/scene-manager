"""A small stand-in for pymxs so module logic can be tested outside 3ds Max.

It fakes only what the M3 modules touch: nodes with properties, lights, texture-map classes,
the environment slot, renderers.current, atmospherics, user properties and the MAXScript helper
functions from env/mapstore.py. It is NOT 3ds Max: renderer property names here are our own
guesses, so a passing test proves the logic, not the API names (those are CHECK items).

Usage:  import tests.standin_pymxs as s; s.install(renderer="vray")
"""
import math
import sys
import types


class Name(str):
    pass


class Point3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __repr__(self):
        return "[%g,%g,%g]" % (self.x, self.y, self.z)


class Cls:
    def __init__(self, name, superclass, defaults=None, factory=None):
        self.name, self.superclass, self.defaults = name, superclass, defaults or {}

    def __str__(self):
        return self.name

    def __call__(self, **kw):
        o = Obj(self)
        for k, v in self.defaults.items():
            setattr(o, k, v() if callable(v) else v)
        for k, v in kw.items():
            setattr(o, k, v)
        if self.superclass in ("light", "camera", "GeometryClass"):
            RT.all_nodes.append(o)
        return o


class Obj:
    _handle = 100

    def __init__(self, cls):
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "_props", {})
        Obj._handle += 1
        object.__setattr__(self, "inode", types.SimpleNamespace(handle=Obj._handle))
        object.__setattr__(self, "_user", {})

    def __getattr__(self, k):
        props = object.__getattribute__(self, "_props")
        if k in props:
            return props[k]
        raise AttributeError(k)

    def __setattr__(self, k, v):
        self._props[k] = v

    def __repr__(self):
        return "<%s %s>" % (self._cls.name, self._props.get("name", ""))


class Coords:
    def __init__(self):
        self.mappingType, self.mapping, self.U_Offset = 0, 0, 0.0


class Output:
    def __init__(self):
        self.output_amount = 1.0


class _Viewport:
    def __init__(self):
        self.cam = None

    def getCamera(self):
        return self.cam

    def setCamera(self, c):
        self.cam = c


class Runtime:
    def __init__(self, renderer="vray"):
        self.Name = Name
        self.Point3 = Point3
        self.all_nodes = []
        self.environmentMap = None
        self.useEnvironmentMap = False
        self.maps = {}
        self.atmos = []
        self.viewport = _Viewport()
        self.rootNode = Obj(Cls("RootNode", "node"))
        self.maxOps = types.SimpleNamespace(getNodeByHandle=self._by_handle)
        self.vp = {"solid": False, "disp": False, "image": ""}
        self.executed = []
        self.maxFileName, self.maxFilePath = "test.max", "D:/scenes/"
        self.renderWidth, self.renderHeight = 1920, 1080
        self.pathConfig = types.SimpleNamespace(getCurrentProjectFolder=lambda: "D:/project")
        # enough for core/storage.py and core/manager.py
        self.custAttributes = types.SimpleNamespace(add=lambda node, ca: setattr(node, "sm_json", ""))
        self.SM_SceneManagerDataCA = object()
        self.renderSceneDialog = types.SimpleNamespace(isOpen=lambda: False, close=lambda: None, open=lambda: None)
        self.setSaveRequired = lambda v: None
        light = lambda n, d: Cls(n, "light", dict({"on": True, "name": n, "pos": lambda: Point3(),
                                                    "controller": None, "target": None}, **d))
        self.VRaySun = light("VRaySun", {"intensity_multiplier": 1.0, "size_multiplier": 1.0, "shadows": True})
        self.CoronaSun = light("CoronaSun", {"intensity": 1.0, "sizeMultiplier": 1.0, "castShadows": True})
        self.VRayLight = light("VRayLight", {"type": 0, "multiplier": 1.0, "texmap": None, "texmap_on": False,
                                             "invisible": False})
        self.Omnilight = light("Omnilight", {"multiplier": 1.0})
        self.VRaySky = Cls("VRaySky", "textureMap", {"name": "VRaySky", "manual_sun_node": False, "sun_node": None})
        self.CoronaSky = Cls("CoronaSky", "textureMap", {"name": "CoronaSky", "intensity": 1.0})
        self.VRayBitmap = Cls("VRayBitmap", "textureMap", {"name": "VRayBitmap", "HDRIMapName": "", "mapType": 0,
                                                           "horizontalRotation": 0.0, "overall_mult": 1.0})
        self.Bitmaptexture = Cls("Bitmaptexture", "textureMap", {"name": "Bitmap", "filename": "",
                                                                 "coords": Coords, "output": Output})
        self.Checker = Cls("Checker", "textureMap", {"name": "Checker"})
        self.renderers = types.SimpleNamespace(current=None)
        self.set_renderer(renderer)

    # renderer -------------------------------------------------------------
    def set_renderer(self, r):
        if r == "vray":
            c = Cls("V_Ray_7", "renderer", {"environment_gi_on": False, "environment_gi_map": None,
                                             "environment_gi_map_on": False, "environment_rr_on": False,
                                             "environment_rr_map": None, "environment_rr_map_on": False})
        elif r == "corona":
            c = Cls("CoronaRenderer", "renderer", {"bg_overrideDirect": False, "bg_texmapDirect": None,
                                                   "bg_overrideReflect": False, "bg_texmapReflect": None,
                                                   "bg_overrideRefract": False, "bg_texmapRefract": None})
        else:
            c = Cls("Arnold", "renderer", {})
        self.renderers.current = c()

    # generic --------------------------------------------------------------
    def classOf(self, o):
        return o._cls if isinstance(o, Obj) else type(o).__name__

    def superClassOf(self, o):
        return o._cls.superclass

    def isProperty(self, o, n):
        return isinstance(o, Obj) and str(n) in o._props

    def getProperty(self, o, n):
        return o._props[str(n)]

    def setProperty(self, o, n, v):
        o._props[str(n)] = v

    def getPropNames(self, o):
        return list(o._props)

    @property
    def lights(self):
        return [n for n in self.all_nodes if n._cls.superclass == "light"]

    @property
    def cameras(self):
        return [n for n in self.all_nodes if n._cls.superclass == "camera"]

    def getNodeByName(self, name):
        for n in self.all_nodes:
            if n.name == name:
                return n
        return None

    def _by_handle(self, h):
        for n in self.all_nodes:
            if n.inode.handle == h:
                return n
        return None

    def getUserProp(self, n, k):
        return n._user.get(k)

    def setUserProp(self, n, k, v):
        n._user[k] = v

    def redrawViews(self):
        pass

    completeRedraw = redrawViews

    # atmospherics -----------------------------------------------------------
    @property
    def numAtmospherics(self):
        return len(self.atmos)

    def getAtmospheric(self, i):
        return self.atmos[i - 1]

    def isActive(self, a):
        return a.active

    def setActive(self, a, v):
        a.active = v

    # MAXScript ------------------------------------------------------------
    def execute(self, code):
        self.executed.append(code)
        c = code.strip()
        if c == "viewport.DispBkgImage":
            return self.vp["disp"]
        if c == "backgroundImageFileName":
            return self.vp["image"]
        if c == "viewport.IsSolidBackgroundColorMode()":
            return self.vp["solid"]
        if c.startswith("viewport.EnableSolidBackgroundColorMode"):
            self.vp["solid"] = "true" in c.split(";")[0]
            self.vp["disp"] = "DispBkgImage = true" in c
            if 'backgroundImageFileName = @"' in c:
                self.vp["image"] = c.split('backgroundImageFileName = @"')[1].split('"')[0]
            elif 'backgroundImageFileName = ""' in c:
                self.vp["image"] = ""
            return None
        return None   # definitions (custom attributes, helper fns) are faked below

    def SM_getMap(self, key):
        return self.maps.get(key)

    def SM_storeMap(self, key, m):
        self.maps[key] = m
        return m

    def SM_mapKeys(self):
        return list(self.maps)

    def SM_setZRot(self, n, a):
        n.zrot = float(a)

    def SM_getZRot(self, n):
        return n._props.get("zrot", 0.0)


RT = None


def install(renderer="vray"):
    """Put fake `pymxs` and `pymxs.runtime` into sys.modules. Returns the runtime."""
    global RT
    RT = Runtime(renderer)
    mod = types.ModuleType("pymxs")
    mod.runtime = RT

    class _Undo:
        def __init__(self, *a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    mod.undo = _Undo
    sys.modules["pymxs"] = mod
    sys.modules["pymxs.runtime"] = RT
    return RT


def atmospheric(name, active=True):
    a = Obj(Cls("VRayEnvironmentFog", "atmospheric"))
    a.name, a.active = name, active
    RT.atmos.append(a)
    return a
