"""Open the Scene Manager app (the separate window) from 3ds Max.

The app ships as one zip (app/release/SceneManager-win.zip). It is unpacked once per version into
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
    if not ZIP.is_file():
        return None
    st = ZIP.stat()
    base = config.HOME / "app"
    target = base / ("%d_%d" % (st.st_mtime_ns // 10**9, st.st_size))
    exe = target / EXE_NAME
    if not exe.is_file():
        print("Scene Manager: unpacking the app (first start of this version)...")
        tmp = base / (target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(tmp)
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        for old in base.iterdir():  # keep only the current version
            if old != target and old.is_dir():
                shutil.rmtree(old, ignore_errors=True)
    return str(exe)


def launch():
    """Start the bridge and the app. Falls back to the panel inside 3ds Max when no app build is present."""
    from .bridge import max_server
    if not max_server.is_running():
        max_server.start()
    exe = _app_exe()
    if exe is None:
        print("Scene Manager: no app build at %s; opening the panel inside 3ds Max instead." % ZIP)
        from .ui import main_window
        return main_window.show()
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("QT_", "PYTHON"))}  # Max's own Qt/Python settings must not leak in
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([exe], cwd=os.path.dirname(exe), env=env, close_fds=True, creationflags=flags)
    return exe
