# Scene Manager for 3ds Max

Keep many render setups (camera, resolution/output, time, and more modules over time) inside one .max file. Switch with a double click, batch render locally, share setups with the team as preset files, and let Claude Code drive 3ds Max through a local bridge.

Targets: 3ds Max 2025+ (Python 3.11, PySide6). Renderers: V-Ray, Corona, Arnold.

## Install (once per machine)
1. In 3ds Max: **Scripting > Run Script...** and pick `install_scene_manager.ms` from this folder.
2. The window opens. Add a toolbar button via **Customize > Customize User Interface > Toolbars**, category **SceneManager**.
3. After editing code, run `dev_reload.py` (Scripting > Run Script) instead of restarting Max.

## Use
The panel opens floating. Drag its title bar onto a side of 3ds Max to dock it; narrow docks stack the list above the cards.

| Action | How |
|---|---|
| New setup / folder | **+ Setup** captures the scene (with thumbnail) into the selected folder. **+ Folder** makes a folder |
| Activate | Double-click a setup, or **Activate** |
| Inheritance | Values on a folder pass down to every setup inside. In a card, tick a property to set it on this setup; untick to inherit again. Dots: blue = set here, grey = inherited, orange = differs from the scene now |
| Module on/off | Checkbox in the card header. Off on a setup overrides the folder. **+ Module** adds one |
| Edit live | Changing a value on the active setup applies it to the scene immediately |
| Card menu (⋯) | Fetch from scene, apply only this module, size x2 / half, clear, remove |
| Organise | Drag setups between folders, right-click for colour, rename, duplicate, delete, export |
| Find | Search box and tag chips (tags are set under the setup name) |
| Thumbnails | Click the thumbnail to grab the viewport. ▦ switches the list to a thumbnail grid |
| Batch render | Tick setups or whole folders, open ▶ in the left rail, **Render queue**. Warns on duplicate outputs |
| Scene baseline | Setup menu (right-click or •••) > Scene baseline > Capture, with the scene in its neutral state. Afterwards a setup looks the same whichever setup was active before |
| Lights / Layers | Tick a row to store it on this setup; unticked rows inherit. "not listed: off/hide" for solo setups |
| Objects | Add rules: `set:Furniture`, `layer:Trees`, `pattern:Tree_*`, `node:Car` (+ Selection adds the selected objects). ✓ on, ✕ off, · leave alone |
| Repair | Deleting a camera/light a setup uses shows a warning; Setup menu > Repair missing nodes re-links it |
| Team presets | Right-click > Export / Import presets. Set the team folder under ⚙ |

Output path tokens: `{scene} {folder} {setup} {camera} {renderer} {width} {height} {date} {time} {user} {project}`
Example: `D:/renders/{scene}/{folder}/{setup}_{camera}_{date}.exr`

Setups live in a custom attribute on the scene root, so they save with the .max. **Merge and Xref do not carry them**: export the setups from the source scene and import them in the target (nodes are matched by name).

## Claude Code bridge
The bridge starts with 3ds Max (turn it off in `~/.scene_manager/config.json` → `"bridge_autostart": false`, or with the **Claude bridge** toggle). It listens on 127.0.0.1:8765 only and needs a random token from `~/.scene_manager/bridge.json`.

1. Install Python 3.10+ on Windows (outside Max), then: `pip install -r claude_bridge/requirements.txt`
2. Register the server once, from this folder:
   `claude mcp add --scope project 3dsmax -- python claude_bridge/mcp_server.py`
3. Start 3ds Max, then run `claude` in this folder.
4. Ask things like: "Make a setup called Dusk: sun at azimuth 250, elevation 8, softer shadows, 3000x2000, output to D:/renders/{scene}/{setup}.exr".

M2 tools: `capture_baseline`, `clear_baseline`, `get_baseline`, `restore_baseline`, `list_targets`, `set_lights`, `set_layers`, `set_object_rule`, `set_notes`, `todo`, `find_missing_nodes`, `repair_node`, `camera_key_range`.

Tools: `scene_info`, `inspect_node`, `list_setups`, `get_setup`, `apply_setup`, `capture_setup`, `create_folder`, `move_item`, `set_module_values`, `update_setup_info`, `delete_setup`, `render_setups`, `set_sun_direction`, `run_python`, `run_maxscript`. The ✦ page in the panel lists what Claude did. Everything Claude changes in the scene is one undo step.

## Layout
```
scene_manager/core      storage, setup manager, tokens, node refs, module base + registry
scene_manager/modules   one file per module (camera, output, time_range, ...)
scene_manager/render    local batch render
scene_manager/ui        floating window
scene_manager/bridge    TCP listener inside Max + commands
claude_bridge           MCP server for Claude Code (runs outside Max)
```
Add a module: new file in `scene_manager/modules`, subclass `Module`, list its `props` (the card is built from them), implement `capture()` and `apply()`, decorate with `@register`, import it in `core/registry.py`. See docs/roadmap.md for the order.
