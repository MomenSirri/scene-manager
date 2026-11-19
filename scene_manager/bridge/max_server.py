"""Local TCP listener inside 3ds Max for Claude Code (via claude_bridge/mcp_server.py).

Listens on 127.0.0.1 only. Each request needs the random token written to ~/.scene_manager/bridge.json.
Protocol: one JSON line in {"token", "cmd", "args", "id"?}, one JSON line out {"ok", "result"|"error", "id"?}.
A client that sends cmd "subscribe" keeps its connection open and also receives event lines
{"event": "changed"} whenever setups or the scene state change (the Scene Manager app uses this).
Qt signals run on the Max main thread, so pymxs calls are safe here.
"""
import hmac
import json
import secrets
import traceback

from PySide6 import QtCore, QtNetwork

from .. import config
from . import commands

_server = None


class BridgeServer(QtCore.QObject):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.token = secrets.token_hex(16)
        self.tcp = QtNetwork.QTcpServer(self)
        self.tcp.newConnection.connect(self._on_new)
        self._buffers = {}
        self._subscribers = []
        self._socks = []
        # many changes in one go (an activation touches a dozen modules) become one event
        self._event_timer = QtCore.QTimer(self)
        self._event_timer.setSingleShot(True)
        self._event_timer.setInterval(30)
        self._event_timer.timeout.connect(lambda: self.emit_event("changed"))

    def start(self):
        if not self.tcp.listen(QtNetwork.QHostAddress("127.0.0.1"), self.port):
            raise RuntimeError("Claude bridge could not listen on port %d: %s" % (self.port, self.tcp.errorString()))
        config.write_bridge_info(self.port, self.token)
        from ..core.manager import get_manager
        get_manager().add_listener(self._event_timer.start)
        commands._log_listeners.append(self._event_timer.start)

    def stop(self):
        from ..core.manager import get_manager
        get_manager().remove_listener(self._event_timer.start)
        if self._event_timer.start in commands._log_listeners:
            commands._log_listeners.remove(self._event_timer.start)
        self._event_timer.stop()
        self.emit_event("closing")
        for sock in list(self._socks):  # connected apps see the bridge go at once
            try:
                sock.disconnectFromHost()
            except RuntimeError:
                pass
        self.tcp.close()
        config.clear_bridge_info()

    def emit_event(self, name, **data):
        line = json.dumps(dict(data, event=name)).encode("utf-8") + b"\n"
        for sock in list(self._subscribers):
            try:
                sock.write(line)
                sock.flush()
            except RuntimeError:  # socket already deleted
                self._subscribers.remove(sock)

    def _on_new(self):
        while self.tcp.hasPendingConnections():
            sock = self.tcp.nextPendingConnection()
            self._buffers[id(sock)] = b""
            self._socks.append(sock)
            sock.readyRead.connect(lambda s=sock: self._on_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_closed(s))

    def _on_closed(self, sock):
        self._buffers.pop(id(sock), None)
        for group in (self._subscribers, self._socks):
            if sock in group:
                group.remove(sock)
        try:
            sock.deleteLater()
        except RuntimeError:  # already gone with the server
            pass

    def _on_read(self, sock):
        buf = self._buffers.get(id(sock), b"") + bytes(sock.readAll())
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                reply = self._handle(line, sock)
                sock.write(json.dumps(reply, default=str).encode("utf-8") + b"\n")
                sock.flush()
        self._buffers[id(sock)] = buf

    def _handle(self, line, sock=None):
        rid = None
        try:
            req = json.loads(line.decode("utf-8"))
            rid = req.get("id")
            if not hmac.compare_digest(str(req.get("token", "")), self.token):
                return {"ok": False, "error": "bad token", "id": rid}
            if req.get("cmd") == "subscribe":
                if sock is not None and sock not in self._subscribers:
                    self._subscribers.append(sock)
                return {"ok": True, "result": {"subscribed": True}, "id": rid}
            fn = commands.COMMANDS.get(req.get("cmd"))
            if fn is None:
                return {"ok": False, "error": "unknown command %r" % req.get("cmd"), "id": rid}
            return {"ok": True, "result": fn(**(req.get("args") or {})), "id": rid}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "traceback": traceback.format_exc(),
                    "id": rid}


def is_running():
    return _server is not None


def start(port=None):
    global _server
    if _server is None:
        srv = BridgeServer(port or config.load()["bridge_port"])
        srv.start()
        _server = srv
        print("Scene Manager: Claude bridge listening on 127.0.0.1:%d" % srv.port)
    return _server.port


def stop():
    global _server
    if _server is not None:
        _server.stop()
        _server = None
