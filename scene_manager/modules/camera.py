"""Camera: the camera shown in the active viewport (and therefore rendered).

M2: "lock" locks the camera's (and its target's) move/rotate/scale so it cannot be nudged by
accident. API (CHECK IN MAX): setTransformLockFlags node #all | #none, getTransformLockFlags node
-> BitArray (.numberSet). A deleted or replaced camera is re-linked with Repair missing nodes.
Native locks only stop the gizmos, so a locked camera is also guarded (see _camlock): viewport
navigation, the frame buffer or scripts that move it are undone at the next redraw.
"""
from pymxs import runtime as rt

from ..core import nodes
from . import _camlock
from ..core.module_base import Module, Prop
from ..core.registry import register


@register
class CameraModule(Module):
    key = "camera"
    label = "Camera"
    order = 10
    category = "camera"
    column = "Camera"
    props = [Prop("camera", "Camera", "camera"),
             Prop("lock", "Lock camera", "bool", tip="Lock move/rotate/scale of the camera and its target")]

    def capture(self):
        cam = rt.viewport.getCamera()
        return {"camera": nodes.ref(cam) if cam is not None else None,
                "lock": _is_locked(cam) if cam is not None else False}

    def apply(self, values, context):
        r = values.get("camera")
        if not r:
            return
        cam = nodes.resolve(r)
        if cam is None:
            raise RuntimeError("camera '%s' not found" % r.get("name"))
        rt.viewport.setCamera(cam)
        if values.get("lock") is not None:
            set_lock(cam, bool(values["lock"]))

    def summary(self, values):
        name = (values.get("camera") or {}).get("name", "")
        return name + (" (locked)" if name and values.get("lock") else "")


def set_lock(cam, on):
    """Native transform locks plus the guard, on the camera and its target."""
    pair = [n for n in (cam, _target(cam)) if n is not None]
    if _is_locked(cam) != on:
        for n in pair:
            rt.setTransformLockFlags(n, rt.Name("all" if on else "none"))
    if on != _camlock.is_guarded(cam):
        _camlock.guard(pair, on)


def sync_guards():
    """After a file opens: guard every camera that is saved with all transforms locked."""
    _camlock.reset()
    locked = [c for c in rt.cameras if rt.superClassOf(c) == rt.camera and _is_locked(c)]
    pair = [n for c in locked for n in (c, _target(c)) if n is not None]
    if pair:
        _camlock.guard(pair, True)


def _target(cam):
    try:
        t = cam.target if rt.isProperty(cam, rt.Name("target")) else None
        return t if t is not None and rt.isValidNode(t) else None
    except Exception:
        return None


def _is_locked(node):
    try:
        flags = rt.getTransformLockFlags(node)
        try:
            return int(flags.numberSet) >= 9
        except AttributeError:
            return len(list(flags)) >= 9
    except Exception:
        return False
