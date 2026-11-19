"""Offscreen UI harness (no 3ds Max): builds a demo scene with the stand-in pymxs and opens the window.

    python -m tests.ui_harness shot.png      # save a screenshot
Used by tests/test_ui.py.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "standin_m2"), os.path.dirname(HERE)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SCENE_MANAGER_HOME", tempfile.mkdtemp(prefix="smhome_"))


def build(size=(1280, 800)):
    from pymxs import runtime as rt
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    rt.add("Cam01", "Targetcamera", "camera", keys=[10, 80])
    rt.add("Cam02", "Physical", "camera")
    rt.add("Key", "VRayLight", "light", on=True, multiplier=30.0, color=rt.Color(255, 240, 220))
    rt.add("Fill", "VRayLight", "light", on=True, multiplier=5.0, color=rt.Color(200, 220, 255))
    rt.add("Sun001", "VRaySun", "light", on=True, intensity_multiplier=1.0, size_multiplier=1.0)
    for i in range(6):
        rt.add("Tree_%02d" % i, "Editable_Poly", "geometry", layer="Vegetation")
    rt.add("Car", "Editable_Poly", "geometry", layer="Cars")
    rt.viewport.setCamera(rt.getNodeByName("Cam01"))
    from scene_manager.core import manager as M
    mgr = M.get_manager()
    ext = mgr.add_folder("Exterior")
    mgr.add_setup("Day", parent=ext["id"])
    mgr.add_setup("Dusk", parent=ext["id"])
    mgr.add_setup("Night", parent=ext["id"])
    mgr.add_folder("Interior")
    mgr.add_setup("Kitchen", parent="Interior")
    mgr.update_item("Dusk", tags=["client"], color="#ff9f0a")
    mgr.apply("Day")
    from scene_manager.ui import main_window
    win = main_window.AppWindow(None)
    win.resize(*size)
    win.show()
    app.processEvents()
    return app, win, mgr


if __name__ == "__main__":
    app, win, mgr = build()
    out = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
    win.panel.select(mgr.get("Day")["id"])
    app.processEvents()
    win.grab().save(out)
    print("saved", out)
