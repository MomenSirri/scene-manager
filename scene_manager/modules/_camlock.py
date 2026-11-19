"""Camera lock guard.

Max's transform locks (setTransformLockFlags) only stop the move/rotate/scale gizmos. Viewport
navigation through a camera view, the V-Ray/Corona frame buffer, scripts and other tools still move
the camera. The guard remembers the transform of each locked node and puts it back whenever
something changes it (a `when transform` change handler, run at the next redraw).

API (CHECK IN MAX): MAXScript `when transform <node> changes id:#smCamLock handleAt:#redrawViews`,
`deleteAllChangeHandlers id:#smCamLock`, Dictionary (Max 2017.1+), node[3].isAnimated (Transform subanim).
Animated nodes are not guarded (snapping back would rewrite their keys); they keep the native lock only.
"""
from pymxs import runtime as rt

_MXS = r"""
global smCamLockTM
global smCamLockBusy
if smCamLockTM == undefined do smCamLockTM = Dictionary #integer
if smCamLockBusy == undefined do smCamLockBusy = false
fn smCamLockSame a b = (
    local ok = true
    for i = 1 to 4 while ok do ok = (distance a[i] b[i]) < 0.0001
    ok
)
fn smCamLockEnforce n = (
    if not smCamLockBusy and isValidNode n do (
        local h = (getHandleByAnim n)
        if hasDictValue smCamLockTM h do (
            local tm = smCamLockTM[h]
            if not (smCamLockSame n.transform tm) do (
                smCamLockBusy = true
                try (with undo off (with animate off n.transform = tm)) catch ()
                smCamLockBusy = false
            )
        )
    )
)
fn smCamLockRebuild = (
    deleteAllChangeHandlers id:#smCamLock
    for h in smCamLockTM.keys do (
        local n = getAnimByHandle h
        if isValidNode n then (
            when transform n changes id:#smCamLock handleAt:#redrawViews nn do smCamLockEnforce nn
        ) else removeDictValue smCamLockTM h
    )
)
"""

_ready = False


def _init():
    global _ready
    if not _ready:
        rt.execute(_MXS)
        _ready = True


def _animated(node):
    try:
        return bool(rt.execute("(getAnimByHandle %d)[3].isAnimated" % int(rt.getHandleByAnim(node))))
    except Exception:
        return False


def guard(nodes_, on):
    """Start (on=True) or stop guarding the given nodes at their current transform."""
    _init()
    for n in nodes_:
        if n is None or not rt.isValidNode(n):
            continue
        h = int(rt.getHandleByAnim(n))
        if on and not _animated(n):
            rt.execute("smCamLockTM[%d] = (getAnimByHandle %d).transform" % (h, h))
        else:
            rt.execute("if hasDictValue smCamLockTM %d do removeDictValue smCamLockTM %d" % (h, h))
    rt.execute("smCamLockRebuild()")


def is_guarded(node):
    _init()
    try:
        return bool(rt.execute("hasDictValue smCamLockTM %d" % int(rt.getHandleByAnim(node))))
    except Exception:
        return False


def reset():
    """Forget every guard (a new scene was opened); handlers of deleted nodes go too."""
    global _ready
    try:
        rt.execute("deleteAllChangeHandlers id:#smCamLock; smCamLockTM = Dictionary #integer")
    except Exception:
        pass
    _ready = False
