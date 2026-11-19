# M2 (Scene) test in 3ds Max

Setup: 3ds Max 2025+, V-Ray or Corona. After copying the code, run `dev_reload.py` (Scripting > Run Script).
Watch the MAXScript Listener for "Scene Manager: ... failed" lines and send them back.

## 0. Scene
Two cameras (Cam01 animated over frames 10-80, Cam02 static), three lights (Key, Fill, Lamp) plus a sun,
layers Vegetation (some objects named Tree_01...), Cars, Interior, and a selection set "Furniture"
(select chairs, type the name in the main toolbar's Named Selection Sets box).

## 1. Baseline (deterministic activation)
1. Right-click empty space in the setups list > Scene baseline > Capture baseline from the scene.
   Status bar ends with "baseline".
2. New Setup "Day" (all lights on). New Setup "Night".
3. On Night: Lights card, tick Fill, set intensity 8; set "Lights not listed" to off.
4. Activate Night: only Fill is on (sun is the Sun module's job). Activate Day: Key, Fill, Lamp on again, Fill back to its old intensity.
   Expected: Day looks the same whether you came from Night or not.

## 2. Layers
On Night tick Vegetation, untick Visible. Activate Night then Day: Vegetation hides, then shows.

## 3. Objects
On Night: + Add Module > Objects. Add `pattern:Tree_*` (✕ in Visible column), `node:Tree_07` (✓ Visible),
`set:Furniture` (✕ in Render). Activate Night: every tree hidden except Tree_07, chairs not renderable
(Object Properties > Renderable off). Activate Day: all back.

## 4. XRef Scenes (only if the scene has an XRef Scene)
Card lists each XRef scene; untick Visible on Night, activate Night/Day.

## 5. Notes and To do
+ Add Module > Notes / To do. Type a note, click elsewhere (it saves on focus out). Add to-dos with Enter.
Right-click > Capture scene into this setup must NOT wipe them.

## 6. Camera lock and repair
1. Camera card on Night: Lock camera on. Activate Night, try to move Cam02: it must not move
   (Hierarchy > Link Info shows all locks ticked).
2. Rename Cam02 to Cam02_new: Night still activates it.
3. Delete Cam02_new: status bar shows a warning. Right-click > Repair missing nodes..., pick Cam01, Repair.

## 7. Frames from camera keys
Frames card on a setup that uses Cam01: Type = camera. Activate: Render Setup shows Range 10 to 80.
Card menu "Range from camera keys (fixed)" stores the range as numbers instead.

## 8. Claude
In `claude` (from F:\scene-manager): "capture a baseline, then make a setup Dusk with only Fill on at 5 and
Vegetation hidden, and add a to-do 'check glass'". Expect calls to capture_baseline, capture_setup,
set_lights, set_layers, todo.

## API calls to confirm (report any error text)
| Feature | Call |
|---|---|
| Lights colour on Corona lights | property name `colorDirect` (guess) |
| XRef Scenes | `xrefs.getXRefFile i` then `.hidden`, `.disabled` |
| Camera lock | `getTransformLockFlags` returns BitArray, read `.numberSet` from Python |
| Camera keys | MAXScript `SM_keyRange` walker (Physical camera with animated FOV is a good test) |
