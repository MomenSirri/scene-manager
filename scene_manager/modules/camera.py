"""Camera: the camera shown in the active viewport (and therefore rendered).

M2: "lock" locks the camera's (and its target's) move/rotate/scale so it cannot be nudged by
accident. API (CHECK IN MAX): setTransformLockFlags node #all | #none, getTransformLockFlags node
-> BitArray (.numberSet). A deleted or replaced camera is re-linked with Repair missing nodes.
"""
from pymxs import runtime as rt

from ..core import nodes
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
        if values.get("lock") is not None and _is_locked(cam) != bool(values["lock"]):
            flag = rt.Name("all" if values["lock"] else "none")
            for n in (cam, _target(cam)):
                if n is not None:
                    rt.setTransformLockFlags(n, flag)

    def summary(self, values):
        name = (values.get("camera") or {}).get("name", "")
        return name + (" (locked)" if name and values.get("lock") else "")


def _target(cam):
    try:
        return cam.target if rt.isProperty(cam, rt.Name("target")) else None
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
