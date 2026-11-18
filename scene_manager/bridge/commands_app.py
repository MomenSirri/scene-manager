"""Keeps the Scene Manager app window attached to 3ds Max (Windows only).

The app makes its window an "owned" window of the 3ds Max main window, so Windows keeps it above Max (not above
other programs), hides it while Max is minimized and shows it again with Max. `ui_app_attach` is the handshake:
the app sends its window handle and gets the 3ds Max one back.
"""
import ctypes
import sys

from pymxs import runtime as rt

GWLP_HWNDPARENT = -8
GW_OWNER = 4
SW_SHOW, SW_RESTORE = 5, 9

_app = {"hwnd": 0}


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


def ui_app_attach(hwnd=0, from_max=False):
    """The app reports its window. With from_max, 3ds Max sets the owner itself (used when the app could not)."""
    _app["hwnd"] = int(hwnd or 0)
    owner = max_hwnd()
    owned = False
    u = _user32()
    if u and _app["hwnd"] and owner and u.IsWindow(_app["hwnd"]):
        if from_max:
            u.SetWindowLongPtrW(_app["hwnd"], GWLP_HWNDPARENT, owner)
        owned = (u.GetWindow(_app["hwnd"], GW_OWNER) or 0) == owner
    return {"max_hwnd": str(owner), "owned": owned}


def bring_to_front():
    """Show the app window that is already open. False when there is none (the caller then starts the app)."""
    u = _user32()
    hwnd = _app["hwnd"]
    if not u or not hwnd or not u.IsWindow(hwnd):
        _app["hwnd"] = 0
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
