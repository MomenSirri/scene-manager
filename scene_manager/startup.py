"""Called from the startup script written by install_scene_manager.ms.

Scene callbacks are kept cheap: each one only records what happened; the work runs once, a moment later,
on the main thread. Deleting 5,000 objects therefore costs one pass over the setups, not 5,000.
"""
import time

from pymxs import runtime as rt

from . import config

_PY = "python.execute \\\"import scene_manager.startup as s; s.%s\\\""
_EVENTS = (
    ("filePreOpen", "_busy(True)"), ("systemPreReset", "_busy(True)"), ("systemPreNew", "_busy(True)"),
    ("filePostOpen", "_on_scene_changed()"), ("systemPostReset", "_on_scene_changed()"),
    ("systemPostNew", "_on_scene_changed()"),
    ("filePostMerge", "_on_scene_edited()"), ("postRendererChange", "_on_scene_edited()"),
    ("nodeRenamed", "_on_renamed()"), ("nodePreDelete", "_on_deleted()"),
)
_CALLBACKS = "callbacks.removeScripts id:#SceneManager\n" + "\n".join(
    "callbacks.addScript #%s \"%s\" id:#SceneManager" % (ev, _PY % call) for ev, call in _EVENTS)

_loading = 0.0         # time a file open / scene reset started (0 = idle): node events are noise meanwhile
_LOADING_MAX = 300.0   # a cancelled or failed open never sends the "post" event; stop ignoring after this
_deleted = set()       # node names deleted since the last flush
_renamed = []          # (old, new) since the last flush
_edited = False
_timer = None


def init():
    rt.execute(_CALLBACKS)
    if config.load().get("bridge_autostart"):
        try:
            from .bridge import max_server
            max_server.start()
        except Exception as e:
            print("Scene Manager: Claude bridge not started: %s" % e)


def shutdown():
    """Remove our callbacks (dev_reload calls this before importing the code again)."""
    try:
        rt.execute("callbacks.removeScripts id:#SceneManager")
    except Exception:
        pass
    if _timer is not None:
        _timer.stop()


def _schedule():
    """Run _flush once, shortly after the last event of a burst."""
    global _timer
    try:
        from PySide6 import QtCore
    except ImportError:
        _flush()
        return
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setSingleShot(True)
        _timer.setInterval(150)
        _timer.timeout.connect(_flush)
    _timer.start()


def _flush():
    global _edited
    from .core import repair
    from .core.manager import get_manager
    mgr = get_manager()
    renamed, deleted, edited = list(_renamed), set(_deleted), _edited
    del _renamed[:]
    _deleted.clear()
    _edited = False
    notify = edited
    try:
        for old, new in renamed:
            mgr.on_node_renamed(old, new)
        for name in deleted:
            if rt.getNodeByName(name) is None and repair.on_node_deleted(mgr, name):
                notify = True
    except Exception as e:
        print("Scene Manager: scene event handling failed: %s" % e)
    if notify:
        mgr._notify()


def _is_loading():
    return bool(_loading) and time.monotonic() - _loading < _LOADING_MAX


def _busy(on):
    global _loading
    _loading = time.monotonic() if on else 0.0
    if on:
        del _renamed[:]
        _deleted.clear()


def _on_scene_changed():
    _busy(False)
    from .core.manager import get_manager
    get_manager().reload()


def _on_scene_edited():
    """Renderer switched or a file merged: cards and the status bar show scene values."""
    global _edited
    if not _is_loading():
        _edited = True
        _schedule()


def _on_renamed():
    if _is_loading():
        return
    p = rt.callbacks.notificationParam()
    vals = [str(x) for x in p] if p is not None else []
    # documented as #(oldName, newName); be tolerant if a node comes first
    if len(vals) >= 2:
        _renamed.append((vals[-2], vals[-1]))
        _schedule()


def _on_deleted():
    """Warn when a node used by setups is deleted (Repair missing nodes re-links it)."""
    if _is_loading():
        return
    try:
        n = rt.callbacks.notificationParam()
        if n is not None:
            _deleted.add(str(n.name))
            _schedule()
    except Exception as e:
        print("Scene Manager: delete check failed: %s" % e)
