// The page gets a small, fixed API. It cannot reach Node or the file system.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sm", {
  call: (cmd, args) => ipcRenderer.invoke("sm:call", cmd, args || {}),
  onEvent: (fn) => {
    const h = (_e, ev) => fn(ev);
    ipcRenderer.on("sm:event", h);
    return () => ipcRenderer.removeListener("sm:event", h);
  },
  chat: (what, text, allow) => ipcRenderer.invoke("sm:chat", what, text, allow),
  status: () => ipcRenderer.invoke("sm:status"),
  store: {
    get: (key) => ipcRenderer.invoke("sm:store-get", key),
    set: (key, value) => ipcRenderer.invoke("sm:store-set", key, value),
  },
  win: {
    minimize: () => ipcRenderer.send("sm:win", "minimize"),
    maximize: () => ipcRenderer.send("sm:win", "maximize"),
    close: () => ipcRenderer.send("sm:win", "close"),
    setOnTop: (on) => ipcRenderer.invoke("sm:on-top", !!on),
    setAttach: (on) => ipcRenderer.invoke("sm:attach", !!on),
    roll: (on) => ipcRenderer.invoke("sm:roll", !!on),
    drag: (phase, x, y) => ipcRenderer.send("sm:drag", phase, x, y),
  },
});
