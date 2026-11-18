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
  token = info.token;
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

// ---- owned by 3ds Max ---------------------------------------------------------------
// The window is made an "owned" window of the 3ds Max main window (Win32 GWLP_HWNDPARENT). Windows then keeps
// it above Max but not above other programs, hides it while Max is minimized and brings it back with Max.
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
      GetWindow: lib.func("intptr_t GetWindow(intptr_t hWnd, uint32_t uCmd)"),
      IsWindow: lib.func("int IsWindow(intptr_t hWnd)"),
    };
  } catch (e) { console.error("owner:", e.message); }
  return user32;
}
const GWLP_HWNDPARENT = -8, GW_OWNER = 4;
let maxHwnd = 0n, owned = false, rolled = false, fullBounds = null;

function hwndArg(argv) {
  const a = (argv || []).find((x) => String(x).startsWith("--max-hwnd="));
  try { return a ? BigInt(a.split("=")[1]) : 0n; } catch (_) { return 0n; }
}
function ownHwnd() {
  const b = win.getNativeWindowHandle();
  return b.length >= 8 ? b.readBigInt64LE(0) : BigInt(b.readInt32LE(0));
}
/** Attach to (or, with 0, detach from) the 3ds Max main window. Returns true when the window is owned afterwards. */
function setOwner(hwnd) {
  const u = win32();
  if (!win || win.isDestroyed()) return false;
  if (!u) { applyOnTop(); return false; }
  try {
    const target = store.attach === false ? 0n : BigInt(hwnd || 0);
    if (target && !u.IsWindow(target)) return owned;
    const me = ownHwnd();
    u.SetWindowLongPtrW(me, GWLP_HWNDPARENT, target);
    owned = !!target && BigInt(u.GetWindow(me, GW_OWNER)) === target;
  } catch (e) { console.error("owner:", e.message); owned = false; }
  applyOnTop();
  return owned;
}
// Not owned (detached, or attaching failed): float above everything, as before. Owned: only when the pin is on.
function applyOnTop() {
  if (win && !win.isDestroyed()) win.setAlwaysOnTop(owned ? store.onTop === true : store.onTop !== false);
}
async function attach() {   // after every (re)connect: Max tells us its window, we tell Max ours
  if (!win || win.isDestroyed()) return;
  try {
    const me = process.platform === "win32" ? ownHwnd().toString() : "0";
    const r = await call("ui_app_attach", { hwnd: me });
    if (r && r.max_hwnd) maxHwnd = BigInt(r.max_hwnd);
    if (!setOwner(maxHwnd) && store.attach !== false && maxHwnd) {
      const r2 = await call("ui_app_attach", { hwnd: me, from_max: true });   // second way: 3ds Max sets it
      owned = !!(r2 && r2.owned); applyOnTop();
    }
    emit({ event: "window", ...windowState() });
  } catch (_) { /* older Scene Manager code in Max: stay a normal window */ }
}
function windowState() {
  return { owned, rolled, attach: store.attach !== false, onTop: win && !win.isDestroyed() ? win.isAlwaysOnTop() : false };
}

// Minimizing an owned window leaves a tiny bar in a screen corner that is easy to lose, so the minimize button
// rolls the window up to its title bar instead, in place.
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
  win.once("ready-to-show", () => { setOwner(maxHwnd); win.show(); });   // owner first: no taskbar button flashes up
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
    if (h) { maxHwnd = h; setOwner(h); }
    comeToFront();
  });
  app.whenReady().then(() => {
    ipcMain.handle("sm:call", (_e, cmd, args) => call(String(cmd), args || {}));
    ipcMain.handle("sm:status", () => ({ connected, ...windowState() }));
    ipcMain.handle("sm:store-get", (_e, key) => store[key]);
    ipcMain.handle("sm:store-set", (_e, key, value) => { store[key] = value; saveStore(); });
    ipcMain.handle("sm:on-top", (_e, on) => { store.onTop = !!on; saveStore(); win.setAlwaysOnTop(!!on); return !!on; });
    ipcMain.handle("sm:attach", (_e, on) => {
      store.attach = !!on; saveStore();
      if (on) attach(); else { setOwner(0); emit({ event: "window", ...windowState() }); }
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
