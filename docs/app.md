# Scene Manager app (separate window)

The UI is a separate Electron app, like the Scene Manager 3 beta; 3ds Max keeps the Python core and modules.

```
3ds Max                                   Scene Manager.exe (Electron)
 scene_manager/core, modules               electron/main.cjs   window, socket to Max, saved layout
 bridge/max_server.py  127.0.0.1 + token   electron/preload.cjs  the only API the page gets
 bridge/commands_ui.py ui_* commands  <->  src/  React UI (App, Tree, Board, fields)
        pushes {"event": "changed"}         asks ui_state / ui_item again and redraws what changed
```

- 3ds Max is the single source of truth. The app stores only its own look (card places, sizes, colours,
  folded folders) in `~/.scene_manager/app_ui.json`.
- Same bridge as Claude Code uses, so both see the same commands and changes from Claude show up live.
- Edits on the active setup go to the scene at once, each as one undo step in Max.

## Run it
| Goal | How |
|---|---|
| Open from Max | Scripting > Run Script > `open_app.py` (or run `install_scene_manager.ms` once for a toolbar button) |
| First start | the zip `app/release/SceneManager-win.zip` is unpacked once to `~/.scene_manager/app/`, then started |
| Work on the UI without Max | `python tools/dev_backend.py`, then in `app/`: `npm install`, `npm run dev`, open http://127.0.0.1:5173 |
| Rebuild the app | in `app/`: `npm run build`, `npx electron-builder --win dir --x64`, zip `release/win-unpacked` as `SceneManager-win.zip` |

## The board
Dots every 18 px. A card's left edge, width and height are whole dots; a new card is as tall as its module's
rows. Drag a header or the teal corner: a glowing box and lit dots show exactly where the card lands. Cards
keep their left edge and pack upward. Double-click the corner to fit the content again.

## Status
| Done | Not yet (phase 3) |
|---|---|
| setups list (search, tags, drag to move, rename, colours, keys), cards for every module, tables (lights, layers, objects), to-do, notes, add-module palette, render queue, Claude log, always on top | HDRI browser, file pickers, render progress, editors for toggles / light mix / custom properties (shown read-only), card layout tokens, import/export presets, repair missing nodes |

Tests without Max: `python -m tests.test_bridge_events` (protocol), `python -m tests.test_ui` (Qt panel).
Not yet run against real 3ds Max.

## Attached to 3ds Max

The app window is an owned window of the 3ds Max main window (Win32 `GWLP_HWNDPARENT`).

| Behaviour | How |
|---|---|
| Stays above 3ds Max, not above other programs | owner set in `app/electron/main.cjs` `setOwner()` (koffi, user32) |
| Hides when Max is minimized, returns with it | done by Windows for owned windows |
| Minimize button | rolls the window up to its title bar in place (`setRolled`), it never goes to the taskbar |
| Toolbar button while the app is open | `commands_app.bring_to_front()` shows it, unrolls it and gives it focus |
| Pin button | above all programs (off by default) |
| Settings > Attach this window to 3ds Max | off = free window that floats above everything, as before |

Handshake: after each connect the app calls `ui_app_attach(hwnd)` and gets the Max window handle back
(`rt.windows.getMAXHWND()`); the launcher also passes it as `--max-hwnd=`. If the app cannot set the owner itself,
3ds Max tries (`from_max=True`). The window has no taskbar button while attached. While 3ds Max is busy
(rendering, loading) an attached window can be slow to react, because Windows links the two windows' input.

## The board is a free canvas

- A card stays where it is dropped: `gx`, `gy` (dots) per card in `~/.scene_manager/app_ui.json` under `cards`. Drop on an occupied
  place and it lands in the nearest empty one (`grid.ts` `freeSpot`). Cards never placed by hand are packed into two columns.
- The board always keeps 24 empty dots right of and below the last card and scrolls both ways; dragging near an edge scrolls.
- Nothing overlaps: a card that grows or is resized pushes the cards under it down (`grid.ts` `layout`).
- Smallest card: wide enough for its full title and for label + value + tick (15 dots, tables 22), tall enough for the header
  and about three rows. A card smaller than its rows scrolls them under a fixed header.

## Title bar

The title bar is not a system title bar (`-webkit-app-region: drag` is not used). `App.tsx` `dragBar` follows the pointer and
`main.cjs` `sm:drag` moves the window. Reason: as a system title bar Windows applied its own behaviour to it (shaking it minimizes
all other windows, 3ds Max included, and the attached app window then disappears with Max). Window events and title bar buttons
are written to `~/.scene_manager/app.log`.
