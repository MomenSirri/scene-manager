# Working on and with Scene Manager

## Driving 3ds Max (MCP server "3dsmax")
- Call `scene_info` first. Use `inspect_node` before setting renderer-specific properties; never guess property names, read them.
- Sun and shadows: use `set_sun` (azimuth/elevation, or date + time + city or latitude/longitude/utc_offset; intensity; softness = sun size; shadows on/off; north offset). `sun_position` only calculates. `environment_info` shows sun, dome, sky/HDRI, GI/reflection overrides, atmospherics, viewport background. Environment: `set_environment` (none/sky/hdri/custom), `set_dome`, `set_env_overrides`, `set_atmosphere`, `list_hdris`; ask before `create_sun`. Pass `setup=` to also store the change on a setup. `set_sun_direction` still works for plain angles. If the sun is part of a Daylight system or Sun Positioner, change that system instead (inspect it first).
- For anything else use `run_python` (globals: `rt` = pymxs.runtime, `pymxs`, `sm` = setup manager; assign `result`). Prefer pymxs; use `run_maxscript` only when pymxs is awkward.
- Renderer differs per scene: check `scene_info.renderer_short` (vray / corona / arnold). Light and shadow properties differ per renderer.
- Setups live in folders; folder values pass down. Address setups by path, e.g. "Street / Dusk".
- To change a stored setup use `set_module_values` (module and property names are in `scene_info()["modules"]`). Put shared values on the folder, differences on the setup.
- After the user is happy with a look in the scene, save it with `capture_setup` (pass `folder` to file it).
- Render settings: call `render_info` first, then `render_props(filter=...)` to find exact renderer property names. `set_render_props` changes the scene now; to store on a setup use `set_module_values` with `render_vray` / `render_corona` / `render_arnold`, or `fetch_render_overrides`, `fetch_post_production`, `add_custom_property`.
- Lights, layers, objects: use `set_lights`, `set_layers`, `set_object_rule` (they merge rows); `list_targets` lists selection sets, layers and lights. `set_module_values` replaces a whole table.
- Objects targets: `set:Name`, `layer:Name`, `pattern:Tree_*`, `node:Name`. Prefer a selection set or pattern over many node rules.
- Before comparing or batch rendering setups, suggest `capture_baseline` if `get_baseline` is empty (setups then look the same whichever was active before).
- Missing cameras/lights after edits: `find_missing_nodes`, then `repair_node` (ask which node replaces it).
- Notes and to-dos per setup: `set_notes`, `todo`.
- Ask before `render_setups`, `delete_setup`, deleting nodes, or saving/overwriting the .max file.
- Keep changes small and report what you changed (node, property, old -> new).

## Working on the code
- Target 3ds Max 2025+ (Python 3.11, PySide6). Renderers: V-Ray, Corona, Arnold.
- One module per file in `scene_manager/modules`, subclass `core.module_base.Module`, declare `props` (cards are generated), keep values JSON-safe and keys stable. `apply()` always receives every prop.
- Store node references with `core.nodes.ref()` and read them with `core.nodes.resolve()`.
- Optional Module hooks (see `core/module_base.py`): `merge`, `differs`, `capture_baseline`, `available`, `reset`, `extend_context`, `touches_scene`. Prop kind `table` = {row: {column: value}} merged per row.
- New card widgets: `ui/kinds_<group>.py` calling `prop_kinds.register_kind`; new bridge commands: `bridge/commands_<group>.py` + `claude_bridge/tools_<group>.py`. No edits to registry, cards, commands or mcp_server needed.
- Flag any 3ds Max or renderer API call you are not sure exists so it can be checked in Max.
- UI updates in place: never rebuild cards or the setups tree to show a change. `ModuleCard.sync()`, `SetupTree.sync()` and `Panel.refresh_cards()` reconcile; a full board rebuild happens only when layout tokens change. Give card widgets a parent before show/hide. Run `python -m tests.test_ui` (offscreen) after UI edits; details in `docs/ui_overhaul.md`.
