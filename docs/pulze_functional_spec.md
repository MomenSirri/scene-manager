# Pulze Scene Manager: functional spec and gap list

Date: 2026-11-18. Written from public material only: docs.pulze.io (2.x and 3 beta sections, changelogs, developer pages), pulze.io product, pricing and blog pages, and the screenshots published on those pages. Nothing was installed, decompiled or inspected. Supersedes the feature tables in `research.md`; architecture notes there still stand.

How sure each line is:

| Mark | Meaning |
|---|---|
| D | Stated in the public docs, changelog or blog text |
| S | Read off a published screenshot (layout and labels are certain, behaviour behind a button is not) |
| I | Inferred by me from D and S; check before relying on it |
| ? | Not public. Needs a look at the running plugin (section 9) |

## 1. Two generations, two layouts

Pulze ships 2.6.3 (stable) and 3.0.1 (beta, 2026-11-16). They look very different, and Momen's requests match a mix of both.

| Topic | 2.6.3 | 3.0 beta |
|---|---|---|
| Window | Own window titled "Scene Manager" with min/max/close (S). Docking into Max: ? | Panel inside 3ds Max (D). Docking: ? |
| Left rail | One icon per module, grouped, with a coloured bar per group (S). Click shows or hides that module's card (I) | Three view icons only: Setups, Variations, Comments. Bottom: user avatar, feedback, settings (S) |
| Setup list | A card of its own, a table with columns (S, D) | A slim tree column with folders, search and tag chips (S, D) |
| Adding a module | Rail icon (I); the window "opens with all modules" (D) | Boxed + button at the right end of the setup header (S, I). Modules are "cards you add, arrange and switch on per setup" (D) |
| Card header | Group colour, icon, title, then copy, menu, on/off switch, close (S) | Drag grip, title, gear, on/off tick. No colour band (S) |
| Card size | Resize grip in each card's bottom-right corner (S) | No grip visible; cards flow in columns (S) |
| Theme | Light or Dark (D) | Dark, cyan accent (S) |
| Grouping of setups | Flat list, colour stripe per row (S) | Nested folders with inherited values, tags, colours (D) |
| Extras | Live Mode, Camera Sync, Preview mode, Templates, Bake (D) | Variations, Comments, quality levels, background render, REST/Python/MCP (D) |

Reading for our build: the module rail with icons that Momen asked for is the 2.x pattern. The folder tree, tags and tick-per-property rows we already follow are the 3.0 pattern. Combining them is a sound target: 3.0 tree and cards, 2.x module rail.

## 2. Layout in detail

### 2.1 Version 3 beta, Setups view (S unless marked)

| Zone | Contents |
|---|---|
| Rail (about 44 px) | Top: Setups (stack icon), Variations (shuffle icon), Comments (bubble). Bottom: avatar with initials, feedback, settings. Active view has a filled tile |
| List header | "Setups" + total count. Icon buttons: delete, lightning, new folder, capture frame, wand. Accent + button creates a setup. Meaning of lightning and wand: ? (likely activate and setup-from-scene, I) |
| Filter | Search field. Two view toggles (plain list, detailed list). Tag chips with counts: All 13, client 3, day 4, dusk 1, ... scrolling sideways |
| Tree | Folder row: chevron, folder icon, name, count of setups. Setup row: tick box (selection for batch), name. Tree lines connect children. Folders nest (Drafts > Old). Active setup: highlighted row with accent bar on its left edge |
| Setup header | Thumbnail tile, setup name, one line of notes under it. Activation time ("78 ms"). Quality switch: None, Draft, Full. Then compare/transfer icon, save icon, add-module button |
| Card area | Cards in columns (2 visible at about 500 px; more when wide, I). Each card is as tall as its content, so columns are uneven (masonry) |

Keyboard shortcuts exist in the setup list; several setups can be duplicated at once; several table rows can be edited at once (D, 3.0.1). The exact keys: ?

### 2.2 Version 3 card anatomy (S)

| Part | Behaviour |
|---|---|
| Grip (6 dots, left of title) | Drag to rearrange cards (I, matches "arrange" in D) |
| Title | Module name |
| Extra icon | Module specific, e.g. Resolution has a presets icon; Fabric axis has a refresh icon |
| Gear | Module options, probably choosing which properties show (I; the API has add_property "properties to a module", D) |
| Tick (accent) | Module on or off for this setup. Off means that part of the scene is left alone (D) |
| Row dot | Filled accent dot: value is set here. Hollow dot with dimmed label: not set / not available (seen on "Map" and "Scale"). Whether hollow also means "inherited from folder": ? |
| Row | Label left, control right, fixed control column width |
| Collapse | No collapse control visible in any screenshot: ? |

### 2.3 Version 2 window (S unless marked)

| Zone | Contents |
|---|---|
| Top bar | Left: Preview toggle, Camera Sync / Live, Render (teapot), Bake, cloud / RenderFlow submit, export (order I; names D). Right: RenderFlow, Settings gear, account menu |
| Rail | About 20 module icons in groups with a colour bar: purple (name, camera, resolution, time), yellow (sun, lights, dome, environment), cyan (background, atmosphere), green (layers, objects, xref, variants), teal (output), orange (render settings, preset, elements), violet (post, scripts), then misc |
| Setup List card | Header buttons: colour, delete, duplicate, transfer, thumbnail, columns, wand, +. Table: drag handle, render toggle (teapot), #, Scene Name, Camera, Resolution, Sun, Dome, Environment. Row colour stripe. Active row bold on grey. Columns are chosen in Settings (D) |
| Cards | Free grid of cards, each with its own corner resize grip. Header: copy (copy this module's values to other setups, I), menu, on/off switch, close (hide card) |

## 3. Core behaviour

| Topic | Behaviour | Mark |
|---|---|---|
| Setup | A saved state of the scene. Values are grouped by module | D |
| Activation | Click a setup. Scene Manager writes the setup's values into the scene. Result is the same whichever setup was active before (v3) | D |
| Activation report | v3 returns what was applied and what was skipped, with a reason per skipped item, and shows the time taken | D, S |
| Module off | That part of the scene is not touched | D |
| Apply order | Pre-Setup script, .rps preset, all other modules, Post-Setup script. At render: Pre-Render, render, Post-Render | D |
| Storage | Inside the .max file. Every edit is saved to the scene at once. Scene opens without the plugin | D |
| Dirty flag | Activating or creating a setup must not mark the file as changed; no "unsaved changes" prompt when only Scene Manager data changed | D (2.5.12, 2.3.6 fixes) |
| Rename / delete tracking | Renaming or deleting a camera or any used object updates every setup that uses it. If it happened while the plugin was closed, it is picked up at next start | D |
| Nothing is created | v3 never creates lights, materials or maps; it only switches what exists. (2.x Sun card could create a sky map) | D |
| Folders (v3) | Nest. A value set on a folder applies to every setup inside. A setup shows "each value and where it comes from" | D |
| Setup from scene (v3) | One click turns the scene as it is into a setup | D |
| Compare (v3) | Differences between two setups, module by module | D |
| Missing things (v3) | Lists references the scene no longer has and relinks them | D |
| Tags, colour, notes, to-dos, thumbnail | Per setup. Thumbnail from viewport or VFB | D |
| Delete | Confirmation dialog. Deleting a setup does not change the scene | D |
| Duplicate | Copy lands directly below the original | D |
| Preview mode (2.x) | Toggle in the top bar (was Alt+click on a setup). While on, edits in the panel do not touch the scene | D |
| Camera Sync (2.x) | Watches the viewport; when the active camera changes, activates the setup that uses it | D |
| Live Mode (2.x) | As Camera Sync, and also adds a setup for each new camera | D |
| Templates (2.x) | Import / export setups to share with a team | D |
| Read-only / busy | v3 refuses edits on a read-only scene and while a batch runs | D |

## 4. Modules

Group colours are the 2.x ones. "v3" marks things seen only in the beta.

### 4.1 Camera and framing

| Module | Controls and behaviour | Mark |
|---|---|---|
| Scene Name (2.x) | Text label for the setup; feeds the SceneName output rule. In v3 the setup name does this | D, S |
| Camera | Dropdown of all scene cameras. Select-in-scene button. Lock tick (locks the camera). Sets the viewport's active camera | D, S |
| Resolution | Width, Height, Image aspect with lock, aspect slider (2.x), x2 and /2 buttons (2.x), presets dropdown, Scale dropdown (v3). Used by bake and farm submit | D, S |
| Time Output / Frames | Type: Single, Range, List. Range has start, end, Every Nth. Button pulls first and last key from an animated camera and sets the timeline too. Stores slider time and timeline range; drives Render Setup > Time Output | D, S |
| Region (v3) | V-Ray and Corona frame buffer region, and the 3ds Max crop, per setup | D |

### 4.2 Lighting and environment

| Module | Controls and behaviour | Mark |
|---|---|---|
| Sun | Dropdown of suns plus "Disable Sun Lights". Choosing one turns it on and turns the other main lights off. Cloud button (2.x): create matching V-Ray/Corona sky, link it, put it in the environment slot. v3: sun dial (dome with sun path, azimuth and altitude read-outs, compass), Mode "Time & place" or angles, Location (city), Date, Time of day slider. 2.5: daylight system gets date and time controls | D, S |
| Lights | Table: Name, Enabled (bulb), Intensity. Add from selection, clear all, select and remove per row. Instanced lights are one row (v3). Colour and other properties via Custom Properties | D, S |
| Dome | Dropdown of dome lights. Buttons: select, show its HDRI in the Material Editor, fetch the HDRI the dome already has. One dome per setup or one shared | D |
| HDRI Browser | Favourite folders, thumbnail grid, click to assign | D |
| Environment | Mode: None (default), Sky (needs a valid sun), HDRI, Custom. For a bitmap: Filename with browse and reset, Horizontal rotation slider with reset. Corona Sky, V-Ray and Corona Clouds properties. v3: Use map, Map slot, GI environment, Reflection environment (renderer overrides; FStorm too) | D, S |
| Atmosphere | Pick atmospherics from a dropdown, then enable or disable each per setup (VRayAerialPerspective, VRayEnvironmentFog) | D |
| Background | Viewport background: Gradient, Solid, Env, Custom image (photo matching) | D, S |

### 4.3 Scene control

| Module | Controls and behaviour | Mark |
|---|---|---|
| Layers | Search or dropdown to add; button adds layers selected in Max. Table: Name, Visible, Freeze, Render, V. to Cam (visible to camera). Remove per row | D, S |
| Objects | Add from selection, clear (with confirmation). Table: Name, Visible, Transform, Material, Object ID (v3). Transform and Material store the object's position and material for that setup. Closed groups: only the group head is listed, children follow. Docs warn to stay under 10 to 20 objects | D, S |
| Xref Scene | List of Xref scenes; enabled and visible per setup | D |
| Variants (2.x) | List of layers, one per product version; each can get its own output name and folder. Replaced by Variations in v3 | D |
| Custom Properties / Custom | Any property of any camera, light or object, per setup | D |
| Materials, Color corrections (v3) | Listed by name only; controls: ? | D |

### 4.4 Rendering

| Module | Controls and behaviour | Mark |
|---|---|---|
| Render Output - Common | Root folder, then rule rows. Each row: drag handle, type (Date, Camera, SceneName, Index, Extension, ...), format or value (MM-DD-YYYY, 3 Digits, JPEG), a folder toggle (row ends in "/" and makes a subfolder, or stays in the file name), + and - to add and remove rows. Live preview of the full path. Warning icon on a duplicate path. "Create output directory tree" button, works on several selected setups. Missing folders are made at render time. Global format options for jpg, png, tif, tga, exr, hdr | D, S |
| Render Output - Channels, - Raw | V-Ray only: Separate Render Channels path and Raw (.vrimg) path, same rule system | D |
| Output (v3) | "Save file" tick. Same rows with a separator per row ("/" or "_"). Tokens: `{{setup}}`, `{{camera}}`, `{{date}}`, `{{version:3}}` (number is padding), user, own values. Format dropdown | D, S |
| Render Settings | Curated key properties per renderer. Corona card: Pass limit, Noise level limit, Time limit (minutes), Render hidden lights; each has slider, number and reset. Full V-Ray and FStorm lists: ? | D, S |
| Render Settings - Override | Enable, press Fetch to record the default. Change anything in Render Setup, press Fetch again to lock the differences into the setup. Shows how many and which properties differ | D |
| Render Preset | One .rps per setup, loaded first, then overwritten by the other modules | D |
| Render Elements | Update and Clear buttons. Table: Name, Active, Extension (per-element file type, "default"). On or off per setup | D, S |
| Post-Production / VFB | LightMix section and Tone Mapping section, each with fetch and clear. LightMix rows: tick, multiplier, colour. Tone mapping: operator list with tick and value. V-Ray: VFB layers, needs "Save VFB color correction to RGB channel" on. Corona 8+ tone mapping, bloom and glare, sharpening | D, S |
| Quality (v3) | Header switch None / Draft / Full. A render can be started at a quality level. "Save output" toggle next to it. Render button turns orange when a quality level is on or nothing will be saved. What Draft and Full change: ? | D, S |

### 4.5 Scripting and misc

| Module | Controls and behaviour | Mark |
|---|---|---|
| Script File | Pre-Render and Post-Render script file paths per setup | D |
| Script Editor | Four tabs in run order: Pre-Setup, Post-Setup, Pre-Render, Post-Render. Syntax highlighting, autocomplete. Test button evaluates and shows errors | D |
| Thumbnail | Capture from viewport or from VFB | D |
| Notes | Free text | D, S |
| Todo | Checklist | D |
| Removed in 2.6.3 | Assets, Plugins, Render Manager. Skip | D |

## 5. Rendering workflows

| Feature | Behaviour | Mark |
|---|---|---|
| Batch render | One button renders the ticked setups in order, each saved where its Output says. No manual steps between setups | D |
| Before start | Stops with an error if two setups resolve to the same output path | D |
| Cancel | Cancels the whole batch, not just the current frame | D |
| Frames | Single, range, Nth and list all honoured per setup | D |
| Progress | v3: batch state running / done / stopped; per setup a status and output file. Shows the 3ds Max render log | D |
| One at a time | Starting a second batch is refused | D |
| Background render (v3) | Renders on the same computer in the background while you keep working | D |
| Chaos Vantage (v3) | Batch through V-Ray GPU's live link | D |
| Save as files | Each setup, or a batch, saved as its own .max, .vrscene or Corona scene | D |
| Bake Setups | Converts setups to native Scene States plus render presets and adds them to Max's Batch Render list. Bakes camera, resolution, output, lighting, render settings. For farms or people without the plugin | D |
| RenderFlow | Submit setups to Pulze's farm manager. Out of scope for us (local only) | D |
| Network render | The panel must not pop up during network rendering | D |

## 6. Variations (v3)

| Part | Behaviour | Mark |
|---|---|---|
| Sets list | "Sets" with count; delete, duplicate, +. Row: tick, thumbnail, name, number of variations | S |
| Axes | One card per axis (Furniture, Fabric, Setup). Axis types: objects, materials, textures, cameras, layers, HDRIs, existing setups. Card has grip, gear, on/off tick; rows are options with icon or colour swatch; "+ Add" and option count in the footer | D, S |
| Count | Product of all axes: 12 x 12 x 11 = 1,584 | D |
| Stepper | Bottom bar: previous / next, "1 of 1,584", shuffle, name of the current combination. Stepping applies it to the scene | D, S |
| Output | Output card where each axis is a token row, so each file is named from its options | D, S |
| Render | "Render this" for the current one; render all; list of every variation with its file, also as CSV | D, S |

## 7. Comments (v3) and automation

| Feature | Behaviour | Mark |
|---|---|---|
| Comments view | Tree of setups with comment counts plus "General". Canvas shows a viewport or frame buffer shot. Tools: select, pan, comment pin, pen, text, rectangle, colour. Pins carry the author's initials | S |
| Thread | Status Open / Waiting for Agent / Resolved. Replies, resolve button. Can link objects, materials or lights and be assigned to a person or an AI agent, which replies with what it changed | D, S |
| REST API | Local only, port 45710. Setups list, activate, state, values, render start / progress / stop, run script | D |
| MCP server | 36 tools: overview, get/compare setups, find properties, look (viewport picture), missing things, make/update/delete, add module / property / rows, thumbnail, notes, todos, render, variation sets, comments, run script | D |
| MAXScript API (2.x) | At least `bakeSetups` | D |

## 8. Preferences

| Setting | Options | Mark |
|---|---|---|
| Notification | Message box on file load when the scene has Scene Manager data. Off by default | D |
| Theme | Light, Dark | D |
| Viewport switch | Active Viewport (default); Only Active Perspective, Camera, Orthographic; View to Render (uses the locked render view, then returns) | D |
| Redraw viewport after switching setup | Tick | D |
| Interactive (Corona) | Stop and restart interactive render on each switch | D |
| Columns | Which columns the setup list shows | D |
| Save as Default | Stores the settings as defaults | D |
| Assistants (v3) | Connect buttons for AI clients | D |

## 9. What the public material does not show

| Open question | Why it matters |
|---|---|
| Docking and floating behaviour, minimum sizes, how cards reflow on resize | Momen's resize and floating complaints |
| Card collapse, card drag feel, right-click menus | Card behaviour |
| What the lightning, wand, compare and save icons do; the keyboard shortcuts | Setup list |
| How an inherited value looks versus an overridden one | Our override ticks |
| Property lists inside Render Settings (V-Ray, FStorm), Lights, Color corrections, Materials | Module content |
| Full token list, what Draft and Full change | Output and quality |

Most of these are now answered in section 12. They could only be answered by watching the plugin run. That is allowed under the project rules if Momen installs the 3 beta himself (Pulze account, 30-day trial; note the installer removes 2.x). I would then only look at its panel in 3ds Max and click through it: no reading of its files, scripts or licence.

## 10. Our repo against this spec

State of our code (`/mnt/project-files/scene-manager`, same as `F:\scene-manager`): M1 to M4 built and passing stand-in tests; none of it confirmed in 3ds Max yet.

| Area | Pulze | Ours | Gap |
|---|---|---|---|
| Folder tree, inheritance, tags, colours, search | v3 | Built (`ui/main_window.py` SetupTree, chips) | Multi-select actions, shortcuts, detailed-list view |
| Module rail | 2.x: icon per module | Rail holds pages and categories; modules come from a palette popup | Icon per module on the rail (Momen's ask) |
| Cards | Grip drag, gear, on/off | Built (`ui/cards.py`): collapse, drag, override ticks, fetch, clear | Drag and resize are unreliable; collapse icon too small (other thread) |
| Camera, Resolution, Frames | Yes | Built | Resolution presets, x2 and /2, Scale; region per setup |
| Sun, Dome, Environment, HDRI browser, Atmosphere, Background | Yes | Built (M3) incl. date/time/location and GI/reflection overrides | Visual sun dial; city lookup |
| Lights, Layers, Objects, Xref | Yes | Built (M2); Objects scale past 20 via rules | Objects: Transform and Material per setup; Layers: visible to camera; instanced lights as one row |
| Output | Rule rows with folder toggle, live preview | Tokens and Output builder built | Row-based builder UI, per-row separator, create directory tree, duplicate warning shown on the card |
| Render settings, override, preset, elements, post, LightMix, custom properties | Yes | Built (M4) | Per-element file extension |
| Quality None / Draft / Full, Save output | v3 | None | New |
| Activation report and timing | v3 | None | New |
| Batch render | Yes | Built (`render/batch.py`) with duplicate check and cancel | Max render log, per-setup status list |
| Scripts | Yes | None (M5) | New |
| Variations | v3 | None (M5) | New |
| Materials, Color corrections | v3 | None (M5) | New |
| Preview mode, Camera Sync, Live Mode | 2.x | None (M5) | New |
| Templates | 2.x | Team presets export/import built | Done |
| Compare setups, missing things | v3 | Repair missing nodes built; no compare | Compare view |
| Preferences | Section 8 | Theme, density only | Viewport switch mode, redraw, Corona interactive restart, load notification |
| Comments | v3 | None (M6) | New |
| Bake, save per-setup files, background render, Vantage | Yes | None (M7) | New |
| Claude bridge | MCP with 36 tools | Own MCP server and bridge built | Add look, compare, activation report |

## 11. Gaps in priority order

| # | Gap | Why this rank |
|---|---|---|
| 1 | Test M1 to M4 in 3ds Max and fix what breaks | Nothing is proven in Max; every later item sits on it |
| 2 | Panel shell: module icons on the rail, steady resize (no stray windows), movable floating cards, one frame style | Momen's current blockers; in progress in the UI thread |
| 3 | Activation report (applied / skipped with reason, time) | Cheap, and makes item 1 far easier to debug |
| 4 | Output card as rule rows with live preview, folder toggle, create directory tree, duplicate warning | Used on every setup; ours is token text only |
| 5 | Quality levels None / Draft / Full with Save output toggle | Daily use: test renders without overwriting finals |
| 6 | Scripts module (four hooks, Test button) | In the project brief, small, unlocks studio-specific steps |
| 7 | Objects: transform and material per setup; Layers: visible to camera; Materials module | Needed before Variations can swap materials |
| 8 | Variations (sets, axes, stepper, per-option naming, render all) | Biggest v3 feature; depends on 4 and 7 |
| 9 | Preferences: viewport switch mode, redraw, Corona interactive restart | Small, avoids surprises when switching |
| 10 | Preview mode, Camera Sync, Live Mode | Workflow comfort |
| 11 | Batch polish: per-setup status list, Max log, background render | Local render only, so background render matters more than farm |
| 12 | Bake to native Scene States / presets / Batch Render; save per-setup .max or .vrscene | Hand-off to people without the tool |
| 13 | Compare setups; region per setup; per-element extension; resolution presets | Nice to have |
| 14 | Comments with Claude replies | Large; our bridge already covers the Claude part |
| 15 | Chaos Vantage | Last |

## 12. Observed in the running 3 beta (3.0.1.388, Momen's PC, 2026-11-18)

Watched and clicked the panel only. Test scene: V-Ray, two VRayLights, a VRaySun, a camera and two objects. Where this section disagrees with sections 1 to 9, this section wins.

### 12.1 Window and canvas

| Topic | What it does |
|---|---|
| Window | Its own program window ("Scene Manager 3.0.1.388-beta") with a dark title bar and normal minimise / maximise / close. It floats above 3ds Max and stays on top while you work in Max. It does not dock into Max |
| Settings | A second, separate window |
| Card area | A dotted canvas with a fixed grid of columns. Cards have a fixed column width; table cards (Layers, Objects, Lights, Atmosphere, Script) are two columns wide |
| Resizing the window | Cards do not move or reflow. A smaller window just shows scroll bars (vertical and horizontal). Maximised on a 3440 px screen the cards still sit in two columns on the left with empty canvas to the right |
| Drag a card | Grab anywhere on the header (tooltip: "Drag to move · double-click to fold"). A teal dashed box shows where it will land, snapped to a grid column. On drop the card rises to the top of that column; the other cards close the gap |
| Resize a card | Small teal corner mark at the bottom-right on hover. Drag for any width and height. Labels stay left, controls stay right at their fixed width |
| Fold | Double-click the header, or gear > Fold. Only the header row stays; cards below move up |
| New module | Lands in the first free spot, switched on |

### 12.2 Card gear menu

Rename field, nine colour dots (cyan, blue, violet, magenta, pink, orange, yellow, lime, green), Add a property (only on cards that take properties), Fold, Reset size, Copy values (Ctrl+C), Paste values (Ctrl+V), Remove (red).

### 12.3 Header and setup list

| Control | Tooltip / behaviour |
|---|---|
| Lightning | "Apply on select: on". Toggle: clicking a setup activates it |
| Viewfinder | "One setup per camera" |
| Wand | "Setup from scene" |
| Sliders (setup header) | "Quality levels" |
| Disk (setup header) | "Save output" toggle |
| Boxed + (setup header) | "Add a module" |
| Right-click a setup | Activate (Enter), Add to batch, Rename (F2), Color >, Thumbnail >, Duplicate (Ctrl+D), Move to folder >, Delete (Del) |

### 12.4 Add a module menu

A drop-down list in groups. Items already on the board are dimmed. Items the current renderer cannot use are dimmed with a tooltip, e.g. "Needs V-Ray: the scene renders with Arnold".

| Group | Modules |
|---|---|
| View | Camera, Resolution, Frames, Region |
| Light and sky | Sun, Dome, Environment, Lights, Atmosphere |
| Scene | Layers, Objects, Xrefs, Viewport |
| Render | Output, Render elements, Render settings, Color corrections, LightMix |
| Custom | Custom, Script |
| Notes | Notes, To-do, Comments, Tags, Prompt |

A new setup starts with Camera, Frames, Environment, Resolution, Sun, Output, Layers, Objects. With Arnold: Dome, Render settings, Color corrections and LightMix are unavailable.

### 12.5 Property rows and tables

| Thing | Behaviour |
|---|---|
| Row dot | Filled = a value is stored. Hollow = the property is listed but nothing is stored, so the scene is left alone; the control shows a dash |
| Tick boxes | Three states: on, off, dash (not set) |
| Disabled card | Whole card dimmed; empty tables show grey placeholder bars |
| Table cards | "+ Add" at the bottom offers "Selected in 3ds Max". Magnifier in the header opens an inline search. Rows are grouped by object class with a count ("VRayLight 2"), group can fold and sort |
| Add a property | Popover with search. Lists every property with its current value; a tick marks the ones already shown. Tooltip gives the internal property name |

### 12.6 Module contents seen

| Module | Contents |
|---|---|
| Camera | Camera dropdown ("No cameras in the scene" when empty), select button, Locked |
| Frames | Type, Start, End, Every, Timeline |
| Resolution | Width, Height, Image aspect (lock), Scale; presets icon in the header. Presets live in Settings > Library: HD 1920x1080, 4K UHD 3840x2160, Square 2000x2000, Portrait 4:5 1080x1350, A3 landscape 300 dpi 4961x3508 |
| Sun | Sun dropdown ("Choose a sun"), select button, Mode (Free shown; Time & place in the blog), Azimuth, Altitude |
| Environment | Use map, Map slot ("None / No map") |
| Dome | Dome dropdown ("Choose a dome"), select button |
| Lights | Columns On, Intensity, Color by default. Add a property lists the light's whole property set: Azimuth, Altitude, Enabled, Multiplier, Color, Temperature, Double sided, Shadow bias, Affect atmospherics / diffuse / reflections / specular, contributions, Color mode, Cutoff threshold, Decay near/far, Dome options, Invisible to camera, include / exclude lists, Light distribution, No decay, Units, Size0, Size1 and more |
| Render settings | Starts empty with "+ Add a property". The list is the renderer's full settings grouped like Render Setup rollouts: Frame buffer, Global switches, IPR options, Image sampler (antialiasing), Bucket image sampler and so on. No curated short list |
| Color corrections | Refresh button; tree of V-Ray frame buffer layers with a tick each (Stamp, Display Correction) |
| LightMix | Empty state: "Add a LightMix element, render once, then refresh" |
| Render elements | Empty state: "Add them in Render Setup, then refresh" |
| Region | "Viewport" field ("Not set") with a fetch button |
| Viewport | Background, Image (browse), Style, Edged faces, Safe frame, Grid, Lighting, Shadows, Ambient occlusion, Quality |
| Output | Save file, Root folder (browse), path preview with +, Format |
| Custom | Empty with "+ Add a property" |
| Script | Stage dropdown ("Post setup" shown), run / format / open buttons, "Type or browse your Python script" with Type and Browse. Python, not MAXScript |
| Notes, To-do, Tags, Prompt | "Write a note"; "+ Add an item"; "+ Add a tag"; free text prompt (used for the image-model brief) |

### 12.7 Quality levels

A small grid. Columns are levels (Draft, Full, + adds a level). Rows are properties ("+ Add" adds one). Default single row: Resolution > Scale, Draft 25 %, Full 100 %. So a quality level is a named set of overrides laid over the active setup.

### 12.8 Settings window

| Page | Contents |
|---|---|
| Appearance | Theme: Dark, Light, System |
| Notifications | File loaded: show in the status bar if the scene contains setups |
| Switching | Update viewport: Active viewport, 3D views only, View to render. Redraw viewport. Restart Corona IR. Sync V-Ray IPR size |
| Library | HDRI folders (add a folder). Resolution presets |
| Storage | Size of setups and comments, images, unused images saved in the scene |
| Assistants, Updates | AI client connections; updater |

### 12.9 Variations view

Empty state: "No sets yet. A set is one product: its properties make every variation." with a New set button.

### 12.10 Still not seen

Output token list (the + in the path row), Sun in Time & place mode, the Objects and Layers columns with rows, folder inheritance display, batch render progress, comments. These need a real scene with a saved setup or two.

### 12.11 What this changes for our build

| Finding | Consequence |
|---|---|
| Not docked: a floating always-on-top window | We do not need Max docking to match the original. A plain top-level tool window parented to Max is enough and avoids dock resize problems |
| Cards never reflow on window resize | Rebuilding cards on every resize is unnecessary. Keep positions fixed and let the area scroll |
| Grid with drop placeholder and upward packing | Replace free masonry with: fixed column grid, dashed drop target, pack upward in the column |
| Whole header drags; double-click folds; gear holds Fold / Reset size / Copy / Paste / Remove | No tiny collapse arrow needed |
| Modules come from a grouped menu, dimmed with a reason when unavailable | If we keep the left rail for modules (Momen's wish), use the same six groups and the same dimming with a tooltip |
| Render settings and Lights are generic "add any property" lists | Our Custom properties engine can drive both; the curated lists become defaults, not limits |
| Hollow dot = listed but not stored | Same idea as our override ticks; a dot is lighter than a tick box |
| Quality levels = override columns | Small feature on top of our override model |

## Sources

- https://docs.pulze.io/scene-manager (installation, setups, camera-and-framing, lighting, scene-control, rendering, scripting, bake-setups, misc, settings, changelog)
- https://docs.pulze.io/scene-manager-3 (installation, changelog, developers: overview, rest-api, python-sdk, mcp-server, api-reference/introduction)
- https://www.pulze.io/products/scene-manager and https://www.pulze.io/pricing/scene-manager
- https://www.pulze.io/blog/scene-manager-3-beta, /scene-manager-april-2026, /scene-manager-render-automation, /scene-manager-2-5
- Screenshots on those pages: 3 beta setups view, variation set, comments view; 2.x "interface with all modules"
- https://www.cgchannel.com/2024/05/get-pulzes-free-scene-manager-lite-for-3ds-max/ , https://cgpress.org/archives/pulze-scene-manager-2-5-beta-released.html , https://rebusfarm.net/news/pulze-keeping-it-together-using-pulze-scene-manager
