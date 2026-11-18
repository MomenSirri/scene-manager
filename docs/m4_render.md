# M4 Render modules

Status: built and tested with a pymxs stand-in (not yet in 3ds Max). Targets 3ds Max 2025+, V-Ray / Corona / Arnold.

## Modules

| Card | Key | Order | Stores | Auto in new setups |
|---|---|---|---|---|
| Render preset | `render_preset` | 5 | .rps file, "Keep Common tab" | no (+ Module) |
| Renderer | `renderer` | 8 | vray / vray_gpu / corona / arnold / scanline / art | yes |
| Output builder | `output_builder` | 15 | `{version}` (0 = next free on disk), digits, custom tokens | no |
| Render overrides | `render_override` | 45 | every renderer property that differs from the defaults | no |
| V-Ray / Corona / Arnold settings | `render_vray`, `render_corona`, `render_arnold` | 50 | curated quality settings | only the current renderer's card |
| Render elements | `render_elements` | 60 | elements on/off, master switch, element file names (`{element}`), V-Ray separate channels + raw file | yes |
| Post-production | `post` | 65 | V-Ray VFB layer tree (JSON, includes LightMix layer), Corona tone mapping values | no |
| LightMix | `lightmix` | 70 | per light group: on, intensity multiplier (baked into the lights) | no |
| Custom properties | `custom_props` | 95 | any property of any node / renderer / environment / MAXScript expression | no |

Order matters: the preset loads first, everything else overrides it; curated cards win over Render overrides; Custom properties apply last and win over everything.

Behaviour notes
- **Renderer switch**: switching keeps the previous renderer object for this Max session, so going back restores its settings. A renderer not used yet starts from defaults plus what the setup's cards set. Store important settings in the curated card or Render overrides.
- **Curated cards for another renderer** stay stored and silently do nothing until that renderer is current.
- **Render overrides**: Fetch = compare the renderer with a fresh instance of the same class. Skipped on purpose: curated props, `output_*` (Render elements), colour mapping / bloom (Post-production), `environment_*` / `bg_*` (Environment, M3). Overrides fetched from V-Ray do nothing on Corona.
- **Element files**: `D:/renders/{scene}/{setup}/{setup}_{element}.exr`. Folders are created for enabled elements.
- **{version}**: in any token path (Output, element files, V-Ray channels/raw, preset). 0 = scans the folder for the highest existing number (also folders like `v003`) and uses the next one, so each new render after an activation gets a new version. Frame numbers Max appends are ignored.
- **Custom tokens**: Output builder card, Custom tokens: `client = ACME`, `shot = {camera}_{width}`.
- **LightMix**: groups are the light-select render elements; lights in none get their own group. "Base intensity" is captured with the mix; the multiplier scales it. It wins over the Lights module (M2) for those lights. V-Ray's interactive VFB LightMix lives in Post-production instead.

## Claude bridge (tools_render.py / commands_render.py)
`render_info`, `render_props(filter, changed_only)`, `set_render_props(values)`, `fetch_render_overrides(name)`, `fetch_post_production(name)`, `save_render_preset(path)`, `add_custom_property(name, prop, target, node, path, value)`. Module values also work through `set_module_values` (keys above).

## API calls used (CHECK = not verified in Max, please confirm)

| Area | Call | Sure? |
|---|---|---|
| Renderer | `renderers.current`, `classOf`, `RendererClass.classes`, `renderers.current = <class>()` | creating an instance by calling the class: CHECK |
| Defaults | `classOf(renderers.current)()` (unassigned instance), `getPropNames`, `getProperty`, `setProperty`, `isProperty` | instance creation: CHECK |
| Preset | `renderPresets.LoadAll 0 f`, `renderPresets.Load 0 f #{...}`, `renderPresets.LoadCategories f`, `renderPresets.SaveAll 0 f` | Load with bitArray + LoadCategories: CHECK |
| Elements | `maxOps.GetCurRenderElementMgr()`, `NumRenderElements`, `GetRenderElement`, `.elementName`, `.enabled`, `SetRenderElementFilename`, `Get/SetElementsActive` | yes |
| V-Ray output | `output_splitgbuffer`, `output_splitfilename`, `output_saveRawFile`, `output_rawFileName` | CHECK names |
| V-Ray curated | `imageSampler_type_new`, `twoLevel_threshold`, `twoLevel_baseSubdivs`, `twoLevel_fineSubdivs`, `progressive_noise_threshold`, `progressive_max_render_time`, `gi_on`, `gi_primary_type`, `gi_secondary_type`, `lightcache_subdivs`, `options_displacement`, `options_maxDepth(_on)` | CHECK the two progressive names and the enum values |
| Corona curated | `adaptivity_targetError`, `progressive_passLimit`, `progressive_timeLimit`, `denoise_filterType`, `denoise_blendAmount`, `gi_primarySolver`, `gi_secondarySolver`, `shading_maxRayDepth`, `shading_maxSampleIntensity`, `lights_samplesMult`, `displace_enable` | CHECK all |
| Arnold curated | `AA_samples`, `enable_adaptive_sampling`, `AA_samples_max`, `AA_adaptive_threshold`, `GI_*_samples`, `GI_*_depth` | CHECK all |
| VFB layers | `(vfbControl #getLayerMgr)[1]`, `.saveLayersToJSON()`, `.loadLayersFromJSON s` | from V-Ray docs; CHECK |
| Corona tone mapping | renderer props starting `colorMap_` / `bloomGlare_` | Corona 8+ operator stack is not covered: CHECK what `render_props("colorMap")` shows |
| Light select | element props `lights` / `includedNodes` / `nodes` | CHECK |

Each curated value tries a list of property names, so a wrong name shows as "not found on vray: ..." in the activation errors instead of breaking the setup. Fix the name in `modules/render_settings.py`.

## Test in 3ds Max
1. Run `dev_reload.py` (or restart Max). Open the panel: new cards appear under the Render rail icon.
2. **Curated**: V-Ray scene, select a setup, open the V-Ray settings card. Values should match Render Setup. Tick Noise threshold, change it, check Render Setup (F10). Errors in the status bar mean a property name is wrong: run `showProperties renderers.current` and tell me the right name.
3. **Renderer switch**: on setup B set Renderer = corona. Activate B, then A. A must be V-Ray again with your settings.
4. **Overrides**: change a few odd settings in Render Setup (e.g. bucket size), + Module > Render overrides on a setup, Fetch. Reset the renderer (assign it again), activate the setup: the settings come back.
5. **Preset**: save a .rps from Render Setup, + Module > Render preset, pick it. Activate: settings load, resolution stays (Keep Common tab on).
6. **Elements**: add 2-3 elements, toggle one off on a setup, set Element files to `C:/temp/{setup}/{setup}_{element}.exr`, activate, check the Render Elements tab filenames. V-Ray: tick separate channels with a path.
7. **Post**: render once, add a VFB layer (e.g. Exposure), + Module > Post-production. Change the VFB, activate the setup: the stored layers return. Corona: same with tone mapping.
8. **LightMix**: create a light-select element with two lights, + Module > LightMix, set its multiplier to 0.5, activate: those lights' intensity halves; set back to 1: original values.
9. **Output builder**: output `C:/temp/{client}/{setup}_v{version}.exr`, custom token `client = ACME`, version 0. Render; activate again: the path shows v002.
10. **Custom properties**: select a light, + Property, property `multiplier`, change the value, activate.
11. **Claude**: ask "what render settings does this scene use?" (uses `render_info`), "store the current render overrides on Dusk".
