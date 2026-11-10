import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const backendDir = path.join(rootDir, "backend");
const frontendDir = path.join(rootDir, "frontend");

function resolvePython() {
  const winVenv = path.join(backendDir, ".venv", "Scripts", "python.exe");
  const unixVenv = path.join(backendDir, ".venv", "bin", "python");

  if (process.platform === "win32" && fs.existsSync(winVenv)) {
    return winVenv;
  }
  if (fs.existsSync(unixVenv)) {
    return unixVenv;
  }
  return process.platform === "win32" ? "python" : "python3";
}

const pythonExe = resolvePython();
console.log(`==> Starting RelayOps Development Servers...`);
console.log(`==> Python:   ${pythonExe}`);
console.log(`==> API:      http://127.0.0.1:8000 (docs: /api/docs)`);
console.log(`==> Web:      http://127.0.0.1:5173\n`);

const apiProc = spawn(
  pythonExe,
  ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
  {
    cwd: backendDir,
    stdio: "inherit",
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
  }
);

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const webProc = spawn(npmCmd, ["run", "dev"], {
  cwd: frontendDir,
  stdio: "inherit",
  shell: process.platform === "win32",
});

function cleanup() {
  console.log("\n==> Shutting down RelayOps dev servers...");
  try {
    if (process.platform === "win32") {
      if (apiProc.pid) spawn("taskkill", ["/PID", String(apiProc.pid), "/T", "/F"]);
      if (webProc.pid) spawn("taskkill", ["/PID", String(webProc.pid), "/T", "/F"]);
    } else {
      if (apiProc.pid) apiProc.kill("SIGTERM");
      if (webProc.pid) webProc.kill("SIGTERM");
    }
  } catch {
    // Process already terminated
  }
}

process.on("SIGINT", () => {
  cleanup();
  process.exit(0);
});

process.on("SIGTERM", () => {
  cleanup();
  process.exit(0);
});

apiProc.on("exit", (code) => {
  if (code && code !== 0) {
    console.error(`Backend process exited with code ${code}`);
  }
});

webProc.on("exit", (code) => {
  if (code && code !== 0) {
    console.error(`Frontend process exited with code ${code}`);
  }
});
