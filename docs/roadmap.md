# Roadmap: Momen's target spec (2.6.3 modules + v3 beta features)

Renderers: V-Ray, Corona, Arnold (Pulze v3 does not list Arnold; we support it). 3ds Max 2025+. Local rendering only for now.
Each milestone ends with code you can run in Max. One module per step inside a milestone.

| # | Milestone | Contents | Status |
|---|---|---|---|
| M1 | Core + panel | Folder tree with inherited values, per-property overrides, tags, colours, thumbnails, dockable panel, Camera, Resolution & Output, Frames, Sun (direction, on, intensity, softness), local batch render, team presets, Claude bridge | **Built, needs test in Max** |
| M2 | Scene | Deterministic activation (scene baseline, so a setup looks the same whichever setup was active before), Lights (on/off + properties), Layers (visible/freeze/render), Objects (scales past 20 via selection sets / name patterns), Xref Scene, Notes, Todo, camera lock + repair on rename/delete, Frames from camera keys | **Built, needs test in Max** (see M2 notes below) |
| M3 | Lighting & environment | Sun sky creation (V-Ray Sky, Corona Sky, Arnold Physical Sky) and env slot, Sun dial by date/time/location (own solar-position maths), Dome light + HDRI, HDRI browser with favourite folders and thumbnails, Environment modes None/Sky/HDRI/Custom, GI and reflection environment overrides, Atmosphere, Viewport background | **Built, passes stand-in tests, needs test in Max** (see docs/m3_test_in_max.md) |
| M4 | Render | Render settings (curated per renderer), Render settings override (diff against a fetched default), .rps preset, Render elements on/off, V-Ray channels/raw output, Post-production (V-Ray VFB layers, Corona tone mapping), LightMix, Output builder ({version} auto-increment, custom tokens), Custom properties (any property of any node) | **Built, needs test in Max** (see docs/m4_render.md) |
| M5 | Workflow | Scripts (pre/post setup, pre/post render), Materials module + material overrides, Colour corrections, Variations (axes x options, every combination generated and named), Templates, Live mode / camera sync, Preview mode | |
| M6 | Claude & comments | Comments pinned to viewport or VFB shots, linked to objects/lights, assignable to a teammate or Claude; Claude picks them up through the MCP server and replies with what changed | |
| M7 | Output & pipeline | Bake to native Scene States, render presets and Batch Render; save one .max (or .vrscene) per setup; background rendering in a separate 3dsmaxbatch process; Chaos Vantage; farm submit later | |

Skipped on purpose: Assets, Plugins, Render Manager (removed by Pulze in 2.6.3); RenderFlow buttons (local only for now).

## Needs screenshots from the original
The public docs do not list the properties inside Render Settings, Lights and Custom Properties, nor every v3 module. Screenshots of those cards would become the spec for M2 and M4.

## M2 notes (built 2026-11-17)
| Item | Where | How |
|---|---|---|
| Deterministic activation | `core/manager.py` (baseline), `ui/scene_tools.py` | Setup menu > Scene baseline > Capture. Props/modules a setup does not store come from the baseline, not from whatever the last setup left. Without a baseline M1 behaviour stays (current scene fills the gaps). Status bar shows "baseline" when one exists |
| Lights | `modules/lights.py` | Table: on / intensity / colour per non-sun light, merged per light from folder to setup. "Lights not listed: off" switches every other light off |
| Layers | `modules/layers.py` | Table: visible / render / frozen per layer. "Layers not listed: hide" |
| Objects | `modules/objects.py` | Rules by `set:`, `layer:`, `pattern:` (wildcards) or `node:`; specific beats broad. Properties: visible, renderable, camera, reflections, shadows, see-through, frozen; square = leave alone. Objects changed by the previous setup are put back first |
| XRef Scenes | `modules/xref_scenes.py` | Table: enabled / visible per XRef scene |
| Notes, To do | `modules/notes.py`, `modules/todo.py` | Bookkeeping only (`touches_scene = False`), added with + Add Module |
| Camera lock | `modules/camera.py` | "Lock camera" locks move/rotate/scale of camera and target |
| Repair on rename/delete | `core/repair.py`, `startup.py`, `ui/scene_tools.py` | Renames follow automatically (table rows too). Deleting a used node shows a warning in the status bar; Setup menu > Repair missing nodes re-links |
| Frames from camera keys | `modules/time_range.py` | Frames type "camera" follows the setup camera's keys on every activation; card menu "Range from camera keys" stores a fixed range |
| Stand-in test | `tests/test_m2.py` | `python tests/test_m2.py` (no Max needed) runs every M2 feature against `tests/standin_m2/pymxs.py` |
| Claude bridge | `bridge/commands_scene.py`, `claude_bridge/tools_scene.py` | capture/clear/get/restore_baseline, list_targets, set_lights, set_layers, set_object_rule, set_notes, todo, find_missing_nodes, repair_node, camera_key_range |

### Shared files changed by M2 (all additive; M1 behaviour kept when the new hooks are unused)
- `core/module_base.py`: Prop kinds `table`, `note`, `todo` and `Prop.columns`; Module hooks `merge`, `differs`, `capture_baseline`, `available`, optional `reset`, attribute `touches_scene`; helper `merge_table`.
- `core/manager.py`: `module_state` merges through `Module.merge` (tables merge per row); `_capture_into` stores only differing table rows and uses `available()` for default lists; `apply` uses the baseline and the `reset` hook; `differs_from_scene` uses `Module.differs`; new `baseline`, `capture_baseline`, `clear_baseline`, `restore_baseline`; `context` calls the optional `extend_context` hook (asked for by M4); `on_node_renamed` also renames table rows.
- `core/manager.py` (later): a module whose `capture()` fails no longer stops a new setup (it is skipped and printed); `capture_baseline` returning None keeps a module out of the baseline (LightMix, Custom properties and VFB post use this so they don't undo Lights on every activation).
- Ownership: Sun module owns suns, Dome light module (M3) owns dome lights; the Lights module skips both.
- `core/registry.py`: modules are auto-imported from `scene_manager/modules` (M3 wrote the final version).
- `ui/cards.py`: extra prop kinds come from `ui/prop_kinds.py` (`register_kind`, auto-loads `ui/kinds_*.py`); wide kinds get a full-width row.
- `ui/main_window.py`: status line shows baseline / missing-node warning; setup menus get Scene baseline + Repair missing nodes.
- `startup.py`: `#nodePreDelete` callback.
- `modules/camera.py`, `modules/time_range.py`: lock, camera-keys mode.

### Max API calls to check (M2)
| Call | Used for | Sure? |
|---|---|---|
| `light.on`, `.multiplier` / `.intensity`, `.color` / `.rgb` / `.colorDirect` | Lights | on/multiplier/intensity yes; Corona colour property name unsure |
| `LayerManager.getLayer i`, `.getLayerFromName`, layer `.on .renderable .isFrozen` | Layers | yes |
| `getNumNamedSelSets`, `getNamedSelSetName`, `getNamedSelSetItemCount`, `getNamedSelSetItem` | Objects sets | yes (1-based) |
| node `.isHidden .renderable .primaryVisibility .secondaryVisibility .castShadows .xray .isFrozen` | Objects | yes |
| `xrefs.getXRefFileCount`, `xrefs.getXRefFile i`, `.filename .disabled .hidden` | XRef Scenes | check `.hidden` |
| `getTransformLockFlags` (BitArray `.numberSet`), `setTransformLockFlags node #all/#none` | Camera lock | check `.numberSet` through pymxs |
| MAXScript walker over `.controller.keys` and sub-anims (`SM_keyRange`) | Camera keys | check on a Physical camera with FOV keys |
| `callbacks.notificationParam()` in `#nodePreDelete` | Delete warning | yes (returns the node) |

## M4 notes (render)
Details, API calls to check and Max test steps: docs/m4_render.md.
Shared-file changes made by M4 (all additive):
- `core/tokens.py`: `{version}` auto-increment (next free number on disk, or fixed from the Output builder) and `{element}` in `TOKENS`; custom tokens come from the Output builder through the `extend_context` hook M2 added to `SetupManager.context()`.
- No edits to registry, manager, cards, commands or mcp_server: M4 code lives in `modules/render_*.py`, `output_builder.py`, `post_production.py`, `lightmix.py`, `custom_props.py`, `render/rprops.py`, `ui/kinds_render.py`, `bridge/commands_render.py`, `claude_bridge/tools_render.py`.
- Apply order used: preset 5, renderer 8, output builder 15, render overrides 45, curated settings 50, elements 60, post 65, LightMix 70, custom properties 95.
- Ownership: environment GI/reflection overrides stay in M3 (Render overrides skips `environment_*` / `bg_*`); LightMix applies after the Lights module (M2) and wins for lights in a group.

## M3 notes (lighting & environment)
Max test steps and API calls to check: docs/m3_test_in_max.md. Stand-in tests: `python -m tests.test_m3` (87 checks; UI part needs PySide6).
New files: `env/` (solar.py, renderers.py, mapstore.py, hdri.py), `modules/` environment.py, env_override.py, dome.py, atmosphere.py, viewport_bg.py, `ui/` kinds_env.py (kinds light, hdri, image, checklist), hdri_browser.py, `bridge/commands_env.py`, `claude_bridge/tools_env.py`, `tests/` standin_pymxs.py, test_m3.py.
Shared-file changes made by M3 (additive):
- `modules/sun.py`: new props shadows, position (angles / date_time), date, time, latitude, longitude, utc_offset, north; card actions "now" and "golden hour". Date/time is written on the sun node as user property `sm_sun_position`, so capture reads it back.
- `core/registry.py`: auto-imports every file in `modules/` (files starting with `_` skipped).
- `bridge/commands.py` merges `COMMANDS` from any `bridge/commands_*.py`; `claude_bridge/mcp_server.py` loads any `claude_bridge/tools_*.py` (`register(mcp, call)`).
- A second custom attribute on rootNode (`SceneManagerMaps`) keeps sky / HDRI / custom maps alive between setups; safe to remove (maps are rebuilt).
- Apply order: sun 40, dome 45, environment 50, GI/reflection overrides 55, atmosphere 58, viewport background 60.
Not in M3 yet: Arnold GI/reflection overrides (Arnold has none), creating an Arnold sun, CoronaBitmap (Corona uses Bitmaptexture for now).
