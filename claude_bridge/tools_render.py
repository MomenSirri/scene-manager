"""MCP tools for the M4 render modules (loaded by mcp_server.py: register(mcp, call))."""
from typing import Any


def register(mcp, call):
    @mcp.tool()
    def render_info() -> dict:
        """Current renderer, installed renderers, curated render settings, render elements, number of settings
        changed vs defaults, and light groups. Call before changing render settings."""
        return call("render_info")

    @mcp.tool()
    def render_props(filter: str | None = None, changed_only: bool = False) -> dict:
        """Renderer properties with current and default values. filter = part of the name (e.g. "noise", "gi_").
        Use it to find exact property names; never guess them."""
        return call("render_props", filter=filter, changed_only=changed_only)

    @mcp.tool()
    def set_render_props(values: dict) -> dict:
        """Set renderer properties in the scene now, e.g. {"progressive_noise_threshold": 0.01}. Not stored in a
        setup: to store, use set_module_values (render_vray / render_corona / render_arnold, render_override) or
        fetch_render_overrides. Colours as {"color": [r, g, b, a]}."""
        return call("set_render_props", values=values)

    @mcp.tool()
    def fetch_render_overrides(name: str) -> dict:
        """Store on a setup or folder every renderer property that differs from the renderer defaults."""
        return call("fetch_render_overrides", name=name)

    @mcp.tool()
    def fetch_post_production(name: str) -> dict:
        """Store the current V-Ray frame buffer layers (incl. LightMix) or Corona tone mapping on a setup or folder."""
        return call("fetch_post_production", name=name)

    @mcp.tool()
    def save_render_preset(path: str) -> dict:
        """Save the current render settings as a .rps file (all categories). Ask before overwriting a file."""
        return call("save_render_preset", path=path)

    @mcp.tool()
    def add_custom_property(name: str, prop: str, target: str = "node", node: str | None = None,
                            path: str | None = None, value: Any = None) -> dict:
        """Store any property on a setup or folder (Custom properties module). target: node | renderer |
        environment | maxscript. path: dot path from the target ("material", "modifiers.1") or a MAXScript
        expression for target maxscript. value None keeps the current scene value."""
        return call("add_custom_property", name=name, prop=prop, target=target, node=node, path=path, value=value)
