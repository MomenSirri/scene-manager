"""Called from the startup script written by install_scene_manager.ms."""
from pymxs import runtime as rt

from . import config

_CALLBACKS = r"""
callbacks.removeScripts id:#SceneManager
callbacks.addScript #filePostOpen "python.execute \"import scene_manager.startup as s; s._on_scene_changed()\"" id:#SceneManager
callbacks.addScript #systemPostReset "python.execute \"import scene_manager.startup as s; s._on_scene_changed()\"" id:#SceneManager
callbacks.addScript #systemPostNew "python.execute \"import scene_manager.startup as s; s._on_scene_changed()\"" id:#SceneManager
callbacks.addScript #nodeRenamed "python.execute \"import scene_manager.startup as s; s._on_renamed()\"" id:#SceneManager
callbacks.addScript #nodePreDelete "python.execute \"import scene_manager.startup as s; s._on_deleted()\"" id:#SceneManager
"""


def init():
    rt.execute(_CALLBACKS)
    if config.load().get("bridge_autostart"):
        try:
            from .bridge import max_server
            max_server.start()
        except Exception as e:
            print("Scene Manager: Claude bridge not started: %s" % e)


def _on_scene_changed():
    from .core.manager import get_manager
    get_manager().reload()


def _on_renamed():
    p = rt.callbacks.notificationParam()
    vals = [str(x) for x in p] if p is not None else []
    # documented as #(oldName, newName); be tolerant if a node comes first
    if len(vals) >= 2:
        old, new = vals[-2], vals[-1]
        from .core.manager import get_manager
        get_manager().on_node_renamed(old, new)


def _on_deleted():
    """M2: warn when a node used by setups is deleted (Repair missing nodes re-links it)."""
    try:
        n = rt.callbacks.notificationParam()
        if n is None:
            return
        from .core import repair
        from .core.manager import get_manager
        mgr = get_manager()
        if repair.on_node_deleted(mgr, str(n.name)):
            mgr._notify()
    except Exception as e:
        print("Scene Manager: delete check failed: %s" % e)
