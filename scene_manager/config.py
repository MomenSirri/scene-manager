"""User config and bridge info, stored in ~/.scene_manager (shared with the MCP server)."""
import json
import os
from pathlib import Path

HOME = Path(os.environ.get("SCENE_MANAGER_HOME", Path.home() / ".scene_manager"))
CONFIG_FILE = HOME / "config.json"
BRIDGE_FILE = HOME / "bridge.json"

DEFAULTS = {
    "bridge_port": 8765,
    "bridge_autostart": True,
    "presets_folder": "",
    "glass_backdrop": True,  # patterned background behind translucent cards
    "backdrop_scheme": "lagoon",  # lagoon | aurora | deep_sea
    "debug_windows": False,  # log every window that opens to ~/.scene_manager/windows.log
}

_cache = None      # parsed config; the panel reads it many times per refresh, so do not hit the disk each time
_cache_stamp = None


def _stamp():
    try:
        st = CONFIG_FILE.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def load():
    """Config as a fresh dict (safe to modify). Re-read from disk only when the file changed."""
    global _cache, _cache_stamp
    stamp = _stamp()
    if _cache is None or stamp != _cache_stamp:
        data = dict(DEFAULTS)
        try:
            data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        _cache, _cache_stamp = data, stamp
    return json.loads(json.dumps(_cache))


def save(data):
    """Write atomically (a crash while saving must not leave half a config file)."""
    global _cache, _cache_stamp
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)
    _cache, _cache_stamp = json.loads(json.dumps(data)), _stamp()


def update(**fields):
    cfg = load()
    cfg.update(fields)
    save(cfg)
    return cfg


def write_bridge_info(port, token):
    HOME.mkdir(parents=True, exist_ok=True)
    BRIDGE_FILE.write_text(json.dumps({"port": port, "token": token, "pid": os.getpid()}), encoding="utf-8")


def clear_bridge_info():
    try:
        BRIDGE_FILE.unlink()
    except OSError:
        pass
