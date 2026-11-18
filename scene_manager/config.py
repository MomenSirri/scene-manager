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
    "backdrop_scheme": "lagoon",  # lagoon | aurora | deep_sea  # team folder for exported setups, e.g. a network share
}


def load():
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return data


def save(data):
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_bridge_info(port, token):
    HOME.mkdir(parents=True, exist_ok=True)
    BRIDGE_FILE.write_text(json.dumps({"port": port, "token": token, "pid": os.getpid()}), encoding="utf-8")


def clear_bridge_info():
    try:
        BRIDGE_FILE.unlink()
    except OSError:
        pass
