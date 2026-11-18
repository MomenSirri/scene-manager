"""Open the Scene Manager app (the separate window) from 3ds Max.

The app ships as one zip (app/release/SceneManager-win.zip, or the same file in pieces .001, .002, ...). It is unpacked once per version into
~/.scene_manager/app/<stamp>/ and started from there, so later launches are instant. 3ds Max only starts
the bridge and the app; the app then connects by itself and reconnects when Max restarts.
"""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from . import config

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "app" / "release" / "SceneManager-win.zip"
EXE_NAME = "Scene Manager.exe"


def _app_exe():
    """Path of the unpacked app, unpacking the zip first when it is new. None when there is no app build."""
    custom = config.load().get("app_path")
    if custom and os.path.isfile(custom):
        return custom
    parts = sorted(ZIP.parent.glob(ZIP.name + ".[0-9][0-9][0-9]")) if ZIP.parent.is_dir() else []
    if not ZIP.is_file() and not parts:
        return None
    base = config.HOME / "app"
    if ZIP.is_file():
        source, st = ZIP, ZIP.stat()
        stamp = "%d_%d" % (st.st_mtime_ns // 10**9, st.st_size)
    else:  # delivered in pieces (SceneManager-win.zip.001, .002, ...): joined on first start
        source = None
        stamp = "p%d_%d" % (max(p.stat().st_mtime_ns for p in parts) // 10**9, sum(p.stat().st_size for p in parts))
    target = base / stamp
    exe = target / EXE_NAME
    if not exe.is_file():
        print("Scene Manager: unpacking the app (first start of this version)...")
        tmp = base / (target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        base.mkdir(parents=True, exist_ok=True)
        joined = None
        if source is None:
            joined = source = base / "package.zip"
            with open(joined, "wb") as out:
                for part in parts:
                    with open(part, "rb") as f:
                        shutil.copyfileobj(f, out)
        with zipfile.ZipFile(source) as z:
            z.extractall(tmp)
        if joined is not None:
            joined.unlink()
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        for old in base.iterdir():  # keep only the current version
            if old != target and old.is_dir() and not old.name.endswith(".tmp"):
                shutil.rmtree(old, ignore_errors=True)
    return str(exe)


def _stop_other_builds(exe):
    """Close a running Scene Manager app that is not this build. Without this the old app keeps answering (one app
    at a time) and a new build never starts until the user closes the window by hand."""
    if os.name != "nt":
        return
    script = ("Get-Process -Name 'Scene Manager' -ErrorAction SilentlyContinue | "
              "Where-Object { $_.Path -and $_.Path -ne '%s' } | Stop-Process -Force" % exe.replace("'", "''"))
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Scene Manager: could not close an older app window (%s). Close it by hand if the new one does not open." % e)


def launch():
    """Start the bridge and the app. Falls back to the panel inside 3ds Max when no app build is present."""
    from .bridge import max_server
    if not max_server.is_running():
        max_server.start()
    from .bridge import commands_app
    exe = _app_exe()
    if exe is not None and commands_app.bring_to_front(exe):  # this build is already open: the button brings it back
        return "already open"
    if exe is None:
        print("Scene Manager: no app build at %s; opening the panel inside 3ds Max instead." % ZIP)
        from .ui import main_window
        return main_window.show()
    _stop_other_builds(exe)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "PYTHON"))}  # Max's own Qt/Python settings must not leak in
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    # the app attaches its window to this 3ds Max window (stays above Max, hides and returns with it)
    subprocess.Popen([exe, "--max-hwnd=%d" % commands_app.max_hwnd()], cwd=os.path.dirname(exe), env=env, close_fds=True, creationflags=flags)
    return exe
