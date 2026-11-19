"""Bridge test without 3ds Max: python -m tests.test_bridge_events (needs PySide6).

Starts the real bridge server on the stand-in pymxs and talks to it the way the Scene Manager app does:
subscribe, call with an id, and expect a pushed "changed" event after an edit."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "standin_m2"), os.path.dirname(HERE)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SCENE_MANAGER_HOME"] = tempfile.mkdtemp(prefix="smhome_")


def main():
    try:
        from PySide6 import QtCore, QtNetwork
    except ImportError:
        print("skip bridge test (no PySide6)")
        return 0
    from pymxs import runtime as rt
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    rt.add("Cam01", "Targetcamera", "camera")
    rt.viewport.setCamera(rt.getNodeByName("Cam01"))
    from scene_manager import config
    from scene_manager.bridge import max_server
    port = max_server.start(port=18765)
    info = json.loads(config.BRIDGE_FILE.read_text())
    got = []
    sock = QtNetwork.QTcpSocket()
    buf = {"b": b""}

    def read():
        buf["b"] += bytes(sock.readAll())
        while b"\n" in buf["b"]:
            line, buf["b"] = buf["b"].split(b"\n", 1)
            got.append(json.loads(line))

    sock.readyRead.connect(read)
    sock.connectToHost("127.0.0.1", port)
    sock.waitForConnected(2000)

    def send(cmd, rid, **args):
        sock.write((json.dumps({"token": info["token"], "cmd": cmd, "args": args, "id": rid}) + "\n").encode())

    def pump(ms=150):
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(ms, loop.quit)
        loop.exec()

    fails = []

    def check(ok, text):
        print(("PASS " if ok else "FAIL ") + text)
        if not ok:
            fails.append(text)

    sock.write(b'{"token": "wrong", "cmd": "ui_state", "id": 9}\n')
    send("subscribe", 0)
    send("ui_schema", 1)
    send("ui_new_setup", 2, name="Day")
    pump()
    by_id = {m.get("id"): m for m in got if "id" in m}
    check(by_id[9]["ok"] is False, "wrong token is refused")
    check(by_id[0]["ok"] and by_id[1]["ok"] and len(by_id[1]["result"]["modules"]) > 10, "subscribe and schema answer with their ids")
    check(by_id[2]["ok"], "new setup created")
    check(any(m.get("event") == "changed" for m in got), "a 'changed' event is pushed after the edit")
    n = len([m for m in got if m.get("event") == "changed"])
    sid = by_id[2]["result"]["id"]
    send("ui_set_value", 3, id=sid, module="output", prop="width", value=2560)
    send("ui_item", 4, id=sid)
    pump()
    by_id = {m.get("id"): m for m in got if "id" in m}
    rows = {r["key"]: r for c in by_id[4]["result"]["cards"] if c["key"] == "output" for r in c["rows"]}
    check(rows["width"]["value"] == 2560 and rows["width"]["own"], "edit is stored and read back")
    events = len([m for m in got if m.get("event") == "changed"]) - n
    check(events == 1, "set + live apply give one event, not several (%d)" % events)
    max_server.stop()
    pump(50)
    check(any(m.get("event") == "closing" for m in got), "'closing' is sent when the bridge stops")
    print("\n%d failed" % len(fails) if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
