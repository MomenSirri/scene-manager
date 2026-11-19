"""Diagnostics only: log what Windows tells the 3ds Max main window (activation, system commands, minimize).

Off unless the file ~/.scene_manager/trace_windows starts with "on". Lines go to ~/.scene_manager/app.log next to
the app's own lines, so the order of events in both programs can be read in one place. It changes nothing in Max.

TO CHECK IN MAX (not verified outside 3ds Max): QAbstractNativeEventFilter.nativeEventFilter receiving the MSG
address as int(message), and returning (False, 0) from it.
"""
import ctypes
import datetime
from ctypes import wintypes

from . import config

_filter = None
_NAMES = {0x0006: "WM_ACTIVATE", 0x001C: "WM_ACTIVATEAPP", 0x0086: "WM_NCACTIVATE", 0x0112: "WM_SYSCOMMAND",
          0x0018: "WM_SHOWWINDOW", 0x0005: "WM_SIZE", 0x0046: "WM_WINDOWPOSCHANGING", 0x0047: "WM_WINDOWPOSCHANGED", 0x0007: "WM_SETFOCUS",
          0x0008: "WM_KILLFOCUS", 0x0281: "WM_IME_SETCONTEXT", 0x0021: "WM_MOUSEACTIVATE"}
_KEYS = {0x01: "LMB", 0x02: "RMB", 0x5B: "Win", 0x5C: "Win", 0x12: "Alt", 0x11: "Ctrl", 0x10: "Shift"}


class _WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("after", ctypes.c_void_p), ("x", ctypes.c_int), ("y", ctypes.c_int),
                ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", ctypes.c_uint)]


def wanted():
    try:
        return (config.HOME / "trace_windows").read_text(encoding="utf-8", errors="ignore").strip().lower().startswith("on")
    except Exception:
        return False


def _log(text):
    try:
        stamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        with open(config.HOME / "app.log", "a", encoding="utf-8") as f:
            f.write("%s MAX %s\n" % (stamp, text))
    except Exception:
        pass


def dump_stack(why=""):
    """Every top-level window front to back, hidden ones too: handle, process, class, title, visible, owner."""
    try:
        u = ctypes.windll.user32
        u.GetTopWindow.restype = u.GetWindow.restype = ctypes.c_void_p
        u.GetTopWindow.argtypes = [ctypes.c_void_p]
        u.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        u.GetWindowLongPtrW.restype = ctypes.c_void_p
        u.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        rows, h, n = [], u.GetTopWindow(None), 0
        buf = ctypes.create_unicode_buffer(80)
        while h and n < 1500:
            n += 1
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(pid))
            u.GetClassNameW(ctypes.c_void_p(h), buf, 80)
            cls = buf.value
            u.GetWindowTextW(ctypes.c_void_p(h), buf, 60)
            ex = int(u.GetWindowLongPtrW(h, -20) or 0)
            rows.append("    %d pid %d %s '%s' %s%s%s owner %s" % (
                h, pid.value, cls, buf.value, "vis" if u.IsWindowVisible(ctypes.c_void_p(h)) else "HIDDEN",
                " TOP" if ex & 0x8 else "", " MIN" if u.IsIconic(ctypes.c_void_p(h)) else "", u.GetWindow(h, 4) or 0))
            h = u.GetWindow(h, 2)
        _log("stack %s (%d windows)\n%s" % (why, n, "\n".join(rows)))
    except Exception as e:
        _log("stack failed: %s" % e)


def start(max_hwnd):
    """Install the filter once. Returns True when it is running."""
    global _filter
    if _filter is not None or not max_hwnd or not wanted():
        return _filter is not None
    from PySide6 import QtCore, QtWidgets
    u = ctypes.windll.user32
    u.GetAsyncKeyState.restype = ctypes.c_short
    u.GetForegroundWindow.restype = ctypes.c_void_p
    u.GetWindow.restype = ctypes.c_void_p
    u.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    target = int(max_hwnd)

    class Filter(QtCore.QAbstractNativeEventFilter):
        def nativeEventFilter(self, event_type, message):
            try:
                msg = wintypes.MSG.from_address(int(message))
                h = int(msg.hWnd or 0)
                if msg.message in (0x0046, 0x0047) and h != target and int(u.GetWindow(h, 4) or 0) == target:
                    p = _WINDOWPOS.from_address(msg.lParam)   # a window owned by Max (toolbars, dialogs)
                    if not p.flags & 0x4:                       # only when its place in the stack changes
                        _log("owned %d %s flags=0x%x after=%s | foreground %s" % (
                            h, "CHANGING" if msg.message == 0x46 else "CHANGED", p.flags, p.after, u.GetForegroundWindow() or 0))
                if h == target and msg.message == 0x001C:   # WM_ACTIVATEAPP: Max gained or lost the foreground
                    QtCore.QTimer.singleShot(400, lambda w=msg.wParam: dump_stack("after Max %s" % ("activated" if w else "deactivated")))
                if msg.message in _NAMES and h == target:
                    extra = ""
                    if msg.message in (0x0046, 0x0047) and msg.lParam:
                        p = _WINDOWPOS.from_address(msg.lParam)
                        extra = " pos=%d,%d size=%dx%d flags=0x%x after=%s" % (p.x, p.y, p.cx, p.cy, p.flags, p.after)
                    keys = "+".join(sorted({n for vk, n in _KEYS.items() if u.GetAsyncKeyState(vk) & 0x8000})) or "-"
                    _log("%s w=0x%x l=0x%x%s | foreground %s | held %s" % (
                        _NAMES[msg.message], msg.wParam & 0xFFFFFFFFFFFFFFFF, msg.lParam & 0xFFFFFFFFFFFFFFFF, extra,
                        u.GetForegroundWindow() or 0, keys))
            except Exception:
                pass
            return False, 0

    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    _filter = Filter()
    app.installNativeEventFilter(_filter)
    _log("trace started for 3ds Max window %d" % target)
    dump_stack("at start")
    return True


def stop():
    global _filter
    if _filter is None:
        return
    try:
        from PySide6 import QtWidgets
        QtWidgets.QApplication.instance().removeNativeEventFilter(_filter)
    except Exception:
        pass
    _filter = None
    _log("trace stopped")
