"""Minimal pymxs stand-in for testing Scene Manager outside 3ds Max. Not a Max emulator."""
import contextlib
import re


class Name(str):
    pass


class Point3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Color:
    def __init__(self, r, g, b):
        self.r, self.g, self.b = float(r), float(g), float(b)

    def __eq__(self, o):
        return isinstance(o, Color) and (self.r, self.g, self.b) == (o.r, o.g, o.b)


class _Cls:
    def __init__(self, name, sup):
        self.name, self.sup = name, sup

    def __str__(self):
        return self.name


_handles = [100]


class Node:
    def __init__(self, name, cls, sup, **props):
        self.name = name
        self._cls = _Cls(cls, sup)
        _handles[0] += 1
        self.inode = type("I", (), {"handle": _handles[0]})()
        self.pos = Point3(0, 0, 0)
        self.controller = None
        self.isHidden = False
        self.renderable = True
        self.xray = False
        self.castShadows = True
        self.primaryVisibility = True
        self.secondaryVisibility = True
        self.isFrozen = False
        self.layer = None
        self.lockflags = set()
        self.keys = []
        self.__dict__.update(props)

    def __repr__(self):
        return "$%s" % self.name


class Layer:
    def __init__(self, name):
        self.name, self.on, self.renderable, self.isFrozen = name, True, True, False


class XRef:
    def __init__(self, fn):
        self.filename, self.disabled, self.hidden = fn, False, False


class _Viewport:
    def __init__(self, rt):
        self.rt, self.cam = rt, None

    def getCamera(self):
        return self.cam

    def setCamera(self, c):
        self.cam = c


class _Dlg:
    def isOpen(self):
        return False

    def close(self):
        pass

    def open(self):
        pass


class _LM:
    def __init__(self):
        self.layers = [Layer("0")]

    @property
    def count(self):
        return len(self.layers)

    def getLayer(self, i):
        return self.layers[i]

    def getLayerFromName(self, n):
        for l in self.layers:
            if l.name == n:
                return l
        return None

    def newLayerFromName(self, n):
        l = Layer(n)
        self.layers.append(l)
        return l


class _XRefs:
    def __init__(self):
        self.files = []

    def getXRefFileCount(self):
        return len(self.files)

    def getXRefFile(self, i):
        return self.files[i - 1]


class Runtime:
    def __init__(self):
        self.reset()

    def reset(self):
        self.nodes = []
        self.rootNode = type("Root", (), {})()
        self.viewport = _Viewport(self)
        self.renderSceneDialog = _Dlg()
        self.LayerManager = _LM()
        self.xrefs = _XRefs()
        self.selsets = {}
        self.renderWidth, self.renderHeight, self.renderPixelAspect = 1920, 1080, 1.0
        self.rendSaveFile, self.rendOutputFilename = False, ""
        self.rendTimeType, self.rendNThFrame, self.rendPickupFrames = 1, 1, ""
        self.sliderTime, self.rendStart, self.rendEnd = 0, 0, 100
        self.maxFilePath, self.maxFileName = "C:/scenes/", "test.max"
        self.environmentMap = None
        self.useEnvironmentMap = True
        self.executed = []
        self.renderers = type("R", (), {"current": _Cls("V_Ray_7", "renderer")})()
        self.units = type("U", (), {"SystemType": "centimeters"})()
        self.pathConfig = type("P", (), {"getCurrentProjectFolder": staticmethod(lambda: "C:/proj")})()
        self.sysInfo = type("S", (), {"username": "momen"})()

    # ---- scene building helpers for tests ----
    def add(self, name, cls, sup, layer="0", **props):
        n = Node(name, cls, sup, **props)
        n.layer = self.LayerManager.getLayerFromName(layer) or self.LayerManager.newLayerFromName(layer)
        self.nodes.append(n)
        return n

    def delete(self, n):
        self.nodes.remove(n)

    # ---- maxscript surface ----
    @property
    def objects(self):
        return list(self.nodes)

    @property
    def cameras(self):
        return [n for n in self.nodes if n._cls.sup == "camera"]

    @property
    def lights(self):
        return [n for n in self.nodes if n._cls.sup == "light"]

    @property
    def selection(self):
        return [n for n in self.nodes if getattr(n, "selected", False)]

    def classOf(self, n):
        if isinstance(n, _Cls):
            return n
        return n._cls if isinstance(n, Node) else type(n).__name__

    def superClassOf(self, n):
        return n._cls.sup

    def isProperty(self, obj, name):
        if obj is self.rootNode:
            return hasattr(obj, str(name))
        return hasattr(obj, str(name)) and not str(name).startswith("_")

    def getProperty(self, obj, name):
        return getattr(obj, str(name))

    def setProperty(self, obj, name, v):
        setattr(obj, str(name), v)

    def getPropNames(self, obj):
        return [Name(k) for k in obj.__dict__ if not k.startswith("_")]

    def getNodeByName(self, name):
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    @property
    def maxOps(self):
        rt = self

        class M:
            @staticmethod
            def getNodeByHandle(h):
                for n in rt.nodes:
                    if n.inode.handle == h:
                        return n
                return None
        return M

    @property
    def custAttributes(self):
        rt = self

        class C:
            @staticmethod
            def add(node, ca):
                node.sm_json = ""
        return C

    SM_SceneManagerDataCA = object()
    Color = Color
    Point3 = Point3
    Name = Name

    def execute(self, code):
        self.executed.append(code)
        m = re.match(r"\(\((\w+)\) as integer\) / TicksPerFrame", code)
        if m:
            return int(getattr(self, m.group(1)))
        m = re.match(r"sliderTime = (-?\d+)f", code)
        if m:
            self.sliderTime = int(m.group(1))
            return None
        m = re.search(r"rendStart = (-?\d+)f; rendEnd = (-?\d+)f", code)
        if m:
            self.rendStart, self.rendEnd = int(m.group(1)), int(m.group(2))
            return None
        m = re.match(r"SM_keyRange \$'(.*)'", code.strip())
        if m:
            n = self.getNodeByName(m.group(1).replace("\\'", "'"))
            if n is None or not n.keys:
                return None
            return [min(n.keys), max(n.keys)]
        return None

    def SM_keyRange(self, n):
        return [min(n.keys), max(n.keys)] if n.keys else None

    def setSaveRequired(self, v):
        pass

    def completeRedraw(self):
        pass

    def redrawViews(self):
        pass

    def maxVersion(self):
        return [27000]

    # transform locks
    def getTransformLockFlags(self, n):
        return type("BA", (), {"numberSet": len(n.lockflags)})()

    def setTransformLockFlags(self, n, flags):
        n.lockflags = set(range(1, 10)) if str(flags) == "all" else set()

    # named selection sets
    def getNumNamedSelSets(self):
        return len(self.selsets)

    def getNamedSelSetName(self, i):
        return list(self.selsets)[i - 1]

    def getNamedSelSetItemCount(self, i):
        return len(self.selsets[list(self.selsets)[i - 1]])

    def getNamedSelSetItem(self, i, j):
        return self.selsets[list(self.selsets)[i - 1]][j - 1]

    def isValidNode(self, n):
        return n in self.nodes


runtime = Runtime()


@contextlib.contextmanager
def undo(on, label=""):
    yield
