# Scene Manager: research and plan for our version

Date: 2026-11-17. Sources: public pages only (pulze.io product page, docs.pulze.io Scene Manager section, changelog, Scene Manager 3 beta blog). No decompiling, no code, no licensing.

## 1. What Pulze Scene Manager is

A 3ds Max panel that stores many **setups** (scene states) in one .max file. Each setup holds values for a set of **modules**. Clicking a setup applies all its modules to the scene. Setups can be batch rendered, sent to Pulze RenderFlow (their farm manager), or baked to native Max scene states / render presets / batch render entries.

| Item | 2.x (current) | 3.0 (beta, 2026-11-16) |
|---|---|---|
| Max versions | 2019 to 2027 | 2021 to 2027, Windows |
| Renderers | V-Ray 7 (incl. GPU), Corona, F-Storm first class; Arnold, Redshift partial | V-Ray, V-Ray GPU, Corona, FStorm |
| Storage | Inside the .max file; scene still opens without plugin | Same, 2.x setups converted on open |
| Price | Free (5 setups), Pro $9.90/seat/month | n/a |
| Requires | Constant internet connection (licensing) | n/a |

## 2. Modules a setup stores (2.x)

| Group | Module | What it stores / does |
|---|---|---|
| Setup | Name, Thumbnail, Notes, Todo | Label, viewport or VFB thumbnail, free notes, checklist |
| Camera & framing | Camera | Active camera; tracks camera rename/delete; lock |
| | Resolution | Width, height, aspect slider, x2 / /2 buttons |
| | Time Output | Single, Range, or List of frames; range from camera keys; drives timeline and render time output |
| Lighting & env | Sun | Pick a sun; turns other main lights off; creates matching V-Ray/Corona sky |
| | Dome | Pick dome light; open or fetch its HDRI |
| | HDRI Browser | Favourite folders with thumbnails |
| | Environment | None, Sky, HDRI, Custom |
| | Atmosphere | Enable/disable Max atmospherics (e.g. VRayAerialPerspective, VRayEnvironmentFog) |
| | Background | Viewport background: gradient, solid, environment, custom image |
| Scene control | Layers | Visibility, freeze, renderable per layer |
| | Objects | Visibility per object (docs say keep to ~10 to 20 objects) |
| | Xref Scene | Enable/disable Xref scenes per setup |
| | Variants | List of layers, one per product variant, with own output name |
| Rendering | Render Output | Project folder, path rules, extension, format options; creates folders; V-Ray separate channels and raw output |
| | Render Settings | Curated key properties for V-Ray, Corona, F-Storm |
| | Render Settings Override | "Fetch" a diff of changed render properties and lock it per setup |
| | Render Preset | Load a .rps first, then other modules override it |
| | Render Elements | On/off per pass, per setup |
| | Post-Production | V-Ray VFB layers / Corona tone mapping (fetch and clear) |
| Scripting | Script File / Editor | MAXScript at Pre-Setup, Post-Setup, Pre-Render, Post-Render |

**Workflow features:** Batch Render all setups (cancel stops whole batch, warns on duplicate output paths), Bake Setups to native Scene States + render presets + Max Batch Render, export per setup as .max / .vrscene / Corona scene, Templates (import/export setups), Live Mode and camera sync (activate the setup that matches the active camera), Preview mode (edit without touching the scene), light/dark theme, MAXScript API with at least `bakeSetups`.

**3.0 beta adds:** nested folders with inherited values, combinatorial variations (objects, materials, cameras, layers, HDRIs), sun by date/time/location, GI/reflection environment overrides, output builder with tokens (setup, camera, date, version, custom), comments pinned to viewport/VFB, background batch rendering, render via Chaos Vantage, a REST API, Python SDK and MCP server.

## 3. How it hooks into 3ds Max (observed, plus our equivalents)

| Need | What we will use | Notes / to verify in Max |
|---|---|---|
| Store data in .max | Custom attribute block on `rootNode` (or `persistents`), holding a JSON string | CA on rootNode survives save/load. Merge does not bring rootNode data: handle with an Export/Import JSON instead |
| Track objects across rename | Store node handle + name + `getHandleByAnim` / `NodeEventCallback` | Handles change on merge; keep name as fallback |
| Apply camera | `viewport.setCamera`, `renderers.current`, `rendSaveFile`, `renderWidth/Height` | Standard pymxs.runtime calls |
| Time | `rendTimeType`, `rendStart`, `rendEnd`, `rendPickupFrames`, `animationRange` | |
| Layers | `LayerManager.getLayer(i)`, `.on`, `.isFrozen`, `.renderable` | |
| Lights | Node `.on`, `.multiplier`, `.color`, renderer-specific props via `getPropNames` | |
| Environment | `environmentMap`, `useEnvironmentMap`, `setActiveViewportBackground` | |
| Render elements | `maxOps.GetCurRenderElementMgr()`, `.enabled` on each element | |
| Atmospherics | `numAtmospherics`, `getAtmospheric i`, `isActive` | |
| Render settings | `getPropNames renderers.current` + snapshot/diff | Generic for any renderer |
| Batch render | Loop setups, apply, `render()` or `max quick render`; progress via Qt | Run with `renderSceneDialog.close()` first |
| Native bake | `sceneStateMgr`, `renderPresets.SaveAll`, `batchRenderMgr.CreateView` | Verify sceneStateMgr parts list per Max version |
| Callbacks | `callbacks.addScript #filePostOpen`, `#filePreSave`, `#nodePostDelete`, `#postRenderFrame` | |
| UI | PySide6 (Max 2025+) / PySide2 (2024) dockable `QDockWidget` parented to `qtmax.GetQMaxMainWindow()` | |

## 4. Where we can be better

| Area | Pulze | Ours |
|---|---|---|
| Licensing | Internet always on | Offline, in-house |
| Farm | RenderFlow native; Deadline only via bake | Native Deadline submitter (one job per setup, or one job with setup as a task param) |
| Data model | Fixed set of modules | Plugin modules (one Python class each), easy to add studio-specific ones |
| Inheritance | Folders only in 3.0 beta | Base setup + child overrides from day one ("only store what differs") |
| Diff | Render override shows a count | Visual diff: current scene vs setup, setup vs setup, with "capture changes" per module |
| Objects | Weak above ~20 objects | Use selection sets / name patterns / layers, scales to thousands |
| Merge / Xref | Not documented | JSON export/import + "re-link missing nodes by name" tool |
| Naming | Tokens only in 3.0 | Token builder from day one: `{scene}{setup}{camera}{date}{version}{frame}` |
| Validation | Duplicate path warning | Pre-flight check: missing camera, missing maps, duplicate outputs, missing render elements |
| Studio tools | Templates | Shared studio presets folder on the network |

## 5. Proposed architecture

```
scene_manager/
  core/
    storage.py      # read/write JSON in a rootNode custom attribute, versioned schema
    setup.py        # Setup dataclass: id, name, parent_id, modules{}, thumbnail
    module_base.py  # class Module: capture(), apply(data), diff(data), validate(), ui()
    registry.py     # module registration
    applier.py      # ordered apply: pre-setup script -> modules -> post-setup script
    tokens.py       # output path token resolver
  modules/          # one file per module: camera.py, resolution.py, time.py, lights.py ...
  render/
    batch.py        # local queue with progress and cancel
    deadline.py     # Deadline submit (later)
    bake.py         # to Scene States / presets / batch render
  ui/
    main_panel.py   # dock widget: setup tree left, module cards right
  maxscript/
    helpers.ms      # only where pymxs is weak (CA definition, callbacks)
  install/
    startup script + macroscript toolbar button
```

Each module is a class with `capture()` (read scene into a dict), `apply(dict)`, `diff(dict)` and a small Qt widget. The core never knows module details, so we add modules one at a time in the priority order from the project brief: Camera, Resolution/Output, Time, Lights, Sun, Environment/HDRI, Layers, Objects, Render settings, Render elements, Atmospherics, Material overrides, Scripts, Batch render, Import/export and bake.

**Step 1 (MVP):** core storage + Camera + Resolution/Output + Time + dock panel with setup list + batch render. Testable in Max in one sitting.

## 6. Open points to verify in Max
- Custom attribute on `rootNode` behaviour on File > Merge and Xref Scene (expected: not carried, hence JSON export).
- `sceneStateMgr` API coverage in 2024+ for baking.
- Corona and V-Ray property names for sun/sky/dome per version.

## 7. Decisions (Momen, 2026-11-17)
| Topic | Decision |
|---|---|
| 3ds Max | 2025 and up (Python 3.11, PySide6) |
| Renderers | V-Ray, Corona, Arnold |
| Rendering | Local only for now |
| Must-have | Claude Code integration: Claude drives 3ds Max (sun, shadows, settings) through an MCP server + bridge in Max |
| UI | Floating window, setup thumbnails |
| Scenes | Xref and merge are common: setups must be exportable/importable |
| Team | Share setups as presets with the team |
