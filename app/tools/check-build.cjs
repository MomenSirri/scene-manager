// After a Windows build: the native module that lets the window attach to 3ds Max must be in the package.
const fs = require("fs");
const path = require("path");
const f = path.join(__dirname, "..", "release", "win-unpacked", "resources", "app.asar.unpacked", "node_modules", "@koromix", "koffi-win32-x64", "win32_x64", "koffi.node");
if (!fs.existsSync(f)) { console.error("BUILD INCOMPLETE: missing " + f + "\nRun: npm install --force --no-save @koromix/koffi-win32-x64"); process.exit(1); }
console.log("ok: koffi for Windows is in the package");
