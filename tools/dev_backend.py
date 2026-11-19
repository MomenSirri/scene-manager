"""Backend for working on the app without 3ds Max: the real Scene Manager core on the stand-in pymxs,
served over HTTP for `npm run dev` (POST /call {"cmd", "args"}).

    python tools/dev_backend.py          # then, in app/:  npm run dev
"""
import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tests", "standin_m2"), ROOT]
os.environ.setdefault("SCENE_MANAGER_HOME", tempfile.mkdtemp(prefix="smhome_"))


def demo_scene():
    from pymxs import runtime as rt
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
    for n in ("Day", "Dusk", "Night"):
        mgr.add_setup(n, parent=ext["id"])
    mgr.add_folder("Interior")
    mgr.add_setup("Kitchen", parent="Interior")
    mgr.update_item("Dusk", tags=["client"], color="#ff9f0a")
    mgr.set_values("Dusk", "sun", {"elevation": 8.0, "azimuth": 265.0})
    mgr.apply("Day")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        from scene_manager.bridge import commands
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            fn = commands.COMMANDS[req["cmd"]]
            body = {"ok": True, "result": fn(**(req.get("args") or {}))}
        except Exception as e:
            body = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        data = json.dumps(body, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    demo_scene()
    print("dev backend on http://127.0.0.1:8799")
    HTTPServer(("127.0.0.1", 8799), Handler).serve_forever()
