"""Run in 3ds Max (Scripting > Run Script): reloads the Scene Manager code and opens the app window."""
import sys

old = sys.modules.get("scene_manager.startup")
if old is not None and hasattr(old, "shutdown"):
    old.shutdown()
tr = sys.modules.get("scene_manager.dev_trace")
if tr is not None:
    tr.stop()
for name in [m for m in sys.modules if m == "scene_manager" or m.startswith("scene_manager.")]:
    if name.endswith("bridge.max_server"):
        try:
            sys.modules[name].stop()
        except Exception:
            pass
    del sys.modules[name]

import os  # noqa: E402
root = os.path.dirname(os.path.abspath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)
import scene_manager.startup  # noqa: E402
scene_manager.startup.init()
import scene_manager.app_launcher as a  # noqa: E402
print("Scene Manager app:", a.launch())
