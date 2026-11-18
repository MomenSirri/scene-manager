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
  });
  s.on("data", (chunk) => {
    buffer += chunk;
    let i;
    while ((i = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, i); buffer = buffer.slice(i + 1);
      if (!line.trim()) continue;
      let msg; try { msg = JSON.parse(line); } catch (_) { continue; }
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

// ---- window ------------------------------------------------------------------------
function createWindow() {
  const b = store.window || {};
  win = new BrowserWindow({
    width: b.width || 1240, height: b.height || 780, x: b.x, y: b.y,
    minWidth: 620, minHeight: 420,
    frame: false, backgroundColor: "#0b0b10", show: false,
    alwaysOnTop: store.onTop !== false,   // floats above 3ds Max by default, like a tool window
    title: "Scene Manager",
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.setMenuBarVisibility(false);
  if (process.env.SM_DEV_URL) win.loadURL(process.env.SM_DEV_URL);
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  win.once("ready-to-show", () => win.show());
  const remember = () => {
    if (!win.isMaximized() && !win.isMinimized()) { store.window = win.getBounds(); saveStore(); }
  };
  win.on("resize", remember);
  win.on("move", remember);
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e) => e.preventDefault());
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {   // the toolbar button in 3ds Max was pressed again: come to the front
    if (win) { if (win.isMinimized()) win.restore(); win.show(); win.focus(); }
  });
  app.whenReady().then(() => {
    ipcMain.handle("sm:call", (_e, cmd, args) => call(String(cmd), args || {}));
    ipcMain.handle("sm:status", () => ({ connected, onTop: win ? win.isAlwaysOnTop() : false }));
    ipcMain.handle("sm:store-get", (_e, key) => store[key]);
    ipcMain.handle("sm:store-set", (_e, key, value) => { store[key] = value; saveStore(); });
    ipcMain.handle("sm:on-top", (_e, on) => { win.setAlwaysOnTop(on); store.onTop = on; saveStore(); return on; });
    ipcMain.on("sm:win", (_e, what) => {
      if (what === "minimize") win.minimize();
      else if (what === "maximize") win.isMaximized() ? win.unmaximize() : win.maximize();
      else if (what === "close") win.close();
    });
    createWindow();
    connect();
  });
  app.on("window-all-closed", () => app.quit());
}
