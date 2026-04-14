/**
 * Next.js 容器管理 API
 *
 * 提供健康檢查、重啟、路由掃描等管理功能
 * 供 workspace-runtime 的 PreviewService 遠端呼叫
 *
 * 架構：
 *   /workspace     ← 共享 volume（原始碼來源，與 runtime 共用）
 *   /web-preview   ← 容器內部工作目錄（rsync 原始碼 + 獨立 node_modules/.next）
 *   /default-app   ← 預設空白應用（無 Next.js 專案時使用）
 */

const express = require("express");
const { execSync, spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const app = express();
app.use(express.json());

const API_PORT = parseInt(process.env.API_PORT || "3013", 10);
const NEXTJS_PORT = parseInt(process.env.PORT || "3003", 10);
const WORKSPACE_DIR = process.env.WORKSPACE_DIR || "/workspace";
const WEB_PREVIEW_DIR = "/web-preview";
const DEFAULT_APP_DIR = "/default-app";

/** 當前 Next.js 子進程 */
let nextjsProcess = null;
/** 當前使用的原始碼來源 */
let currentSource = null;
/** 服務狀態 */
let serviceStatus = "stopped";
/** 狀態訊息 */
let statusMessage = "";

// --- 輔助函數 ---

function checkPort(port) {
  return new Promise((resolve) => {
    const sock = new net.Socket();
    sock.setTimeout(1000);
    sock
      .once("connect", () => {
        sock.destroy();
        resolve(true);
      })
      .once("timeout", () => {
        sock.destroy();
        resolve(false);
      })
      .once("error", () => {
        sock.destroy();
        resolve(false);
      })
      .connect(port, "127.0.0.1");
  });
}

function hasNextjsProject(dir) {
  const pkgPath = path.join(dir, "package.json");
  if (!fs.existsSync(pkgPath)) return false;
  try {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
    const deps = { ...pkg.dependencies, ...pkg.devDependencies };
    return "next" in deps;
  } catch {
    return false;
  }
}

function cleanupPort(port) {
  try {
    execSync(`/scripts/cleanup-port.sh ${port}`, {
      timeout: 15000,
      stdio: "pipe",
    });
  } catch {
    // 忽略清理失敗
  }
}

/**
 * 將原始碼從 sourceDir 同步到 /web-preview
 * 排除 node_modules 和 .next（這些在 /web-preview 內獨立管理）
 */
function syncToWebPreview(sourceDir) {
  console.log(`[Management] Syncing ${sourceDir} → ${WEB_PREVIEW_DIR}`);
  try {
    execSync(
      `rsync -a --delete \
        --exclude='node_modules' \
        --exclude='.next' \
        --exclude='.git' \
        "${sourceDir}/" "${WEB_PREVIEW_DIR}/"`,
      {
        timeout: 60000,
        stdio: "pipe",
      }
    );
    // 確保權限正確
    execSync(`chown -R developer:developer "${WEB_PREVIEW_DIR}"`, {
      timeout: 10000,
      stdio: "pipe",
    });
    console.log("[Management] Sync completed");
    return true;
  } catch (err) {
    console.error(`[Management] Sync failed: ${err.message}`);
    return false;
  }
}

function scanRoutes(dir) {
  const routeJsonPath = path.join(dir, "route.json");
  if (fs.existsSync(routeJsonPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(routeJsonPath, "utf-8"));
      return (data.routes || [])
        .filter((r) => r.path)
        .map((r) => ({ path: r.path }));
    } catch {
      return [];
    }
  }

  // 掃描 app/ 目錄下的 page.tsx/page.js
  const appDir = path.join(dir, "app");
  if (!fs.existsSync(appDir)) return [];

  const routes = [];
  function walk(currentDir, routePath) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile() && /^page\.(tsx?|jsx?)$/.test(entry.name)) {
        routes.push({ path: routePath || "/" });
      }
      if (entry.isDirectory() && !entry.name.startsWith("_")) {
        walk(
          path.join(currentDir, entry.name),
          `${routePath}/${entry.name}`
        );
      }
    }
  }
  walk(appDir, "");
  return routes;
}

async function startNextjs(sourceDir) {
  // 停止現有進程
  await stopNextjs();

  serviceStatus = "starting";
  currentSource = sourceDir;

  // 決定 Next.js 實際執行目錄
  let execDir;
  if (sourceDir === DEFAULT_APP_DIR) {
    // 預設應用直接在原地執行（已預裝 node_modules）
    execDir = DEFAULT_APP_DIR;
    statusMessage = `Starting default preview app...`;
    console.log(`[Management] Using default app at ${DEFAULT_APP_DIR}`);
  } else {
    // workspace 專案：rsync 到 /web-preview 後執行
    statusMessage = `Syncing workspace to /web-preview...`;
    console.log(`[Management] Syncing ${sourceDir} → ${WEB_PREVIEW_DIR}`);
    if (!syncToWebPreview(sourceDir)) {
      serviceStatus = "error";
      statusMessage = "Failed to sync workspace to /web-preview";
      return;
    }
    execDir = WEB_PREVIEW_DIR;
  }

  console.log(`[Management] Starting Next.js from ${execDir} on port ${NEXTJS_PORT}`);
  statusMessage = `Starting Next.js from ${execDir}...`;

  // 確保 node_modules 可用
  const nodeModulesPath = path.join(execDir, "node_modules");
  // 若 node_modules 是殘留的 symlink（Turbopack 不支援），先移除
  try {
    const lstat = fs.lstatSync(nodeModulesPath);
    if (lstat.isSymbolicLink()) {
      fs.unlinkSync(nodeModulesPath);
      console.log("[Management] Removed stale node_modules symlink");
    }
  } catch {
    // 不存在，忽略
  }

  if (!fs.existsSync(nodeModulesPath)) {
    statusMessage = "Installing dependencies...";
    console.log(`[Management] Running npm install in ${execDir}...`);
    try {
      execSync("npm install", {
        cwd: execDir,
        timeout: 180000, // 3 分鐘超時
        stdio: "pipe",
        uid: 1000, // developer user
        gid: 1000,
        env: {
          ...process.env,
          HOME: "/home/developer",
          npm_config_cache: "/tmp/.npm-cache", // 避免 /home/developer/.npm cache 權限問題
        },
      });
      console.log("[Management] npm install completed");
    } catch (err) {
      console.error(`[Management] npm install failed: ${err.message}`);
      serviceStatus = "error";
      statusMessage = `npm install failed: ${err.message}`;
      return;
    }
  }

  cleanupPort(NEXTJS_PORT);

  // 啟動 Next.js dev server
  statusMessage = "Starting Next.js dev server...";
  nextjsProcess = spawn("npx", ["next", "dev", "-p", String(NEXTJS_PORT)], {
    cwd: execDir,
    uid: 1000,
    gid: 1000,
    detached: true, // 建立進程群組，方便整組 kill
    env: {
      ...process.env,
      PORT: String(NEXTJS_PORT),
      HOME: "/home/developer",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  nextjsProcess.stdout.on("data", (data) => {
    const line = data.toString().trim();
    if (line) console.log(`[Next.js] ${line}`);
    // 偵測 Next.js 啟動完成
    if (line.includes("Ready") || line.includes("ready") || line.includes(`localhost:${NEXTJS_PORT}`)) {
      serviceStatus = "running";
      statusMessage = "Next.js is running";
    }
  });

  nextjsProcess.stderr.on("data", (data) => {
    const line = data.toString().trim();
    if (line) console.error(`[Next.js] ${line}`);
  });

  nextjsProcess.on("exit", (code) => {
    console.log(`[Management] Next.js process exited with code ${code}`);
    nextjsProcess = null;
    if (serviceStatus !== "stopping") {
      serviceStatus = "stopped";
      statusMessage = `Next.js exited with code ${code}`;
    }
  });

  // 等待端口可連接（最多 60 秒）
  const startTime = Date.now();
  while (Date.now() - startTime < 60000) {
    if (await checkPort(NEXTJS_PORT)) {
      serviceStatus = "running";
      statusMessage = "Next.js is running";
      console.log(`[Management] Next.js started successfully on port ${NEXTJS_PORT}`);
      return;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }

  if (serviceStatus !== "running") {
    serviceStatus = "starting";
    statusMessage = "Next.js is still starting (compilation may take time)...";
  }
}

async function waitForPortRelease(port, maxWait = 10000) {
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    if (!(await checkPort(port))) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function stopNextjs() {
  if (nextjsProcess) {
    serviceStatus = "stopping";
    statusMessage = "Stopping Next.js...";
    console.log("[Management] Stopping Next.js process...");

    const proc = nextjsProcess;
    const pid = proc.pid;
    nextjsProcess = null;

    // Kill 整個進程群組（因為用了 detached: true）
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      try { proc.kill("SIGTERM"); } catch {}
    }

    await new Promise((resolve) => {
      const timeout = setTimeout(() => {
        try { process.kill(-pid, "SIGKILL"); } catch {}
        try { proc.kill("SIGKILL"); } catch {}
        resolve();
      }, 5000);

      proc.once("exit", () => {
        clearTimeout(timeout);
        resolve();
      });
    });
  }
  cleanupPort(NEXTJS_PORT);
  // 等待端口完全釋放
  await waitForPortRelease(NEXTJS_PORT);
  serviceStatus = "stopped";
  statusMessage = "Next.js stopped";
}

// --- API 路由 ---

app.get("/health", async (_req, res) => {
  const portAvailable = await checkPort(NEXTJS_PORT);
  const nextjsRunning = nextjsProcess !== null && !nextjsProcess.killed;

  let status;
  if (portAvailable) {
    status = "healthy";
  } else if (nextjsRunning) {
    status = "starting";
  } else if (serviceStatus === "stopped" && !hasNextjsProject(WORKSPACE_DIR)) {
    status = "standby";
  } else {
    status = serviceStatus === "starting" ? "starting" : "unhealthy";
  }

  res.json({
    status,
    nextjs_running: nextjsRunning,
    port_available: portAvailable,
    message: portAvailable
      ? "Next.js is running"
      : statusMessage || "Next.js is not running",
    source: currentSource,
    workspace_has_nextjs: hasNextjsProject(WORKSPACE_DIR),
  });
});

app.get("/status", async (_req, res) => {
  const portAvailable = await checkPort(NEXTJS_PORT);
  const workspaceHasNextjs = hasNextjsProject(WORKSPACE_DIR);

  res.json({
    serviceStatus,
    statusMessage,
    portAvailable,
    nextjsProcessAlive: nextjsProcess !== null && !nextjsProcess.killed,
    currentSource,
    workspaceHasNextjs,
    defaultAppAvailable: fs.existsSync(path.join(DEFAULT_APP_DIR, "package.json")),
  });
});

app.post("/restart", async (_req, res) => {
  console.log("[Management] Restart requested");

  // 決定使用哪個來源
  const source = hasNextjsProject(WORKSPACE_DIR) ? WORKSPACE_DIR : DEFAULT_APP_DIR;

  res.json({
    status: "accepted",
    message: `Restarting Next.js from ${source}...`,
    source,
  });

  // 非同步啟動（包含 rsync + npm install + start）
  startNextjs(source).catch((err) => {
    console.error(`[Management] Failed to restart: ${err.message}`);
  });
});

app.post("/stop", async (_req, res) => {
  console.log("[Management] Stop requested");
  await stopNextjs();
  res.json({ status: "stopped", message: "Next.js stopped" });
});

app.get("/routes", (_req, res) => {
  // 路由掃描使用實際執行目錄
  const execDir = currentSource === DEFAULT_APP_DIR
    ? DEFAULT_APP_DIR
    : (currentSource ? WEB_PREVIEW_DIR : DEFAULT_APP_DIR);
  const routes = scanRoutes(execDir);
  res.json({
    routes,
    total: routes.length,
    source: currentSource,
    execDir,
    scannedAt: new Date().toISOString(),
  });
});

// --- 啟動 ---

app.listen(API_PORT, "0.0.0.0", () => {
  console.log(`[Management] Management API listening on port ${API_PORT}`);
  console.log(`[Management] Architecture: /workspace (source) → /web-preview (exec) | /default-app (fallback)`);
});

// 自動啟動 Next.js
async function autoStart() {
  const source = hasNextjsProject(WORKSPACE_DIR) ? WORKSPACE_DIR : DEFAULT_APP_DIR;
  console.log(`[Management] Auto-starting Next.js from ${source}`);
  await startNextjs(source);
}

autoStart().catch((err) => {
  console.error(`[Management] Auto-start failed: ${err.message}`);
});

// 優雅關閉
process.on("SIGTERM", async () => {
  console.log("[Management] Received SIGTERM, shutting down...");
  await stopNextjs();
  process.exit(0);
});

process.on("SIGINT", async () => {
  console.log("[Management] Received SIGINT, shutting down...");
  await stopNextjs();
  process.exit(0);
});
