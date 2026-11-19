"""Makes the Scene Manager app window a tool window of 3ds Max (Windows only).

`ui_app_attach` is the handshake: the app sends its window handle and gets the 3ds Max main window back. The app then
makes 3ds Max the owner of its window (Win32 GWLP_HWNDPARENT, see app/electron/main.cjs), the relation a MAXScript
or Qt tool dialog has to Max: always above Max, minimized and restored with it, no taskbar button of its own.
With `from_max` 3ds Max sets the owner itself, for when the app is not allowed to (Max running as administrator).
"""
import ctypes
import sys

from pymxs import runtime as rt

GWLP_HWNDPARENT = -8
GW_OWNER = 4
SW_SHOW, SW_RESTORE = 5, 9

_app = {"hwnd": 0, "exe": "", "pid": 0}


def _user32():
    if sys.platform != "win32":
        return None
    u = ctypes.windll.user32
    vp = ctypes.c_void_p
    u.IsWindow.argtypes, u.IsWindow.restype = [vp], ctypes.c_int
    u.IsIconic.argtypes, u.IsIconic.restype = [vp], ctypes.c_int
    u.IsWindowVisible.argtypes, u.IsWindowVisible.restype = [vp], ctypes.c_int
    u.ShowWindow.argtypes, u.ShowWindow.restype = [vp, ctypes.c_int], ctypes.c_int
    u.SetForegroundWindow.argtypes, u.SetForegroundWindow.restype = [vp], ctypes.c_int
    u.GetWindow.argtypes, u.GetWindow.restype = [vp, ctypes.c_uint], vp
    u.SetWindowLongPtrW.argtypes, u.SetWindowLongPtrW.restype = [vp, ctypes.c_int, vp], vp
    return u


def max_hwnd():
    """Handle of the 3ds Max main window, 0 when unknown."""
    try:
        return int(rt.windows.getMAXHWND())
    except Exception:
        return 0


def ui_app_attach(hwnd=0, from_max=False, exe="", pid=0):
    """The app reports its window, program file and process, and gets the 3ds Max main window back.
    With `from_max`, 3ds Max makes itself the owner of the app window (used when the app could not)."""
    _app.update(hwnd=int(hwnd or 0), exe=str(exe or ""), pid=int(pid or 0))
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent   # the Scene Manager folder: the app runs Claude from it
    owner, owned = max_hwnd(), False
    u = _user32()
    if u and _app["hwnd"] and owner and u.IsWindow(_app["hwnd"]):
        if from_max:
            u.SetWindowLongPtrW(_app["hwnd"], GWLP_HWNDPARENT, owner)
        owned = (u.GetWindow(_app["hwnd"], GW_OWNER) or 0) == owner
    return {"max_hwnd": str(owner), "owned": owned, "root": str(root)}


def bring_to_front(exe=None):
    """Show the app window that is already open. False when there is none, or when the open one is another build
    than `exe` (an app from before the last update): the caller then replaces it."""
    import os
    u = _user32()
    hwnd = _app["hwnd"]
    if not u or not hwnd or not u.IsWindow(hwnd):
        _app["hwnd"] = 0
        return False
    if exe and os.path.normcase(os.path.abspath(_app["exe"] or "?")) != os.path.normcase(os.path.abspath(exe)):
        return False
    from . import max_server
    srv = max_server._server
    if srv is None or not srv._subscribers:
        return False
    u.ShowWindow(hwnd, SW_RESTORE if u.IsIconic(hwnd) else SW_SHOW)
    u.SetForegroundWindow(hwnd)  # allowed: 3ds Max is the foreground program when its button is pressed
    srv.emit_event("show")       # the app unrolls itself
    return True


COMMANDS = {"ui_app_attach": ui_app_attach}
