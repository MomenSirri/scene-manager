"""MCP server that lets Claude Code drive 3ds Max through the Scene Manager bridge.

Runs outside 3ds Max with normal Python 3.10+:  pip install -r claude_bridge/requirements.txt
Registered for this folder in .mcp.json, or globally with:
    claude mcp add 3dsmax -- python F:\\scene-manager\\claude_bridge\\mcp_server.py
"""
import json
import os
import socket
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HOME = Path(os.environ.get("SCENE_MANAGER_HOME", Path.home() / ".scene_manager"))
BRIDGE_FILE = HOME / "bridge.json"

mcp = FastMCP("3dsmax")


def _call(cmd, timeout=120.0, **args):
    if not BRIDGE_FILE.exists():
        raise RuntimeError("3ds Max bridge is not running. In 3ds Max open Scene Manager and turn on 'Claude bridge'.")
    info = json.loads(BRIDGE_FILE.read_text(encoding="utf-8"))
    try:
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=10) as s:
            s.settimeout(timeout)
            s.sendall((json.dumps({"token": info["token"], "cmd": cmd, "args": args}) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(1 << 16)
                if not chunk:
                    break
                buf += chunk
    except ConnectionRefusedError:
        raise RuntimeError("3ds Max is not listening (closed or bridge stopped). Start the bridge in Scene Manager.")
    reply = json.loads(buf.decode("utf-8"))
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error", "error") + "\n" + reply.get("traceback", ""))
    return reply["result"]


@mcp.tool()
def scene_info() -> dict:
    """Overview of the open 3ds Max scene: file, renderer, cameras, lights, layers, resolution, setups. Call this first."""
    return _call("scene_info")


@mcp.tool()
def inspect_node(name: str) -> dict:
    """All properties of one node (light, camera, object) with current values. Use before changing renderer-specific properties."""
    return _call("inspect_node", name=name)


@mcp.tool()
def list_setups() -> list:
    """List folders and setups (as paths like "Street / Dusk") with what each stores."""
    return _call("list_setups")


@mcp.tool()
def get_setup(name: str) -> dict:
    """One setup or folder: its own overrides and the effective (inherited + own) values."""
    return _call("get_setup", name=name)


@mcp.tool()
def apply_setup(name: str) -> dict:
    """Activate a setup (name or "Folder / Setup" path): apply its effective modules to the scene."""
    return _call("apply_setup", name=name)


@mcp.tool()
def capture_setup(name: str, modules: list[str] | None = None, folder: str | None = None) -> dict:
    """Save the current scene into a setup (creates it, inside `folder` if given, or re-captures it).
    Inside a folder only values that differ from the folder are stored. modules limits which modules."""
    return _call("capture_setup", name=name, modules=modules, folder=folder)


@mcp.tool()
def create_folder(name: str, parent: str | None = None) -> dict:
    """Create a folder. Values set on a folder pass down to every setup inside it."""
    return _call("create_folder", name=name, parent=parent)


@mcp.tool()
def move_item(name: str, folder: str | None = None) -> dict:
    """Move a setup or folder into another folder (None = top level)."""
    return _call("move_item", name=name, folder=folder)


@mcp.tool()
def set_module_values(name: str, module: str, values: dict | None = None, enabled: bool | None = None) -> dict:
    """Override module properties on a setup or folder, e.g. module="sun", values={"azimuth": 250, "elevation": 8}.
    enabled=False switches the module off there. Property names are listed in scene_info()["modules"]."""
    return _call("set_module_values", name=name, module=module, values=values, enabled=enabled)


@mcp.tool()
def update_setup_info(name: str, new_name: str | None = None, description: str | None = None,
                      tags: list[str] | None = None) -> dict:
    """Rename a setup or folder, or set its description and tags."""
    return _call("update_setup_info", name=name, new_name=new_name, description=description, tags=tags)


@mcp.tool()
def delete_setup(name: str) -> dict:
    """Delete a setup. Ask the user first."""
    return _call("delete_setup", name=name)


@mcp.tool()
def render_setups(names: list[str]) -> list:
    """Batch render setups locally, one after another. Blocks until done. Ask the user first."""
    return _call("render_setups", timeout=None, names=names)


@mcp.tool()
def set_sun_direction(azimuth: float, elevation: float, sun_name: str | None = None, distance: float | None = None) -> dict:
    """Move a sun light by compass angles in degrees. Azimuth 0 = north (+Y), 90 = east (+X). Elevation 0 = horizon, 90 = overhead."""
    return _call("set_sun_direction", azimuth=azimuth, elevation=elevation, sun_name=sun_name, distance=distance)


@mcp.tool()
def run_python(code: str) -> dict:
    """Run Python inside 3ds Max. Globals: rt (pymxs.runtime), pymxs, sm (setup manager). Assign `result` to return data. One undo step."""
    return _call("run_python", timeout=600, code=code)


@mcp.tool()
def run_maxscript(code: str) -> dict:
    """Run MAXScript inside 3ds Max and return the result as text. One undo step."""
    return _call("run_maxscript", timeout=600, code=code)


if __name__ == "__main__":
    mcp.run()
