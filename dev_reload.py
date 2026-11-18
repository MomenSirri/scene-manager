"""Run in 3ds Max (Scripting > Run Script) after editing code: reloads all modules and reopens the panel."""
import sys

old_ui = sys.modules.get("scene_manager.ui.main_window")
if old_ui is not None and getattr(old_ui, "_dock", None) is not None:
    old_ui._dock.close()
    old_ui._dock.deleteLater()
    old_ui._dock = None

for name in [m for m in sys.modules if m == "scene_manager" or m.startswith("scene_manager.")]:
    if name.endswith("bridge.max_server"):
        try:
            sys.modules[name].stop()
        except Exception:
            pass
    del sys.modules[name]

import scene_manager.startup  # noqa: E402
scene_manager.startup.init()
import scene_manager.ui.main_window as w  # noqa: E402
w.show()
