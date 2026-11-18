"""Local TCP listener inside 3ds Max for Claude Code (via claude_bridge/mcp_server.py).

Listens on 127.0.0.1 only. Each request needs the random token written to ~/.scene_manager/bridge.json.
Protocol: one JSON line in {"token", "cmd", "args"}, one JSON line out {"ok", "result"|"error"}.
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

    def start(self):
        if not self.tcp.listen(QtNetwork.QHostAddress("127.0.0.1"), self.port):
            raise RuntimeError("Claude bridge could not listen on port %d: %s" % (self.port, self.tcp.errorString()))
        config.write_bridge_info(self.port, self.token)

    def stop(self):
        self.tcp.close()
        config.clear_bridge_info()

    def _on_new(self):
        while self.tcp.hasPendingConnections():
            sock = self.tcp.nextPendingConnection()
            self._buffers[id(sock)] = b""
            sock.readyRead.connect(lambda s=sock: self._on_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_closed(s))

    def _on_closed(self, sock):
        self._buffers.pop(id(sock), None)
        sock.deleteLater()

    def _on_read(self, sock):
        buf = self._buffers.get(id(sock), b"") + bytes(sock.readAll())
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                reply = self._handle(line)
                sock.write(json.dumps(reply, default=str).encode("utf-8") + b"\n")
                sock.flush()
        self._buffers[id(sock)] = buf

    def _handle(self, line):
        try:
            req = json.loads(line.decode("utf-8"))
            if not hmac.compare_digest(str(req.get("token", "")), self.token):
                return {"ok": False, "error": "bad token"}
            fn = commands.COMMANDS.get(req.get("cmd"))
            if fn is None:
                return {"ok": False, "error": "unknown command %r" % req.get("cmd")}
            return {"ok": True, "result": fn(**(req.get("args") or {}))}
        except Exception as e:
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "traceback": traceback.format_exc()}


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
