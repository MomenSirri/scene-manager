// Scene Manager app: its own window, talking to 3ds Max over the local bridge (scene_manager/bridge/max_server.py).
// 127.0.0.1 only; the port and a random token come from ~/.scene_manager/bridge.json, written by 3ds Max.
const { app, BrowserWindow, Menu, ipcMain, nativeTheme, shell, screen } = require("electron");
const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");
const { createChat } = require("./chat.cjs");

const HOME = process.env.SCENE_MANAGER_HOME || path.join(os.homedir(), ".scene_manager");
const BRIDGE_FILE = path.join(HOME, "bridge.json");
const STORE_FILE = path.join(HOME, "app_ui.json");

let win = null;

// What happened to the window, for when it "disappears": ~/.scene_manager/app.log (kept small).
const LOG_FILE = path.join(HOME, "app.log");
function log(text) {
  try {
    if (fs.existsSync(LOG_FILE) && fs.statSync(LOG_FILE).size > 200000) fs.renameSync(LOG_FILE, LOG_FILE + ".old");
    fs.appendFileSync(LOG_FILE, new Date().toISOString() + " " + text + "\n");
  } catch (_) { /* logging must never break the app */ }
}
let store = {};
try { store = JSON.parse(fs.readFileSync(STORE_FILE, "utf8")); } catch (_) { store = {}; }
let saveTimer = null;
function saveStore() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      fs.mkdirSync(HOME, { recursive: true });
      fs.writeFileSync(STORE_FILE + ".tmp", JSON.stringify(store, null, 2));
      fs.renameSync(STORE_FILE + ".tmp", STORE_FILE);
    } catch (e) { console.error("store:", e.message); }
  }, 300);
}

// ---- bridge connection -----------------------------------------------------------
let sock = null, token = "", connected = false, nextId = 1, buffer = "";
const pending = new Map();

function emit(ev) { if (win && !win.isDestroyed()) win.webContents.send("sm:event", ev); }

function setConnected(on) {
  if (connected !== on) { connected = on; emit({ event: on ? "connected" : "disconnected" }); }
}

function connect() {
  let info;
  try { info = JSON.parse(fs.readFileSync(BRIDGE_FILE, "utf8")); } catch (_) { return retry(); }
  token = info.token; maxPid = Number(info.pid) || 0;
  const s = net.createConnection({ host: "127.0.0.1", port: info.port });
  s.setEncoding("utf8");
  s.on("connect", () => {
    sock = s; buffer = "";
    s.write(JSON.stringify({ token, cmd: "subscribe", id: 0 }) + "\n");
    setConnected(true);
    attach();
  });
  s.on("data", (chunk) => {
    buffer += chunk;
    let i;
    while ((i = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, i); buffer = buffer.slice(i + 1);
      if (!line.trim()) continue;
      let msg; try { msg = JSON.parse(line); } catch (_) { continue; }
      if (msg.event === "show") { comeToFront(); continue; }
      if (msg.event === "closing") releaseOwner();
      if (msg.event) { emit(msg); continue; }
      const p = pending.get(msg.id);
      if (p) { pending.delete(msg.id); msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error || "error")); }
    }
  });
  const lost = () => {
    if (sock === s) sock = null;
    releaseOwner();
    for (const p of pending.values()) p.reject(new Error("3ds Max closed the connection"));
    pending.clear();
    setConnected(false);
    retry();
  };
  s.on("error", () => {});
  s.on("close", lost);
}
let retryTimer = null;
function retry() { clearTimeout(retryTimer); retryTimer = setTimeout(connect, 1500); }

function call(cmd, args) {
  return new Promise((resolve, reject) => {
    if (!sock) return reject(new Error("Not connected to 3ds Max"));
    const id = nextId++;
    pending.set(id, { resolve, reject });
    sock.write(JSON.stringify({ token, cmd, args, id }) + "\n");
  });
}

// ---- a tool window of 3ds Max ---------------------------------------------------------
// The window is an "owned" window of the 3ds Max main window (Win32 owner, GWLP_HWNDPARENT), the same relation a
// MAXScript or Qt tool dialog has to Max. Windows itself then does everything: the window is always above Max and
// never above other programs, it disappears when Max is minimized and returns with it, it has no taskbar button of
// its own, and the Max taskbar button stands for both. Nothing here watches or moves windows to get that.
// Not owned (Settings > Attach off, not on Windows, or the owner could not be set): a normal window that floats
// above everything unless the pin is off.
let user32 = null;
function win32() {
  if (user32 !== null) return user32;
  user32 = false;
  if (process.platform !== "win32") return user32;
  try {
    const koffi = require("koffi");
    const lib = koffi.load("user32.dll");
    koffi.struct("POINT", { x: "long", y: "long" });
    user32 = {
      GetTopWindow: lib.func("intptr_t GetTopWindow(intptr_t hWnd)"),
      GetWindowLongPtrW: lib.func("intptr_t GetWindowLongPtrW(intptr_t hWnd, int nIndex)"),
      GetAsyncKeyState: lib.func("short GetAsyncKeyState(int vKey)"),
      GetCursorPos: lib.func("int GetCursorPos(_Out_ POINT *p)"),
      WindowFromPoint: lib.func("intptr_t WindowFromPoint(POINT p)"),
      GetAncestor: lib.func("intptr_t GetAncestor(intptr_t hWnd, uint32_t flags)"),
      SetWindowLongPtrW: lib.func("intptr_t SetWindowLongPtrW(intptr_t hWnd, int nIndex, intptr_t dwNewLong)"),
      GetWindow: lib.func("intptr_t GetWindow(intptr_t hWnd, uint32_t uCmd)"),
      IsWindow: lib.func("int IsWindow(intptr_t hWnd)"),
      IsIconic: lib.func("int IsIconic(intptr_t hWnd)"),
      GetForegroundWindow: lib.func("intptr_t GetForegroundWindow()"),
      GetWindowThreadProcessId: lib.func("uint32_t GetWindowThreadProcessId(intptr_t hWnd, _Out_ uint32_t *lpdwProcessId)"),
      GetClassNameW: lib.func("int GetClassNameW(intptr_t hWnd, void *buf, int n)"),
      GetWindowTextW: lib.func("int GetWindowTextW(intptr_t hWnd, void *buf, int n)"),
      IsWindowVisible: lib.func("int IsWindowVisible(intptr_t hWnd)"),
      IsWindowEnabled: lib.func("int IsWindowEnabled(intptr_t hWnd)"),
      SetWindowPos: lib.func("int SetWindowPos(intptr_t hWnd, intptr_t hWndInsertAfter, int X, int Y, int cx, int cy, uint32_t uFlags)"),
      kernel: { RtlMoveMemory: koffi.load("kernel32.dll").func("void RtlMoveMemory(void *dest, uintptr_t src, size_t len)") },
    };
  } catch (e) { log("win32 unavailable: " + e.message); }
  return user32;
}
const GWLP_HWNDPARENT = -8, GW_OWNER = 4, SWP_ZONLY = 0x0001 | 0x0002 | 0x0010;   // no size, no move, no activate
let maxHwnd = 0n, maxPid = 0, owned = false, rolled = false, fullBounds = null;   // owned = owner is 3ds Max

function hwndArg(argv) {
  const a = (argv || []).find((x) => String(x).startsWith("--max-hwnd="));
  try { return a ? BigInt(a.split("=")[1]) : 0n; } catch (_) { return 0n; }
}
function ownHwnd() {
  const b = win.getNativeWindowHandle();
  return b.length >= 8 ? b.readBigInt64LE(0) : BigInt(b.readInt32LE(0));
}
function ownerNow(u) {
  try { return BigInt(u.GetWindow(ownHwnd(), GW_OWNER) || 0); } catch (_) { return 0n; }
}
/** Make 3ds Max the owner of the window, or release it (Settings > Attach off, hwnd 0). True when owned afterwards. */
function setOwner(hwnd) {
  if (!win || win.isDestroyed()) return false;
  const u = win32();
  if (hwnd) maxHwnd = BigInt(hwnd);
  const want = u && store.attach !== false && maxHwnd && u.IsWindow(maxHwnd) ? maxHwnd : 0n;
  if (u) {
    try {
      const me = ownHwnd();
      if (ownerNow(u) !== want) {
        u.SetWindowLongPtrW(me, GWLP_HWNDPARENT, want);
        if (want) u.SetWindowPos(me, 0n, 0, 0, 0, 0, SWP_ZONLY);   // HWND_TOP: Windows puts it above its owner now
        log(want ? "owner set: 3ds Max window " + want : "owner released");
      }
      owned = !!want && ownerNow(u) === want;
    } catch (e) { log("owner: " + e.message); owned = false; }
  } else owned = false;
  applyOnTop();
  win.setSkipTaskbar(owned);   // an owned window has no taskbar button; said again for Electron's own bookkeeping
  return owned;
}
// Owned by 3ds Max: Windows already keeps the window above 3ds Max, so it is NEVER made "always on top" as well.
// Electron's default always-on-top level re-places the window right behind the Windows taskbar every time it is
// activated. The taskbar is not always a topmost window (it is not while a full-screen window is up), and then
// "behind the taskbar" is the very bottom of the stack: Windows moved the owner with it, so one click on the app
// sent 3ds Max and all its tool windows behind every other program (it looked like a minimize).
// Not owned (Attach off, or 3ds Max gone): floats above everything unless switched off, at a level Electron does
// not tie to the taskbar.
function applyOnTop() {
  if (!win || win.isDestroyed()) return;
  if (!owned && store.onTop !== false) win.setAlwaysOnTop(true, "screen-saver");
  else win.setAlwaysOnTop(false);
}
// 3ds Max is closing or the connection dropped: let go first. Windows destroys owned windows with their owner;
// released, the app stays open and attaches again when Max is back.
function releaseOwner() {
  const u = win32();
  if (!u || !win || win.isDestroyed()) return;
  try {
    if (ownerNow(u)) { u.SetWindowLongPtrW(ownHwnd(), GWLP_HWNDPARENT, 0n); log("owner released (3ds Max gone)"); }
  } catch (e) { log("owner: " + e.message); }
  owned = false;
  win.setSkipTaskbar(false);
  applyOnTop();
  emit({ event: "window", ...windowState() });
}

// Read-only notes for ~/.scene_manager/app.log: which program is in front and when 3ds Max is minimized. It changes
// nothing; it is there so a report like "Max minimized by itself" can be traced to what happened just before.
let lastFront = "", lastState = "";
function describe(u, hwnd) {   // "class 'title' pid"
  if (!hwnd) return "nothing";
  const text = (fn) => { const b = Buffer.alloc(256); const n = fn(hwnd, b, 120); return b.toString("utf16le", 0, Math.max(0, n) * 2); };
  const out = [0]; u.GetWindowThreadProcessId(hwnd, out);
  const pid = out[0] >>> 0;
  const whose = hwnd === ownHwnd() ? "APP" : hwnd === maxHwnd ? "MAX" : pid === maxPid ? "max-other" : pid === process.pid ? "app-other" : "other";
  return whose + " " + text(u.GetClassNameW) + " '" + text(u.GetWindowTextW).slice(0, 40) + "' pid " + pid + " hwnd " + hwnd;
}
function watch() {
  const u = win32();
  if (!u || !win || win.isDestroyed() || !maxHwnd) return;
  try {
    if (!u.IsWindow(maxHwnd)) return;
    const me = ownHwnd();
    const state = "max " + (u.IsIconic(maxHwnd) ? "minimized" : "open") + (u.IsWindowVisible(maxHwnd) ? "" : " hidden") + (u.IsWindowEnabled(maxHwnd) ? "" : " disabled")
      + ", app " + (u.IsIconic(me) ? "minimized" : "open") + (u.IsWindowVisible(me) ? "" : " hidden") + (ownerNow(u) === maxHwnd ? "" : " NOT-OWNED");
    if (state !== lastState) { lastState = state; log("state: " + state); }
    const front = BigInt(u.GetForegroundWindow() || 0);
    const who = String(front);
    if (who !== lastFront) { lastFront = who; log("in front: " + describe(u, front)); }
  } catch (e) { if (!watch.failed) { watch.failed = true; log("watch: " + e.message); } }
}
// Diagnostics for "3ds Max minimizes by itself": every mouse button press anywhere (which button, where, over which
// window) and the Windows key. Positions and window names only, nothing typed; it stays in the local app.log.
const BUTTONS = { 1: "left", 2: "right", 4: "middle", 5: "x1", 6: "x2", 0x5b: "Win key", 0x5c: "Win key" };
const held = {};
function watchInput() {
  const u = win32();
  if (!u || !win || win.isDestroyed()) return;
  try {
    for (const [vk, name] of Object.entries(BUTTONS)) {
      const st = u.GetAsyncKeyState(Number(vk));
      const down = (st & 0x8000) !== 0;
      if (!down && !held[vk] && (st & 1)) log("input: " + name + " pressed and released (short click)");   // between two checks
      if (down === !!held[vk]) continue;
      held[vk] = down;
      if (!down) { log("input: " + name + " up"); continue; }
      const p = {}; u.GetCursorPos(p);
      const at = BigInt(u.WindowFromPoint(p) || 0), root = at ? BigInt(u.GetAncestor(at, 2) || 0) : 0n;
      log("input: " + name + " down at " + p.x + "," + p.y + " over " + describe(u, root || at));
    }
  } catch (e) { if (!watchInput.failed) { watchInput.failed = true; log("watchInput: " + e.message); } }
}
// Every visible top-level window with a title, front to back, written when the list changes: program, class, title,
// flags (TOP = always on top, TOOL = tool window, APPWIN = forced taskbar button, NOACT, MIN) and its owner. Used to
// compare how another tool window (for example Scene Manager 3 beta) sits next to 3ds Max: read from outside, like
// Spy++, never from that program's files.
const exeNames = new Map();
let kernel32 = null, lastSurvey = "";
function exeOf(pid) {
  if (exeNames.has(pid)) return exeNames.get(pid);
  let name = "?";
  try {
    if (kernel32 === null) {
      const k = require("koffi").load("kernel32.dll");
      kernel32 = {
        OpenProcess: k.func("void *OpenProcess(uint32_t access, int inherit, uint32_t pid)"),
        QueryFullProcessImageNameW: k.func("int QueryFullProcessImageNameW(void *h, uint32_t flags, void *buf, _Inout_ uint32_t *size)"),
        CloseHandle: k.func("int CloseHandle(void *h)"),
      };
    }
    const h = kernel32.OpenProcess(0x1000, 0, pid);
    if (h) {
      const buf = Buffer.alloc(1040), size = [520];
      if (kernel32.QueryFullProcessImageNameW(h, 0, buf, size)) name = path.win32.basename(buf.toString("utf16le", 0, size[0] * 2));
      kernel32.CloseHandle(h);
    }
  } catch (e) { if (kernel32 === null) kernel32 = false; }
  exeNames.set(pid, name);
  return name;
}
function survey() {
  const u = win32();
  if (!u || !win || win.isDestroyed()) return;
  try {
    const text = (fn, h) => { const b = Buffer.alloc(256); const n = fn(h, b, 120); return b.toString("utf16le", 0, Math.max(0, n) * 2); };
    const rows = [];
    let h = BigInt(u.GetTopWindow(0n) || 0), guard = 0;
    while (h && guard++ < 3000) {
      if (u.IsWindowVisible(h)) {
        const title = text(u.GetWindowTextW, h);
        const out = [0]; u.GetWindowThreadProcessId(h, out);
        const pid = out[0] >>> 0, owner = BigInt(u.GetWindow(h, GW_OWNER) || 0);
        if (title || pid === maxPid || owner === maxHwnd) {
          const ex = BigInt(u.GetWindowLongPtrW(h, -20));
          const flags = [(ex & 0x8n) && "TOP", (ex & 0x80n) && "TOOL", (ex & 0x40000n) && "APPWIN", (ex & 0x8000000n) && "NOACT", u.IsIconic(h) && "MIN"].filter(Boolean).join("+");
          rows.push(exeOf(pid) + " | " + text(u.GetClassNameW, h) + " | '" + title.slice(0, 36) + "' | " + (flags || "-") + " | hwnd " + h + (owner ? " owner " + owner : ""));
        }
      }
      h = BigInt(u.GetWindow(h, 2) || 0);   // GW_HWNDNEXT: the next one further back
    }
    const all = rows.join("\n    ");
    if (all !== lastSurvey) { lastSurvey = all; log("windows front to back (foreground " + BigInt(u.GetForegroundWindow() || 0) + "):\n    " + all); }
  } catch (e) { if (!survey.failed) { survey.failed = true; log("survey: " + e.message); } }
}
// What Windows tells the app window itself (Windows only): shown/hidden with its owner, activated, system commands.
function hookMessages() {
  if (process.platform !== "win32" || !win.hookWindowMessage) return;
  const names = { 0x000a: "WM_ENABLE", 0x0018: "WM_SHOWWINDOW", 0x001c: "WM_ACTIVATEAPP", 0x0112: "WM_SYSCOMMAND", 0x0002: "WM_DESTROY", 0x0010: "WM_CLOSE",
    0x0021: "WM_MOUSEACTIVATE", 0x0086: "WM_NCACTIVATE", 0x00a1: "WM_NCLBUTTONDOWN", 0x0231: "WM_ENTERSIZEMOVE", 0x0232: "WM_EXITSIZEMOVE", 0x0005: "WM_SIZE", 0x0046: "WM_WINDOWPOSCHANGING", 0x0047: "WM_WINDOWPOSCHANGED" };
  for (const [code, name] of Object.entries(names)) {
    try {
      win.hookWindowMessage(Number(code), (w, l) => {
        const num = (b) => { try { return "0x" + (b.length >= 8 ? b.readBigUInt64LE(0) : BigInt(b.readUInt32LE(0))).toString(16); } catch (_) { return "?"; } };
        let extra = "";
        if (name.startsWith("WM_WINDOWPOS")) {   // WINDOWPOS: hwnd, hwndInsertAfter, x, y, cx, cy, flags
          try {
            const k = win32().kernel, buf = Buffer.alloc(40);
            k.RtlMoveMemory(buf, l.readBigUInt64LE(0), 40);
            const flags = buf.readUInt32LE(32);
            if (flags & 0x4) return;   // SWP_NOZORDER: its place in the stack does not change
            extra = " after=" + buf.readBigUInt64LE(8) + " flags=0x" + flags.toString(16) + " foreground " + BigInt(win32().GetForegroundWindow() || 0);
          } catch (e) { extra = " (" + e.message + ")"; }
        }
        log("msg " + name + " w=" + num(w) + " l=" + num(l) + extra);
      });
    } catch (e) { log("hook " + name + ": " + e.message); }
  }
}
async function attach() {   // after every (re)connect: Max tells us its window, we tell Max ours
  if (!win || win.isDestroyed()) return;
  try {
    const me = process.platform === "win32" ? ownHwnd().toString() : "0";
    const r = await call("ui_app_attach", { hwnd: me, exe: process.execPath, pid: process.pid });
    if (r && r.root) { store.root = r.root; saveStore(); }
    const target = r && r.max_hwnd ? BigInt(r.max_hwnd) : maxHwnd;
    if (!setOwner(target) && store.attach !== false && target && win32()) {
      // second way: 3ds Max sets the owner (needed when Max runs with higher rights than the app)
      const r2 = await call("ui_app_attach", { hwnd: me, exe: process.execPath, pid: process.pid, from_max: true });
      if (r2 && r2.owned) { owned = true; applyOnTop(); win.setSkipTaskbar(true); }
    }
    log("tool window of 3ds Max: " + owned + " (window " + maxHwnd + ", process " + maxPid + ")");
    emit({ event: "window", ...windowState() });
  } catch (_) { /* older Scene Manager code in Max: stay a normal window */ }
}
function windowState() {
  return { owned, rolled, attach: store.attach !== false, onTop: !owned && store.onTop !== false };
}

// A minimized tool window is easy to lose, so the minimize button rolls the window up to its title bar, in place.
const ROLLED = { width: 300, height: 38 };
function setRolled(on) {
  if (!win || win.isDestroyed() || rolled === on) return rolled;
  if (on) {
    if (win.isMaximized()) win.unmaximize();
    fullBounds = win.getBounds();
    rolled = true;
    win.setMinimumSize(ROLLED.width, ROLLED.height);
    win.setBounds({ x: fullBounds.x, y: fullBounds.y, ...ROLLED });
    win.setResizable(false);
  } else {
    win.setResizable(true);
    win.setMinimumSize(620, 420);
    if (fullBounds) { const p = win.getBounds(); win.setBounds({ ...fullBounds, x: p.x, y: p.y }); }
    rolled = false;
  }
  emit({ event: "window", ...windowState() });
  return rolled;
}
/** True when a good part of the rectangle lies on one of the screens. */
function onScreen(r) {
  if (!r || !Number.isFinite(r.x) || !Number.isFinite(r.y)) return false;
  const w = r.width || 620, h = r.height || 420;
  return screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return r.x + w > a.x + 80 && r.x < a.x + a.width - 80 && r.y >= a.y - 20 && r.y < a.y + a.height - 40;
  });
}
function comeToFront() {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  if (!onScreen(win.getBounds())) win.center();   // lost off screen: bring it back where it can be seen
  setRolled(false);
  win.show(); win.focus();
}

// ---- window ------------------------------------------------------------------------
function createWindow() {
  nativeTheme.themeSource = "dark";   // dark title bar
  Menu.setApplicationMenu(null);      // no File/Edit menu row under the title bar
  const b = { ...(store.window || {}) };
  if (!onScreen(b)) { delete b.x; delete b.y; }   // saved on a screen that is gone, or while the window was parked off screen
  if (b.width > 8000 || b.height > 8000) { delete b.width; delete b.height; }   // a size no screen has: saved while another tool had parked the window
  win = new BrowserWindow({
    width: b.width || 1240, height: b.height || 780, x: b.x, y: b.y,
    minWidth: 620, minHeight: 420,
    // A normal Windows frame, like the other tool windows of 3ds Max: Windows moves, snaps, minimizes and
    // maximizes it. (It used to be frameless with its own title bar and a roll-up instead of minimize.)
    backgroundColor: "#0b0b10", show: false,
    title: "Scene Manager",
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.setMenuBarVisibility(false);
  if (process.env.SM_DEV_URL) win.loadURL(process.env.SM_DEV_URL);
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  win.once("ready-to-show", () => { setOwner(maxHwnd); win.show(); });   // owner first: no taskbar button flashes up
  // Tracing for window reports, off unless "debugWindow": true is set in ~/.scene_manager/app_ui.json.
  // Also switched on by a file ~/.scene_manager/trace_windows whose text starts with "on" (no restart of 3ds Max needed, only of the app).
  let traceFile = "";
  try { traceFile = fs.readFileSync(path.join(HOME, "trace_windows"), "utf8").trim(); } catch (_) { /* no file */ }
  if (store.debugWindow === true || /^on\b/i.test(traceFile)) {
    setInterval(watch, 150); setInterval(watchInput, 30); setInterval(survey, 200); hookMessages();
  }
  for (const ev of ["minimize", "restore", "maximize", "unmaximize", "hide", "show", "focus", "blur"])
    win.on(ev, () => log("window " + ev + (owned ? " (attached)" : "")));
  const remember = () => {
    if (rolled || win.isMaximized() || win.isMinimized()) return;
    const now = win.getBounds();
    if (!onScreen(now) || now.width > 8000 || now.height > 8000) return;   // parked off screen (minimized, or hidden by another tool): never a place to reopen at
    store.window = now; saveStore();
  };
  win.on("resize", remember);
  win.on("move", remember);
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e) => e.preventDefault());
}

// Own profile folder. The default would be %APPDATA%\Scene Manager, the same name another product's app can use
// (Pulze Scene Manager); two apps sharing it would share the one-instance lock and their stored data.
try { app.setPath("userData", path.join(HOME, "electron")); } catch (_) { /* default folder */ }
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  maxHwnd = hwndArg(process.argv);
  app.on("second-instance", (_e, argv) => {   // the toolbar button in 3ds Max was pressed again: come to the front
    const h = hwndArg(argv);
    if (h) setOwner(h);
    comeToFront();
  });
  app.whenReady().then(() => {
    ipcMain.handle("sm:call", (_e, cmd, args) => call(String(cmd), args || {}));
    const chat = createChat({ home: HOME, log, emit, getRoot: () => process.env.SCENE_MANAGER_ROOT || store.root || "" });
    ipcMain.handle("sm:chat", (_e, what, text, allow) => {
      if (what === "send") return chat.send(String(text || ""), Array.isArray(allow) ? allow.map(String) : []);
      if (what === "stop") return chat.stop();
      if (what === "reset") return chat.reset();
      if (what === "sign-in") return chat.signIn();
      return chat.status();
    });
    app.on("before-quit", () => chat.stop());
    ipcMain.handle("sm:status", () => ({ connected, ...windowState() }));
    ipcMain.handle("sm:store-get", (_e, key) => store[key]);
    ipcMain.handle("sm:store-set", (_e, key, value) => { store[key] = value; saveStore(); });
    ipcMain.handle("sm:on-top", (_e, on) => { store.onTop = !!on; saveStore(); applyOnTop(); return !owned && !!on; });
    ipcMain.handle("sm:attach", (_e, on) => {
      store.attach = !!on; saveStore();
      setOwner(maxHwnd); emit({ event: "window", ...windowState() });
      if (on && connected && !owned) attach();
      return !!on;
    });
    ipcMain.handle("sm:roll", (_e, on) => setRolled(!!on));
    // The title bar is moved by us, not by Windows. As a system title bar (app-region: drag) Windows applied its
    // own title bar behaviour to it: shaking it minimizes every other window, 3ds Max included, and an attached
    // window disappears with Max. Here a press only records where the pointer is, and moves follow the pointer.
    let drag = null;
    ipcMain.on("sm:drag", (_e, phase, x, y) => {   // x, y: pointer on the screen
      if (!win || win.isDestroyed()) return;
      const p = { x: Math.round(Number(x) || 0), y: Math.round(Number(y) || 0) };
      if (phase === "start") {
        log("title bar pressed");
        if (win.isMaximized()) { drag = null; return; }
        const b = win.getBounds();
        drag = { dx: p.x - b.x, dy: p.y - b.y, w: b.width, h: b.height };
      } else if (phase === "move" && drag) {
        win.setBounds({ x: p.x - drag.dx, y: p.y - drag.dy, width: drag.w, height: drag.h });   // size passed too: it must not creep on scaled screens
      } else if (phase === "end") { if (drag) log("title bar released"); drag = null; }
    });
    ipcMain.on("sm:win", (_e, what) => {
      log("button " + what);
      if (what === "minimize") win.minimize();
      else if (what === "maximize") win.isMaximized() ? win.unmaximize() : win.maximize();
      else if (what === "close") win.close();
    });
    createWindow();
    connect();
  });
  app.on("window-all-closed", () => app.quit());
}
