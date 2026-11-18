"""MCP tools for the M2 scene modules. Loaded by mcp_server.py (_load_extra_tools)."""


def register(mcp, call):
    @mcp.tool()
    def capture_baseline(modules: list[str] | None = None) -> dict:
        """Record the current scene as the baseline every setup starts from, so activating a setup gives the
        same result whichever setup was active before. modules limits which modules (default: all)."""
        return call("capture_baseline", modules=modules)

    @mcp.tool()
    def clear_baseline(modules: list[str] | None = None) -> dict:
        """Remove the scene baseline (or only some modules from it)."""
        return call("clear_baseline", modules=modules)

    @mcp.tool()
    def get_baseline() -> dict:
        """The stored scene baseline: per-module summary and values."""
        return call("get_baseline")

    @mcp.tool()
    def restore_baseline() -> dict:
        """Put the scene back to the baseline (no setup active). Ask the user first."""
        return call("restore_baseline")

    @mcp.tool()
    def list_targets() -> dict:
        """Selection sets, layers (visible/renderable/frozen) and non-sun lights (on/intensity/colour)."""
        return call("list_targets")

    @mcp.tool()
    def set_lights(name: str, lights: dict, others: str | None = None) -> dict:
        """Store light states on a setup or folder (merged with what it already stores).
        lights = {"Key": {"on": false}, "Fill": {"intensity": 8, "color": [255, 230, 200]}}; a light set to null
        is removed (inherits again). others = "off" switches every unlisted light off, "keep" leaves them."""
        return call("set_lights", name=name, lights=lights, others=others)

    @mcp.tool()
    def set_layers(name: str, layers: dict, others: str | None = None) -> dict:
        """Store layer states on a setup or folder: {"Vegetation": {"on": false, "renderable": true, "frozen": false}}.
        null removes a row. others = "hide" hides every unlisted layer."""
        return call("set_layers", name=name, layers=layers, others=others)

    @mcp.tool()
    def set_object_rule(name: str, target: str, visible: bool | None = None, renderable: bool | None = None,
                        camera: bool | None = None, reflections: bool | None = None,
                        cast_shadows: bool | None = None, see_through: bool | None = None,
                        frozen: bool | None = None, remove: bool = False) -> dict:
        """Add or replace one Objects rule on a setup or folder. target = "set:Name" (selection set),
        "layer:Name", "pattern:Tree_*" (wildcard on names) or "node:Name". Omitted properties are left alone.
        More specific rules win: pattern < layer < set < node. remove=True deletes the rule."""
        return call("set_object_rule", name=name, target=target, visible=visible, renderable=renderable,
                    camera=camera, reflections=reflections, cast_shadows=cast_shadows,
                    see_through=see_through, frozen=frozen, remove=remove)

    @mcp.tool()
    def set_notes(name: str, text: str, append: bool = False) -> dict:
        """Set (or append to) the Notes of a setup or folder."""
        return call("set_notes", name=name, text=text, append=append)

    @mcp.tool()
    def todo(name: str, add: str | None = None, done: str | None = None, undone: str | None = None,
             remove: str | None = None) -> dict:
        """Edit a setup's to-do list: add an item, or mark done/undone/remove one by its text or 1-based number."""
        return call("todo", name=name, add=add, done=done, undone=undone, remove=remove)

    @mcp.tool()
    def find_missing_nodes() -> list:
        """Cameras, lights or objects that setups reference but that no longer exist (deleted or replaced)."""
        return call("find_missing_nodes")

    @mcp.tool()
    def repair_node(old_name: str, new_name: str) -> dict:
        """Re-link every setup reference from a missing node to an existing node."""
        return call("repair_node", old_name=old_name, new_name=new_name)

    @mcp.tool()
    def camera_key_range(camera: str | None = None) -> dict:
        """First and last key frame of a camera (default: the active viewport camera). For animation setups use
        set_module_values(module="time", values={"mode": "camera"}) to follow the keys automatically."""
        return call("camera_key_range", camera=camera)
