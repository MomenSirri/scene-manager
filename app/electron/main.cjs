// Scene Manager app: its own window, talking to 3ds Max over the local bridge (scene_manager/bridge/max_server.py).
// 127.0.0.1 only; the port and a random token come from ~/.scene_manager/bridge.json, written by 3ds Max.
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");

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
      if (msg.event) { emit(msg); continue; }
      const p = pending.get(msg.id);
      if (p) { pending.delete(msg.id); msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error || "error")); }
    }
  });
  const lost = () => {
    if (sock === s) sock = null;
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

// ---- following 3ds Max ---------------------------------------------------------------
// The window stays above 3ds Max without being tied to it. Several times a second it looks at what Windows has in
// front: while that is 3ds Max (any of its windows) or this app, the window is "always on top"; when another
// program comes to the front it steps back behind it; while 3ds Max is minimized it is hidden.
// It is deliberately NOT an owned window of 3ds Max (GWLP_HWNDPARENT): that links the input of the two programs,
// and on a real machine pressing this window's title bar minimized 3ds Max.
let user32 = null;
function win32() {
  if (user32 !== null) return user32;
  user32 = false;
  if (process.platform !== "win32") return user32;
  try {
    const koffi = require("koffi");
    const lib = koffi.load("user32.dll");
    user32 = {
      SetWindowLongPtrW: lib.func("intptr_t SetWindowLongPtrW(intptr_t hWnd, int nIndex, intptr_t dwNewLong)"),
      GetWindowLongPtrW: lib.func("intptr_t GetWindowLongPtrW(intptr_t hWnd, int nIndex)"),
      GetWindow: lib.func("intptr_t GetWindow(intptr_t hWnd, uint32_t uCmd)"),
      IsWindow: lib.func("int IsWindow(intptr_t hWnd)"),
      IsIconic: lib.func("int IsIconic(intptr_t hWnd)"),
      GetForegroundWindow: lib.func("intptr_t GetForegroundWindow()"),
      GetWindowThreadProcessId: lib.func("uint32_t GetWindowThreadProcessId(intptr_t hWnd, _Out_ uint32_t *lpdwProcessId)"),
      SetWindowPos: lib.func("int SetWindowPos(intptr_t hWnd, intptr_t hWndInsertAfter, int X, int Y, int cx, int cy, uint32_t uFlags)"),
    };
  } catch (e) { log("win32 unavailable: " + e.message); }
  return user32;
}
const GWLP_HWNDPARENT = -8, GW_OWNER = 4, SWP_BEHIND = 0x0001 | 0x0002 | 0x0010;   // no size, no move, no activate
let maxHwnd = 0n, maxPid = 0, owned = false, rolled = false, fullBounds = null;   // owned = following 3ds Max
let topTries = 0, followTimer = null, hiddenForMax = false, topNow = null, lastFront = "";

function hwndArg(argv) {
  const a = (argv || []).find((x) => String(x).startsWith("--max-hwnd="));
  try { return a ? BigInt(a.split("=")[1]) : 0n; } catch (_) { return 0n; }
}
function ownHwnd() {
  const b = win.getNativeWindowHandle();
  return b.length >= 8 ? b.readBigInt64LE(0) : BigInt(b.readInt32LE(0));
}
function pidOf(u, hwnd) {
  try { const out = [0]; u.GetWindowThreadProcessId(hwnd, out); return out[0] >>> 0; } catch (_) { return 0; }
}
function setTop(on) {
  if (topNow === on || !win || win.isDestroyed()) return;
  topNow = on;
  win.setAlwaysOnTop(on);
}
// Is the window really in the always-on-top band? Asked from Windows, not remembered: hiding and showing the
// window (3ds Max minimized and restored) can drop it without telling us.
function reallyTop(u, me) {
  try { return (Number(BigInt(u.GetWindowLongPtrW(me, -20)) & 0x8n)) !== 0; } catch (_) { return topNow === true; }
}
function forceTop(u, me, why) {
  log("back above 3ds Max (" + why + ")");
  topNow = true;
  win.setAlwaysOnTop(false); win.setAlwaysOnTop(true);
  try { u.SetWindowPos(me, -1n, 0, 0, 0, 0, SWP_BEHIND); } catch (e) { log("forceTop: " + e.message); }   // HWND_TOPMOST
}
// "Hidden while 3ds Max is minimized" without hiding the window. A real hide makes Windows pick another window to
// activate, 3ds Max answers that by restoring itself, and Max bounced back up each time it was minimized (seen in
// the log of a real machine). So the window only becomes invisible, lets clicks through and sinks to the bottom:
// nothing is activated or deactivated.
function setGhost(on) {
  if (!win || win.isDestroyed() || hiddenForMax === on) return;
  hiddenForMax = on;
  try {
    win.setOpacity(on ? 0 : 1);
    win.setIgnoreMouseEvents(on);
    if (on) {
      topNow = false; win.setAlwaysOnTop(false);
      const u = win32();
      if (u) u.SetWindowPos(ownHwnd(), 1n, 0, 0, 0, 0, SWP_BEHIND);   // HWND_BOTTOM
    } else topNow = null;   // the next check puts it back above 3ds Max
  } catch (e) { log("ghost: " + e.message); }
}
function follow() {
  const u = win32();
  if (!u || !win || win.isDestroyed() || !maxHwnd) return;
  try {
    if (!u.IsWindow(maxHwnd)) return;   // 3ds Max is closing; the bridge tells us
    const min = !!u.IsIconic(maxHwnd);
    if (min && !hiddenForMax) { log("3ds Max minimized: hiding"); setGhost(true); }
    else if (!min && hiddenForMax) { log("3ds Max restored: showing"); setGhost(false); }
    if (min) return;
    const front = BigInt(u.GetForegroundWindow() || 0);
    const me = ownHwnd(), pid = front ? pidOf(u, front) : 0;
    const ours = front === me || front === maxHwnd || (pid && (pid === maxPid || pid === process.pid));
    const who = ours ? (front === me ? "app" : "max") : "other";
    if (who !== lastFront) { lastFront = who; log("in front: " + who + (min ? " (max minimized)" : "")); }
    if (store.onTop === true || ours) {   // pin (above every program), or 3ds Max / the app is in front
      if (topNow !== true) setTop(true);
      if (reallyTop(u, me)) topTries = 0;
      else if (topTries < 8) { topTries++; forceTop(u, me, who); }   // not endlessly, should Windows refuse
      return;
    }
    topTries = 0;
    if (front && topNow !== false) {   // another program came forward: go behind it, do not cover it
      setTop(false);
      u.SetWindowPos(me, front, 0, 0, 0, 0, SWP_BEHIND);
    }
  } catch (e) { log("follow: " + e.message); }
}
/** Start or stop following 3ds Max (Settings > Attach). Returns true when following. */
function setOwner(hwnd) {
  if (!win || win.isDestroyed()) return false;
  const u = win32();
  clearInterval(followTimer); followTimer = null; topNow = null; lastFront = "";
  if (hwnd) maxHwnd = BigInt(hwnd);
  owned = !!u && store.attach !== false && !!maxHwnd;
  if (u) {
    try {   // a window left owned by an earlier build is released
      const me = ownHwnd();
      if (BigInt(u.GetWindow(me, GW_OWNER) || 0)) u.SetWindowLongPtrW(me, GWLP_HWNDPARENT, 0n);
    } catch (e) { log("release owner: " + e.message); }
  }
  if (!owned) setGhost(false);
  win.setSkipTaskbar(owned);   // a tool window of 3ds Max: no taskbar button of its own
  if (owned) { followTimer = setInterval(follow, 250); follow(); }
  else setTop(store.onTop !== false);   // not following (or not on Windows): float above everything, as before
  return owned;
}
function applyOnTop() { topNow = null; if (owned) follow(); else setTop(store.onTop !== false); }
async function attach() {   // after every (re)connect: Max tells us its window, we tell Max ours
  if (!win || win.isDestroyed()) return;
  try {
    const me = process.platform === "win32" ? ownHwnd().toString() : "0";
    const r = await call("ui_app_attach", { hwnd: me, exe: process.execPath, pid: process.pid });
    setOwner(r && r.max_hwnd ? BigInt(r.max_hwnd) : maxHwnd);
    log("following 3ds Max: " + owned + " (window " + maxHwnd + ", process " + maxPid + ")");
    emit({ event: "window", ...windowState() });
  } catch (_) { /* older Scene Manager code in Max: stay a normal window */ }
}
function windowState() {
  return { owned, rolled, attach: store.attach !== false, onTop: store.onTop === true };
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
function comeToFront() {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  setGhost(false);
  setRolled(false);
  win.show(); win.focus();
}

// ---- window ------------------------------------------------------------------------
function createWindow() {
  const b = store.window || {};
  win = new BrowserWindow({
    width: b.width || 1240, height: b.height || 780, x: b.x, y: b.y,
    minWidth: 620, minHeight: 420,
    frame: false, backgroundColor: "#0b0b10", show: false,
    minimizable: false,   // see setRolled
    title: "Scene Manager",
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.setMenuBarVisibility(false);
  if (process.env.SM_DEV_URL) win.loadURL(process.env.SM_DEV_URL);
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  win.once("ready-to-show", () => { setOwner(maxHwnd); win.show(); });
  for (const ev of ["minimize", "restore", "maximize", "unmaximize", "hide", "show", "focus", "blur"])
    win.on(ev, () => log("window " + ev + (owned ? " (attached)" : "")));
  const remember = () => {
    if (!rolled && !win.isMaximized() && !win.isMinimized()) { store.window = win.getBounds(); saveStore(); }
  };
  win.on("resize", remember);
  win.on("move", remember);
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e) => e.preventDefault());
}

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
    ipcMain.handle("sm:status", () => ({ connected, ...windowState() }));
    ipcMain.handle("sm:store-get", (_e, key) => store[key]);
    ipcMain.handle("sm:store-set", (_e, key, value) => { store[key] = value; saveStore(); });
    ipcMain.handle("sm:on-top", (_e, on) => { store.onTop = !!on; saveStore(); applyOnTop(); return !!on; });
    ipcMain.handle("sm:attach", (_e, on) => {
      store.attach = !!on; saveStore();
      setOwner(maxHwnd); emit({ event: "window", ...windowState() });
      if (on && connected) attach();
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
        if (win.isMaximized()) { drag = null; return; }
        const b = win.getBounds();
        drag = { dx: p.x - b.x, dy: p.y - b.y, w: b.width, h: b.height };
      } else if (phase === "move" && drag) {
        win.setBounds({ x: p.x - drag.dx, y: p.y - drag.dy, width: drag.w, height: drag.h });   // size passed too: it must not creep on scaled screens
      } else if (phase === "end") drag = null;
    });
    ipcMain.on("sm:win", (_e, what) => {
      log("button " + what);
      if (what === "minimize") setRolled(!rolled);
      else if (what === "maximize") win.isMaximized() ? win.unmaximize() : win.maximize();
      else if (what === "close") win.close();
    });
    createWindow();
    connect();
  });
  app.on("window-all-closed", () => app.quit());
}
