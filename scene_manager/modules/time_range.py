"""Frames: single frame, active segment, range, frame list, or the active camera's keys (M2).

Mode "camera": the range runs from the first to the last key of the setup's camera (and its
target, and animated camera parameters). It is evaluated on every activation, so re-animating the
camera needs no update. Keys are collected by a small MAXScript walker over sub-anims (CHECK IN MAX).
"""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register

MODES = {"single": 1, "active": 2, "range": 3, "frames": 4}  # rendTimeType values
MODE_BY_VALUE = {v: k for k, v in MODES.items()}
CAMERA_MODE = "camera"

_KEY_RANGE_MXS = r"""
global SM_collectKeys
fn SM_collectKeys a t d = (
    if a != undefined and d < 12 do (
        local c = try (a.controller) catch (undefined)
        if c != undefined do try (for k in c.keys do appendIfUnique t k.time) catch ()
        local n = try (a.numSubs) catch (0)
        for i = 1 to n do SM_collectKeys a[i] t (d + 1)
    )
    t
)
global SM_keyRange
fn SM_keyRange obj = (
    local t = #()
    SM_collectKeys obj t 0
    if isProperty obj #target and obj.target != undefined do SM_collectKeys obj.target t 0
    if t.count == 0 then undefined else #((amin t) as integer / TicksPerFrame, (amax t) as integer / TicksPerFrame)
)
"""
_mxs_ready = False


def camera_key_range(cam=None):
    """(first, last) key frame of a camera (default: the active viewport camera), or None."""
    global _mxs_ready
    cam = cam if cam is not None else rt.viewport.getCamera()
    if cam is None:
        return None
    if not _mxs_ready:
        rt.execute(_KEY_RANGE_MXS)
        _mxs_ready = True
    r = rt.SM_keyRange(cam)  # global MAXScript fn defined above, called through pymxs
    if r is None:
        return None
    r = list(r)
    return int(r[0]), int(r[1])


def _frame(expr):
    return int(rt.execute("((%s) as integer) / TicksPerFrame" % expr))


@register
class TimeModule(Module):
    key = "time"
    label = "Frames"
    order = 30
    category = "camera"
    column = "Frames"
    props = [
        Prop("mode", "Type", "enum", options=list(MODES.keys()) + [CAMERA_MODE],
             tip="camera = from the first to the last key of the setup's camera"),
        Prop("frame", "Frame", "int", minimum=-100000, maximum=100000),
        Prop("start", "Start", "int", minimum=-100000, maximum=100000),
        Prop("end", "End", "int", minimum=-100000, maximum=100000),
        Prop("nth", "Every Nth", "int", minimum=1, maximum=1000),
        Prop("frames", "Frame list", "text", tip="e.g. 1,3,5-12"),
    ]

    def capture(self):
        return {
            "mode": MODE_BY_VALUE.get(int(rt.rendTimeType), "single"),
            "frame": _frame("sliderTime"),
            "start": _frame("rendStart"),
            "end": _frame("rendEnd"),
            "nth": int(rt.rendNThFrame),
            "frames": str(rt.rendPickupFrames or ""),
        }

    def apply(self, values, context):
        mode = values.get("mode", "single")
        if mode == CAMERA_MODE:  # camera module (order 10) has already set the viewport camera
            r = camera_key_range()
            if r is None:
                mode = "single"  # camera not animated: render the current/stored frame
            else:
                values = dict(values, start=r[0], end=r[1])
                mode = "range"
        rt.rendTimeType = MODES[mode]
        if mode == "single":
            rt.execute("sliderTime = %df" % int(values["frame"]))
        elif mode == "range":
            start, end = int(values["start"]), int(values["end"])
            rt.execute("if %df < animationRange.start or %df > animationRange.end then "
                       "animationRange = interval (amin %df animationRange.start) (amax %df animationRange.end)"
                       % (start, end, start, end))
            rt.execute("rendStart = %df; rendEnd = %df" % (start, end))
            rt.rendNThFrame = max(1, int(values.get("nth", 1)))
        elif mode == "frames":
            rt.rendPickupFrames = values.get("frames", "")

    def differs(self, values, scene):
        if values.get("mode") == CAMERA_MODE:
            r = camera_key_range()
            want = {"mode": "range", "start": r[0], "end": r[1]} if r else {"mode": "single"}
            return {"mode"} if any(scene.get(k) != v for k, v in want.items()) else set()
        return super().differs(values, scene)

    def actions(self):
        def from_camera(v):
            r = camera_key_range()
            if r is None:
                raise RuntimeError("The active camera has no keys")
            return dict(v, mode="range", start=r[0], end=r[1])
        return [("Range from camera keys (fixed)", from_camera),
                ("Follow camera keys", lambda v: dict(v, mode=CAMERA_MODE))]

    def summary(self, values):
        m = values.get("mode")
        if m == CAMERA_MODE:
            return "camera keys"
        if m == "single":
            return str(values.get("frame", ""))
        if m == "range":
            return "%s-%s" % (values.get("start"), values.get("end"))
        if m == "frames":
            return values.get("frames", "")
        return "active" if m else ""
