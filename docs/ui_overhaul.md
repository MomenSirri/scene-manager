# UI overhaul (2026-11-18)

How the Scene Manager 3 beta is built, seen from outside only (folder layout, no files opened): a separate
Electron app (web UI in its own .exe) plus a 3ds Max plugin under `plugins/max`; the two talk over a local
connection. Its UI therefore redraws only what changed and never runs inside Max's event loop.
We keep the UI inside Max (direct scene access, no round trips) and take the same two ideas:
update in place, and keep scene events cheap.

## What changed

| Area | Before | Now |
|---|---|---|
| Edit a value | every card, the tree, chips and queue rebuilt (about 440 ms in the stand-in, focus and scroll lost) | only the changed rows update (about 4 ms); field keeps focus |
| Switch setup | all cards rebuilt | same cards show the other setup's values |
| Add / remove module, recolour, reorder | whole board rebuilt | one card added, dropped or moved |
| Setups list | cleared and refilled on every change, tooltips built for every row | rows updated in place, tooltip built on hover, full-row rounded highlight, slim columns (right-click header) |
| New setup / folder | modal name dialog | appears at once, name edited in the list |
| Window resize | application-wide event filter (ran for every 3ds Max event) + override cursor | 8 edge grips owned by the window |
| Window log | every window Max opened was written to disk with a stack | off; config `"debug_windows": true` turns it on |
| Scene callbacks | one Python run per deleted or renamed node, also during File > Open | recorded and handled once, 150 ms after the burst; ignored while a file loads |
| Config file | read from disk dozens of times per refresh | cached, re-read only when the file changes; atomic write |
| Undo | panel changes to the scene had no undo step | Activate and live edits are one undo step each |
| Activate | viewport redrawn per module | redraw suspended, one redraw at the end |
| Camera / sun pickers | list fixed when the card was built | re-read from the scene when opened |
| Coming back from Max | 'differs' dots stale | scene re-read when the window is activated |

Keys in the setups list: Enter activate, F2 rename, Del delete, Ctrl+D duplicate, Ctrl+N new setup,
Ctrl+Shift+N new folder; Ctrl+F search.

Bug fixed on the way: `add_setup(parent="Folder name")` stored the name instead of the folder id.

## For module threads
- A card widget from `ui/kinds_*.py` may add `set_value(value)`; then it is updated in place. Without it the
  card swaps just that widget when its value changes.
- Never rebuild the board to show a change: call `mgr.commit()` / `mgr._notify()`, the panel syncs.
- Status bar messages: `panel.flash(text)`.

## Test in 3ds Max
Run `dev_reload.py`, then:
1. Edit Width on Resolution & Output, press Tab: focus moves to Height, the list column updates, nothing flickers.
2. Type in the search box and in a card field: Max shortcuts must not fire (if they do, see the first row below).
3. Drag every window edge and corner; drag the title bar; double-click it to maximise and again to restore.
4. New Setup: a row appears in rename mode. Enter, then Ctrl+Z in Max after Activate restores lights/camera.
5. Delete 100+ objects at once, then File > Open another scene: no pause, no errors in the Listener.
6. Change a light in Max, click back on Scene Manager: the row's dot turns orange.

## API names to verify in Max
| Call | Used for | If it fails |
|---|---|---|
| `qtmax.DisableMaxAcceleratorsOnFocus(window, True)` | typing in our fields must not trigger Max shortcuts | silently skipped; tell me and I switch to `rt.enableAccelerators` on focus |
| `callbacks.addScript #postRendererChange`, `#filePostMerge`, `#filePreOpen`, `#systemPreReset`, `#systemPreNew` | refresh on renderer change, ignore events while loading | Listener shows an error at startup |
| `disableSceneRedraw()` / `enableSceneRedraw()` | one redraw per activation | silently skipped |
| `QWindow.startSystemResize` / `startSystemMove` | edge resize, title drag (already used before) | window does not resize |
