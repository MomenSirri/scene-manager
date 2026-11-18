_modules = {}
_loaded = False

CATEGORIES = [
    # key, label, header colour
    ("camera", "Camera & frame", "#3b5168"),
    ("light", "Lights & sun", "#6a5a2a"),
    ("env", "Environment", "#2f5a52"),
    ("scene", "Scene", "#4a3f5e"),
    ("render", "Render", "#5e3b3b"),
    ("script", "Scripts", "#3f4a3f"),
]
CATEGORY_COLOR = {k: c for k, _, c in CATEGORIES}


def register(cls):
    inst = cls()
    _modules[inst.key] = inst
    return cls


def load_builtin():
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Import every file in scene_manager/modules (files starting with _ are skipped), so a new
    # module needs no edit here. A module file that fails to import is reported and skipped.
    import importlib
    import pkgutil
    import traceback
    from .. import modules as pkg
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        try:
            importlib.import_module(pkg.__name__ + "." + info.name)
        except Exception:
            print("Scene Manager: module file '%s' failed to load:" % info.name)
            traceback.print_exc()


def modules():
    load_builtin()
    return sorted(_modules.values(), key=lambda m: m.order)


def get(key):
    load_builtin()
    return _modules.get(key)
