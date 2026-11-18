// Claude inside the Scene Manager app.
//
// Each message runs the Claude Code CLI the user already has installed and signed in (`claude -p`, their own
// account, no API key here). Claude gets only the 3ds Max tools of this project (claude_bridge/mcp_server.py over
// the local bridge): no shell, no file access. The CLI streams JSON lines; they are turned into a few simple events
// for the page: text, tool step, tool result, done.
//
// Tools that delete or render are not pre-approved: the CLI refuses them and reports that in its result, the page
// asks the user, and on "Allow" the conversation resumes with that tool approved for one turn.
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const SERVER = "3dsmax";   // the name CLAUDE.md uses for the tools
// Asked first, every time (matched on the end of the tool name).
const ASK_FIRST = ["delete_setup", "render_setups", "run_python", "run_maxscript", "create_sun"];

const GUIDE = [
  "You are working inside the Scene Manager app for 3ds Max. The user types short requests and you carry them out in",
  "their open 3ds Max scene with the " + SERVER + " tools. Start with scene_info when you do not know the scene yet.",
  "Keep answers short and plain: say what you changed (node or setup, property, old value to new value). No code",
  "unless asked. Deleting, rendering and running scripts need the user's OK: when such a tool is refused, do not retry",
  "and do not work around it. Say in one sentence what you wanted to do; the app then shows the user an Allow button.",
].join(" ");

function createChat({ home, log, emit, getRoot }) {
  let proc = null, session = null, cliPath = null, turn = 0;
  let leaving = null;   // the previous turn's process while it shuts down (it has answered, but still holds the session)

  /** Where the Claude Code CLI is, or null. Looked up once. */
  function findCli() {
    if (cliPath) return cliPath;
    const names = process.platform === "win32" ? ["claude.exe", "claude.cmd", "claude.bat"] : ["claude"];
    const dirs = [path.join(os.homedir(), ".local", "bin"), path.join(os.homedir(), ".claude", "local"),
      ...(process.env.APPDATA ? [path.join(process.env.APPDATA, "npm")] : []),
      ...String(process.env.PATH || "").split(path.delimiter)];
    for (const d of dirs) for (const n of names) {
      const p = path.join(d, n);
      try { if (d && fs.statSync(p).isFile()) return (cliPath = p); } catch (_) { /* next */ }
    }
    if (process.platform === "win32") {   // the app was started by 3ds Max: its PATH can be older than the user's
      try {
        const out = execFileSync("where.exe", ["claude"], { encoding: "utf8", windowsHide: true, timeout: 5000 });
        const hit = out.split(/\r?\n/).map((s) => s.trim()).find((s) => /\.(exe|cmd|bat)$/i.test(s));
        if (hit) return (cliPath = hit);
      } catch (_) { /* not found */ }
    }
    return null;
  }

  /** The 3ds Max tool server, as the project's .mcp.json describes it (the python to use), with absolute paths. */
  function mcpConfigFile(root) {
    let def = { command: "python", args: [] };
    try {
      const own = JSON.parse(fs.readFileSync(path.join(root, ".mcp.json"), "utf8")).mcpServers || {};
      const found = own[SERVER] || Object.values(own).find((s) => (s.args || []).some((a) => String(a).includes("mcp_server.py")));
      if (found && found.command) def = found;
    } catch (_) { /* no .mcp.json: plain python */ }
    const script = path.join(root, "claude_bridge", "mcp_server.py");
    const args = (def.args || []).filter((a) => !String(a).includes("mcp_server.py"));
    const cfg = { mcpServers: { [SERVER]: { type: "stdio", command: def.command, args: [...args, script],
      env: { ...(def.env || {}), SCENE_MANAGER_HOME: home } } } };
    const file = path.join(home, "chat_mcp.json");
    fs.mkdirSync(home, { recursive: true });
    fs.writeFileSync(file, JSON.stringify(cfg, null, 2));
    return file;
  }

  function settings(allowOnce) {
    const ask = ASK_FIRST.filter((t) => !allowOnce.includes(t)).map((t) => `mcp__${SERVER}__${t}`);
    return JSON.stringify({ permissions: { allow: [`mcp__${SERVER}`], ask } });
  }

  const file = (name, text) => { const f = path.join(home, name); fs.writeFileSync(f, text); return f; };
  const quote = (a) => '"' + String(a).replace(/"/g, '\\"') + '"';

  /** Run one turn. `allowOnce`: tool names (short) the user just approved. */
  async function send(text, allowOnce = []) {
    if (proc) return { ok: false, error: "Claude is still working. Stop it first." };
    if (leaving) await leaving;
    const cli = findCli();
    if (!cli) return { ok: false, error: "no-cli" };
    const root = getRoot();
    if (!root || !fs.existsSync(path.join(root, "claude_bridge", "mcp_server.py")))
      return { ok: false, error: "Not connected to 3ds Max yet (the Scene Manager folder is unknown)." };
    const args = ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
      "--mcp-config", mcpConfigFile(root), "--strict-mcp-config",
      "--tools", "",                       // no shell, no files: only the 3ds Max tools
      "--permission-prompts", "none",      // nothing can ask in the background: unapproved tools are refused
      "--settings", file("chat_settings.json", settings(allowOnce)),       // as files: no quoting trouble on Windows
      "--append-system-prompt-file", file("chat_guide.txt", GUIDE)];
    if (session) args.push("--resume", session);
    const mine = ++turn;
    const viaShell = /\.(cmd|bat)$/i.test(cli);   // npm installs a .cmd, which Windows only runs through a shell
    let child;
    try {
      child = viaShell
        ? spawn(quote(cli) + " " + args.map(quote).join(" "), { cwd: root, shell: true, windowsHide: true })
        : spawn(cli, args, { cwd: root, windowsHide: true });
    } catch (e) { return { ok: false, error: String(e.message || e) }; }
    proc = child;
    log("chat: start" + (session ? " (resume)" : "") + (allowOnce.length ? " allow " + allowOnce.join(",") : ""));
    let buf = "", err = "", finished = false;
    const tools = new Map();   // tool_use id -> short name
    const out = (ev) => emit({ event: "chat", turn: mine, ...ev });

    const onLine = (line) => {
      let m; try { m = JSON.parse(line); } catch (_) { return; }
      if (m.session_id && m.type === "system" && m.subtype === "init") {
        session = m.session_id;
        const server = (m.mcp_servers || []).find((s) => s.name === SERVER);
        if (server && server.status !== "connected") out({ kind: "warn", text: "The 3ds Max tools did not start (" + server.status + "). Check that Python and the 'mcp' package are installed: pip install -r claude_bridge/requirements.txt" });
        return;
      }
      if (m.type === "stream_event") {
        const e = m.event || {};
        if (e.type === "content_block_delta" && e.delta && e.delta.type === "text_delta") out({ kind: "text", text: e.delta.text });
        else if (e.type === "message_start") out({ kind: "message" });
        return;
      }
      if (m.type === "assistant" && m.message) {
        for (const c of m.message.content || []) if (c.type === "tool_use") {
          const name = String(c.name).replace(`mcp__${SERVER}__`, "");
          tools.set(c.id, name);
          out({ kind: "tool", id: c.id, name, input: c.input || {} });
        }
        return;
      }
      if (m.type === "user" && m.message) {
        for (const c of Array.isArray(m.message.content) ? m.message.content : []) if (c.type === "tool_result") {
          let text = Array.isArray(c.content) ? c.content.filter((x) => x.type === "text").map((x) => x.text).join("\n") : String(c.content || "");
          out({ kind: "tool-result", id: c.tool_use_id, name: tools.get(c.tool_use_id), error: !!c.is_error, text: text.slice(0, 600) });
        }
        return;
      }
      if (m.type === "result") {
        finished = true;
        if (proc === child) {   // answered: the next message may be sent; this process gets a moment to exit
          proc = null;
          leaving = new Promise((resolve) => {
            const t = setTimeout(() => { try { child.kill(); } catch (_) { /* gone */ } resolve(); }, 4000);
            child.once("close", () => { clearTimeout(t); resolve(); });
          }).then(() => { leaving = null; });
        }
        if (m.session_id) session = m.session_id;
        const denied = (m.permission_denials || []).map((d) => ({ name: String(d.tool_name).replace(`mcp__${SERVER}__`, ""), input: d.tool_input || {} }))
          .filter((d, i, all) => all.findIndex((x) => x.name === d.name && JSON.stringify(x.input) === JSON.stringify(d.input)) === i);
        const text = typeof m.result === "string" ? m.result : "";
        const signedOut = m.is_error && /login|log in|sign in|authenticat|api key|oauth|credential/i.test(text);
        out({ kind: "done", error: !!m.is_error, text: m.is_error ? text : "", denied, signedOut, cost: m.total_cost_usd });
      }
    };

    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      buf += chunk;
      let i;
      while ((i = buf.indexOf("\n")) >= 0) { const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (line) onLine(line); }
    });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (c) => { err = (err + c).slice(-2000); });
    child.on("error", (e) => { if (proc === child) proc = null; out({ kind: "done", error: true, text: "Could not start Claude: " + e.message, denied: [] }); });
    child.on("close", (code) => {
      if (proc === child) proc = null;
      log("chat: end code " + code);
      if (finished || child.stopped) { if (child.stopped) out({ kind: "done", stopped: true, denied: [] }); return; }
      const signedOut = /login|log in|sign in|authenticat|api key|oauth|credential/i.test(err);
      out({ kind: "done", error: true, signedOut, denied: [], text: err.trim().split(/\r?\n/).slice(-3).join("\n") || "Claude stopped unexpectedly (code " + code + ")." });
    });
    child.stdin.on("error", () => {});
    child.stdin.end(text);   // the message goes in on stdin: no quoting problems, any length
    return { ok: true, turn: mine };
  }

  function stop() {
    const child = proc;
    if (!child) return false;
    child.stopped = true;
    try {
      if (process.platform === "win32") spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true });   // the CLI and its tool server
      else child.kill("SIGTERM");
    } catch (_) { /* already gone */ }
    return true;
  }

  /** Opens a terminal with the CLI so the user can sign in (it asks on first start; /login otherwise). */
  function signIn() {
    const cli = findCli();
    if (!cli) return false;
    try {
      if (process.platform === "win32") spawn("cmd.exe", ["/c", "start", "Claude sign in", "cmd.exe", "/k", quote(cli) + " /login"], { detached: true, windowsVerbatimArguments: true, stdio: "ignore" }).unref();
      else spawn("x-terminal-emulator", ["-e", cli, "/login"], { detached: true, stdio: "ignore" }).unref();
      return true;
    } catch (e) { log("chat: sign in " + e.message); return false; }
  }

  return {
    send, stop, signIn,
    reset() { stop(); session = null; return true; },
    status() { return { cli: findCli(), busy: !!proc, session: !!session }; },
  };
}

module.exports = { createChat };
