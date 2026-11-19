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

## A tool window of 3ds Max

The app window is an owned window of the 3ds Max main window (Win32 owner, `GWLP_HWNDPARENT`, set in
`app/electron/main.cjs` `setOwner` with koffi + user32). This is the relation a MAXScript or Qt tool dialog has to Max,
and Windows does all of the window handling; the app does not watch or move windows.

| Behaviour | How |
|---|---|
| Always above 3ds Max, never above other programs | owned window (Windows) |
| Minimizes with Max and returns in front of it | owned window (Windows) |
| No taskbar button of its own; the Max button stands for both | owned window (Windows) |
| Toolbar button while the app is open | `commands_app.bring_to_front()` shows it, unrolls it and gives it focus |
| Pin button | above all programs (off by default) |
| Settings > Tool window of 3ds Max | off = free window that floats above everything |
| Max closes or the bridge drops | the owner is released first (`releaseOwner`), the app stays open and attaches again |

Handshake: after each connect the app calls `ui_app_attach(hwnd)` and gets the Max window handle back
(`rt.windows.getMAXHWND()`), then sets the owner. If that fails (Max running as administrator), it asks Max to set it
(`from_max`). The first launch gets the handle on the command line (`--max-hwnd=`), so the owner is set before the
window is shown.

Known cost of an owned window in another program: Windows links the input of the two, so while Max is busy
(rendering, loading) the app reacts slowly, like any Max dialog.

History (2026-11-18/19): the first owned version was replaced by a window that followed Max by polling, after a
report that pressing the app's title bar minimized Max. The polling version needed two clicks on the taskbar to
minimize Max and came back behind it, so ownership is back. Tested on the real PC on 2026-11-19 (clicks sent by
remote control and the user's own): clicking Max, the app or its title bar never minimizes; only a click on the Max
taskbar icon does, which minimizes and restores both, as for any Max dialog. The earlier "title bar minimizes Max"
report was such taskbar clicks.

Tracing: set `"debugWindow": true` in `~/.scene_manager/app_ui.json`, or put a file `~/.scene_manager/trace_windows` whose text starts with `on`, and restart the app. `app.log` then records who
is in front, Max/app window states, the window messages the app receives and every mouse button press (position and
window under it, nothing typed). Off by default.

Build note: the package must contain `resources/app.asar.unpacked/node_modules/@koromix/koffi-win32-x64/win32_x64/koffi.node`.
Use `npm run build:win` (it installs that Windows binary and checks for it); without it the app logs
"win32 unavailable" and stays a normal window.

## The board is a free canvas

- A card stays where it is dropped: `gx`, `gy` (dots) per card in `~/.scene_manager/app_ui.json` under `cards`. Drop on an occupied
  place and it lands in the nearest empty one (`grid.ts` `freeSpot`). Cards never placed by hand are packed into two columns.
- The board always keeps 24 empty dots right of and below the last card and scrolls both ways; dragging near an edge scrolls.
- Nothing overlaps: a card that grows or is resized pushes the cards under it down (`grid.ts` `layout`).
- Smallest card: wide enough for its full title and for label + value + tick (15 dots, tables 22), tall enough for the header
  and about three rows. A card smaller than its rows scrolls them under a fixed header.

## Title bar

The window has the normal Windows frame (dark), like Scene Manager 3 beta: Windows moves, snaps, maximizes and
minimizes it; the file name is in the window title. A minimized owned window becomes the small bar at the bottom left
of the screen (standard for tool windows); the toolbar button in Max brings it back.

Compared on the real PC on 2026-11-19 with a window survey (owner, flags; read from outside, nothing of the other
product opened): the beta window is an Electron window (`Chrome_WidgetWin_1`) whose owner is the 3ds Max main window,
not always-on-top, with the normal frame. Ours is now the same in all of these. Before, ours was frameless with its
own title bar, moved by the app, and rolled up instead of minimizing.

## Claude chat

Rail button "Claude" opens a drawer on the right (`app/src/Chat.tsx`). Each message runs the user's own Claude Code CLI
(`app/electron/chat.cjs`): `claude -p --output-format stream-json --include-partial-messages`, message on stdin, `--resume` for
the following messages. No API key is stored; it uses the account the CLI is signed in with.

| Point | How |
|---|---|
| Tools | only this project's 3ds Max MCP server (`--mcp-config ~/.scene_manager/chat_mcp.json --strict-mcp-config --tools ""`), started with the command from `.mcp.json` (default `python`) |
| Asked first | `delete_setup`, `render_setups`, `run_python`, `run_maxscript`, `create_sun` are "ask" rules in `--settings`; with `--permission-prompts none` the CLI refuses them and lists them in `permission_denials`; the chat shows Allow / Don't and resumes with the tool allowed for one turn |
| Guidance | repo `CLAUDE.md` (the CLI runs in the Scene Manager folder) + `chat_guide.txt` |
| Stop | kills the CLI and its tool server (`taskkill /T`) |
| Not signed in / not installed | message with a "Sign in to Claude" button (opens a terminal with `claude /login`) or an install link |

Tested end to end on Linux (Electron + CLI + MCP server + stand-in 3ds Max): tool steps, the Allow flow and resume. Not yet run on
Windows: finding `claude.exe` / `claude.cmd`, and `taskkill`.
