"""Minimal pymxs stand-in for testing Scene Manager logic outside 3ds Max (not shipped)."""
import contextlib
import re


class Name(str):
    pass


class MaxClass:
    def __init__(self, name, superclass="", defaults=None):
        self.name, self.superclass, self.defaults = name, superclass, dict(defaults or {})

    def __call__(self, **kw):
        o = MaxObj(self, dict(self.defaults))
        o.__dict__["_props"].update(kw)
        return o

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, o):
        return isinstance(o, MaxClass) and o.name == self.name

    def __hash__(self):
        return hash(self.name)


class MaxObj:
    def __init__(self, cls, props):
        self.__dict__["_cls"] = cls
        self.__dict__["_props"] = props

    def __getattr__(self, k):
        p = self.__dict__["_props"]
        for key in p:
            if key.lower() == k.lower():
                return p[key]
        raise AttributeError(k)

    def __setattr__(self, k, v):
        p = self.__dict__["_props"]
        for key in p:
            if key.lower() == k.lower():
                p[key] = v
                return
        p[k] = v


class Color:
    def __init__(self, r, g, b, a=255.0):
        self.r, self.g, self.b, self.a = r, g, b, a

    def __eq__(self, o):
        return isinstance(o, Color) and (self.r, self.g, self.b, self.a) == (o.r, o.g, o.b, o.a)


class Point3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


COLOR_CLS, POINT3_CLS, NAME_CLS = MaxClass("Color"), MaxClass("Point3"), MaxClass("Name")


class Node(MaxObj):
    _next = [1]

    def __init__(self, cls, name, props):
        super().__init__(cls, dict(props, name=name))
        h = Node._next[0]
        Node._next[0] += 1
        self.__dict__["inode"] = type("I", (), {"handle": h})()


class ElementMgr:
    def __init__(self):
        self.els, self.active, self.files = [], True, {}

    def NumRenderElements(self):
        return len(self.els)

    def GetRenderElement(self, i):
        return self.els[i]

    def SetRenderElementFilename(self, i, p):
        self.files[i] = p

    def GetElementsActive(self):
        return self.active

    def SetElementsActive(self, b):
        self.active = b


class LayerMgr:
    def __init__(self):
        self.json = '{"layers":[]}'

    def saveLayersToJSON(self):
        return self.json

    def loadLayersFromJSON(self, s):
        self.json = s
        return True


class Presets:
    def __init__(self):
        self.loaded = []

    def LoadAll(self, i, f):
        self.loaded.append(("all", f))

    def LoadCategories(self, f):
        return ["Common", "V-Ray", "GI", "Settings", "Render Elements"]

    def Load(self, i, f, bits):
        self.loaded.append(("some", f, bits))

    def SaveAll(self, i, f):
        open(f, "w").write("rps")


class _NS:
    pass


class _Dummy:
    """Permissive value for runtime names other modules use (stand-in only)."""
    def __getattr__(self, k): return _Dummy()
    def __call__(self, *a, **k): return _Dummy()
    def __bool__(self): return False
    def __iter__(self): return iter(())
    def __len__(self): return 0
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __str__(self): return ""
    def __getitem__(self, i): raise IndexError(i)


class Runtime:
    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        return _Dummy()

    def __init__(self):
        self.reset()

    def reset(self):
        self.Name, self.Color, self.Point3 = Name, Color, Point3
        self.V_Ray_7 = MaxClass("V_Ray_7", "RendererClass", {
            "imageSampler_type_new": 1, "twoLevel_threshold": 0.01, "twoLevel_baseSubdivs": 1,
            "twoLevel_fineSubdivs": 24, "progressive_noise_threshold": 0.005, "progressive_max_render_time": 1.0,
            "gi_on": True, "gi_primary_type": 2, "gi_secondary_type": 3, "lightcache_subdivs": 1000,
            "options_displacement": True, "options_maxDepth_on": False, "options_maxDepth": 5,
            "output_splitgbuffer": False, "output_splitfilename": "", "output_saveRawFile": False,
            "output_rawFileName": "", "colorMapping_type": 6, "system_region_x": 64,
            "environment_gi_on": False, "filter_kernel": None, "colorMapping_darkMult": 1.0})
        self.CoronaRenderer = MaxClass("CoronaRenderer", "RendererClass", {
            "adaptivity_targetError": 2.0, "progressive_passLimit": 0, "progressive_timeLimit": 0,
            "denoise_filterType": 0, "denoise_blendAmount": 0.65, "gi_primarySolver": 0, "gi_secondarySolver": 3,
            "shading_maxRayDepth": 25, "shading_maxSampleIntensity": 20.0, "lights_samplesMult": 2.0,
            "colorMap_simpleExposure": 0.0, "colorMap_highlightCompression": 1.0, "bloomGlare_enabled": False})
        self.Arnold = MaxClass("Arnold", "RendererClass", {"AA_samples": 3, "GI_diffuse_samples": 2})
        self.Default_Scanline_Renderer = MaxClass("Default_Scanline_Renderer", "RendererClass", {"antiAliasing": True})
        self.RendererClass = _NS()
        self.RendererClass.classes = [self.Default_Scanline_Renderer, self.V_Ray_7, self.CoronaRenderer, self.Arnold]
        self.renderers = _NS()
        self.renderers.current = self.V_Ray_7()
        self._elmgr = ElementMgr()
        self.maxOps = _NS()
        self.maxOps.GetCurRenderElementMgr = lambda: self._elmgr
        self.maxOps.getNodeByHandle = lambda h: next((n for n in self._nodes if n.inode.handle == h), None)
        self._layers = LayerMgr()
        self.renderPresets = Presets()
        self._nodes = []
        self.lights = []
        self.cameras = []
        self.selection = []
        self.environmentMap = None
        self.renderWidth, self.renderHeight, self.renderPixelAspect = 1920, 1080, 1.0
        self.rendSaveFile, self.rendOutputFilename = False, ""
        self.maxFileName, self.maxFilePath = "Street.max", "C:/proj/"
        self.pathConfig = _NS()
        self.pathConfig.getCurrentProjectFolder = lambda: "C:/proj"
        self.renderSceneDialog = _NS()
        self.renderSceneDialog.isOpen = lambda: False
        self.renderSceneDialog.close = lambda: None
        self.renderSceneDialog.open = lambda: None
        self.rootNode = MaxObj(MaxClass("RootNode"), {})
        self.custAttributes = _NS()
        self.custAttributes.add = lambda n, ca: n.__setattr__("sm_json", "")
        self.SM_SceneManagerDataCA = None
        self._save_required = False
        self.viewport = _NS()
        self._cam = None
        self.viewport.getCamera = lambda: self._cam
        self.viewport.setCamera = lambda c: setattr(self, "_cam", c)
        self.rendTimeType, self.rendNThFrame, self.rendPickupFrames = 1, 1, ""
        self.LayerManager = _NS()
        self.LayerManager.count = 0

    # ---- scene helpers for tests ----
    def add_light(self, name, cls_name="VRayLight", **props):
        cls = MaxClass(cls_name, "light")
        n = Node(cls, name, dict({"on": True, "multiplier": 10.0}, **props))
        self._nodes.append(n)
        self.lights.append(n)
        return n

    def add_element(self, cls_name, name, **props):
        el = MaxObj(MaxClass(cls_name, "RenderElement"), dict({"elementName": name, "enabled": True}, **props))
        self._elmgr.els.append(el)
        return el

    # ---- runtime functions ----
    def classOf(self, v):
        if isinstance(v, MaxObj):
            return v._cls
        if isinstance(v, Color):
            return COLOR_CLS
        if isinstance(v, Point3):
            return POINT3_CLS
        if isinstance(v, Name):
            return NAME_CLS
        return MaxClass(type(v).__name__)

    def superClassOf(self, v):
        return MaxClass(v._cls.superclass) if isinstance(v, MaxObj) else MaxClass("Value")

    def isProperty(self, obj, name):
        if obj is None:
            return False
        if isinstance(obj, MaxObj):
            return any(k.lower() == str(name).lower() for k in obj._props)
        return hasattr(obj, str(name))

    def getProperty(self, obj, name):
        return getattr(obj, str(name))

    def setProperty(self, obj, name, v):
        if not self.isProperty(obj, name):
            raise RuntimeError("no property %s" % name)
        setattr(obj, str(name), v)

    def getPropNames(self, obj):
        return [Name(k) for k in obj._props if k != "name"]

    def getNodeByName(self, n):
        return next((x for x in self._nodes if x.name == n), None)

    def execute(self, s):
        s = s.strip()
        if s == "(vfbControl #getLayerMgr)[1]":
            return self._layers
        m = re.match(r"#\{([\d,]*)\}$", s)
        if m:
            return {int(x) for x in m.group(1).split(",") if x}
        if "SM_SceneManagerDataCA" in s:
            return None
        m = re.match(r"\(\((\w+)\) as integer\) / TicksPerFrame", s)
        if m:
            return 0
        if s.startswith("sliderTime ="):
            return None
        return None  # other MAXScript: ignored by the stand-in

    def setSaveRequired(self, b):
        self._save_required = b

    def redrawViews(self):
        pass


runtime = Runtime()


@contextlib.contextmanager
def undo(on, label=""):
    yield
