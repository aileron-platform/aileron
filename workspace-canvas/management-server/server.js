/**
 * Canvas container management API.
 *
 * Architecture:
 *   /workspace       source files shared with workspace runtime
 *   /web-canvas      isolated render snapshot
 *   /default-canvas  fallback app
 */

const crypto = require("crypto");
const express = require("express");
const { execSync, spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const app = express();
app.use(express.json());

const API_PORT = parseInt(process.env.API_PORT || "3013", 10);
const CANVAS_PORT = parseInt(process.env.PORT || "3003", 10);
const WORKSPACE_DIR = process.env.WORKSPACE_DIR || "/workspace";
const WEB_CANVAS_DIR = "/web-canvas";
const DEFAULT_CANVAS_DIR = "/default-canvas";
const LOG_LIMIT = 500;

let rendererProcess = null;
let staticServer = null;
let currentSource = null;
let currentType = "default";
let currentRenderer = "default-canvas";
let serviceStatus = "stopped";
let statusMessage = "";
let manifestStatus = "missing";
let lastSyncAt = null;
let lastResetAt = null;
let lastPackageSignature = null;
const logs = [];

function pushLog(scope, message) {
  const entry = {
    ts: new Date().toISOString(),
    scope,
    message: String(message),
  };
  logs.push(entry);
  if (logs.length > LOG_LIMIT) logs.shift();
  const line = `[${scope}] ${entry.message}`;
  if (scope === "error") {
    console.error(line);
  } else {
    console.log(line);
  }
}

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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function hasNextjsProject(dir) {
  const pkgPath = path.join(dir, "package.json");
  if (!fs.existsSync(pkgPath)) return false;
  try {
    const pkg = readJson(pkgPath);
    const deps = { ...pkg.dependencies, ...pkg.devDependencies };
    return Object.prototype.hasOwnProperty.call(deps, "next");
  } catch {
    return false;
  }
}

function hasHtmlFiles(dir) {
  if (!fs.existsSync(dir)) return false;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isFile() && entry.name.endsWith(".html")) return true;
    if (entry.isDirectory() && !entry.name.startsWith(".") && hasHtmlFiles(entryPath)) {
      return true;
    }
  }
  return false;
}

function normalizeRoutePath(routePath) {
  if (!routePath || typeof routePath !== "string") return "/";
  return routePath.startsWith("/") ? routePath : `/${routePath}`;
}

function validateManifest(raw) {
  if (!raw || typeof raw !== "object") {
    throw new Error("route.json must be an object");
  }
  if (raw.version !== 1) {
    throw new Error("route.json version must be 1");
  }
  if (!["html", "nextjs"].includes(raw.type)) {
    throw new Error("route.json type must be html or nextjs");
  }

  const routes = Array.isArray(raw.routes)
    ? raw.routes.map((route) => {
        if (!route || typeof route !== "object") {
          throw new Error("route entries must be objects");
        }
        if (!route.path || typeof route.path !== "string") {
          throw new Error("route.path is required");
        }
        const normalized = {
          path: normalizeRoutePath(route.path),
        };
        if (route.file != null) normalized.file = String(route.file);
        if (route.title != null) normalized.title = String(route.title);
        return normalized;
      })
    : [];

  return {
    version: 1,
    type: raw.type,
    defaultPath: normalizeRoutePath(raw.defaultPath || routes[0]?.path || "/"),
    routes,
  };
}

function loadManifest(dir) {
  const manifestPath = path.join(dir, "route.json");
  if (!fs.existsSync(manifestPath)) return null;
  return validateManifest(readJson(manifestPath));
}

function detectCanvas(dir) {
  try {
    const manifest = loadManifest(dir);
    if (manifest) {
      return {
        type: manifest.type,
        source: "manifest",
        defaultPath: manifest.defaultPath,
        hasManifest: true,
        manifestValid: true,
        manifestStatus: "valid",
        routes: manifest.routes,
      };
    }
  } catch (err) {
    return {
      type: "default",
      source: "manifest",
      defaultPath: "/",
      hasManifest: true,
      manifestValid: false,
      manifestStatus: "invalid",
      error: err.message,
      routes: [],
    };
  }

  if (hasNextjsProject(dir)) {
    return {
      type: "nextjs",
      source: "package",
      defaultPath: "/",
      hasManifest: false,
      manifestValid: true,
      manifestStatus: "missing",
      routes: [],
    };
  }

  if (hasHtmlFiles(dir)) {
    return {
      type: "html",
      source: "html",
      defaultPath: "/",
      hasManifest: false,
      manifestValid: true,
      manifestStatus: "missing",
      routes: [],
    };
  }

  return {
    type: "default",
    source: "default",
    defaultPath: "/",
    hasManifest: false,
    manifestValid: true,
    manifestStatus: "missing",
    routes: [],
  };
}

function cleanupPort(port) {
  try {
    execSync(`/scripts/cleanup-port.sh ${port}`, {
      timeout: 15000,
      stdio: "pipe",
    });
  } catch {
    // Ignore cleanup failures; explicit checks below determine health.
  }
}

function syncToCanvas(sourceDir) {
  pushLog("management", `Syncing ${sourceDir} to ${WEB_CANVAS_DIR}`);
  execSync(
    `rsync -a --delete \
      --exclude='node_modules' \
      --exclude='.next' \
      --exclude='.git' \
      "${sourceDir}/" "${WEB_CANVAS_DIR}/"`,
    {
      timeout: 60000,
      stdio: "pipe",
    }
  );
  execSync(`chown -R developer:developer "${WEB_CANVAS_DIR}"`, {
    timeout: 10000,
    stdio: "pipe",
  });
  lastSyncAt = new Date().toISOString();
}

function packageSignature(dir) {
  const files = ["package.json", "package-lock.json", "npm-shrinkwrap.json"];
  const hash = crypto.createHash("sha256");
  let found = false;
  for (const file of files) {
    const filePath = path.join(dir, file);
    if (fs.existsSync(filePath)) {
      found = true;
      hash.update(file);
      hash.update(fs.readFileSync(filePath));
    }
  }
  return found ? hash.digest("hex") : null;
}

function scanNextjsRoutes(dir) {
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
        walk(path.join(currentDir, entry.name), `${routePath}/${entry.name}`);
      }
    }
  }
  walk(appDir, "");
  return routes;
}

function scanHtmlRoutes(dir) {
  const routes = [];
  function walk(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      const entryPath = path.join(currentDir, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith(".")) {
        walk(entryPath);
      } else if (entry.isFile() && entry.name.endsWith(".html")) {
        const rel = path.relative(dir, entryPath);
        const routePath = rel === "index.html" ? "/" : `/${rel}`;
        routes.push({ path: routePath, file: rel });
      }
    }
  }
  if (fs.existsSync(dir)) walk(dir);
  return routes;
}

function routesForSnapshot() {
  const detection = detectCanvas(WEB_CANVAS_DIR);
  if (detection.routes.length > 0) return detection;
  if (detection.type === "nextjs") {
    detection.routes = scanNextjsRoutes(WEB_CANVAS_DIR);
  } else if (detection.type === "html") {
    detection.routes = scanHtmlRoutes(WEB_CANVAS_DIR);
  } else {
    detection.routes = [{ path: "/" }];
  }
  return detection;
}

async function waitForPortRelease(port, maxWait = 10000) {
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    if (!(await checkPort(port))) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function stopRenderer() {
  serviceStatus = "stopping";
  statusMessage = "Stopping Canvas renderer...";

  if (staticServer) {
    const server = staticServer;
    staticServer = null;
    await new Promise((resolve) => server.close(resolve));
  }

  if (rendererProcess) {
    const proc = rendererProcess;
    const pid = proc.pid;
    rendererProcess = null;
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

  cleanupPort(CANVAS_PORT);
  await waitForPortRelease(CANVAS_PORT);
  serviceStatus = "stopped";
  statusMessage = "Canvas renderer stopped";
}

function assertHtmlRouteFiles(detection) {
  for (const route of detection.routes) {
    if (!route.file) continue;
    const filePath = path.join(WEB_CANVAS_DIR, route.file);
    if (!fs.existsSync(filePath)) {
      throw new Error(`HTML route file not found: ${route.file}`);
    }
  }
}

async function startHtmlRenderer(detection) {
  assertHtmlRouteFiles(detection);
  const htmlRoutes = detection.routes.length > 0 ? detection.routes : scanHtmlRoutes(WEB_CANVAS_DIR);
  const routeMap = new Map(htmlRoutes.filter((r) => r.file).map((r) => [normalizeRoutePath(r.path), r.file]));
  const staticApp = express();

  staticApp.get("*", (req, res, next) => {
    const cleanPath = normalizeRoutePath(req.path);
    const mappedFile = routeMap.get(cleanPath);
    if (mappedFile) {
      res.sendFile(path.join(WEB_CANVAS_DIR, mappedFile));
      return;
    }
    next();
  });
  staticApp.use(express.static(WEB_CANVAS_DIR));
  staticApp.get("*", (_req, res) => {
    const indexPath = path.join(WEB_CANVAS_DIR, "index.html");
    if (fs.existsSync(indexPath)) {
      res.sendFile(indexPath);
      return;
    }
    res.status(404).send("Canvas HTML route not found");
  });

  staticServer = staticApp.listen(CANVAS_PORT, "0.0.0.0");
  currentRenderer = "html-static";
  serviceStatus = "running";
  statusMessage = "Canvas HTML renderer is running";
}

function ensureDependencies(execDir) {
  const nodeModulesPath = path.join(execDir, "node_modules");
  const signature = packageSignature(execDir);
  const needsInstall = !fs.existsSync(nodeModulesPath) || (signature && signature !== lastPackageSignature);
  if (!needsInstall) return;

  statusMessage = "Installing dependencies...";
  pushLog("management", `Running npm install in ${execDir}`);
  execSync("npm install", {
    cwd: execDir,
    timeout: 180000,
    stdio: "pipe",
    uid: 1000,
    gid: 1000,
    env: {
      ...process.env,
      HOME: "/home/developer",
      npm_config_cache: "/tmp/.npm-cache",
    },
  });
  lastPackageSignature = signature;
}

async function startNextjsRenderer(execDir) {
  ensureDependencies(execDir);
  statusMessage = "Starting Canvas Next.js renderer...";
  rendererProcess = spawn("npx", ["next", "dev", "-p", String(CANVAS_PORT)], {
    cwd: execDir,
    uid: 1000,
    gid: 1000,
    detached: true,
    env: {
      ...process.env,
      PORT: String(CANVAS_PORT),
      HOME: "/home/developer",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  rendererProcess.stdout.on("data", (data) => {
    const line = data.toString().trim();
    if (line) pushLog("renderer", line);
    if (line.includes("Ready") || line.includes("ready") || line.includes(`localhost:${CANVAS_PORT}`)) {
      serviceStatus = "running";
      statusMessage = "Canvas Next.js renderer is running";
    }
  });
  rendererProcess.stderr.on("data", (data) => {
    const line = data.toString().trim();
    if (line) pushLog("renderer", line);
  });
  rendererProcess.on("exit", (code) => {
    pushLog("management", `Canvas Next.js renderer exited with code ${code}`);
    rendererProcess = null;
    if (serviceStatus !== "stopping") {
      serviceStatus = "stopped";
      statusMessage = `Canvas renderer exited with code ${code}`;
    }
  });

  currentRenderer = "nextjs-dev";
  const startTime = Date.now();
  while (Date.now() - startTime < 60000) {
    if (await checkPort(CANVAS_PORT)) {
      serviceStatus = "running";
      statusMessage = "Canvas Next.js renderer is running";
      return;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  serviceStatus = "starting";
  statusMessage = "Canvas Next.js renderer is still starting...";
}

async function startRendererFromSnapshot() {
  const detection = detectCanvas(WEB_CANVAS_DIR);
  manifestStatus = detection.manifestStatus;
  if (!detection.manifestValid) {
    currentType = "default";
    currentRenderer = "manifest-error";
    serviceStatus = "manifest_error";
    statusMessage = detection.error || "Invalid route.json";
    return detection;
  }

  currentType = detection.type;
  currentSource = WEB_CANVAS_DIR;
  if (detection.type === "html") {
    await startHtmlRenderer(detection);
  } else if (detection.type === "nextjs") {
    await startNextjsRenderer(WEB_CANVAS_DIR);
  } else {
    currentType = "default";
    currentSource = DEFAULT_CANVAS_DIR;
    await startNextjsRenderer(DEFAULT_CANVAS_DIR);
  }
  return detection;
}

async function syncAndStart({ reset = false } = {}) {
  await stopRenderer();
  serviceStatus = "starting";
  if (reset) {
    pushLog("management", "Resetting Canvas snapshot and caches");
    execSync(`rm -rf "${WEB_CANVAS_DIR}"/* "${WEB_CANVAS_DIR}"/.[!.]* "${WEB_CANVAS_DIR}"/..?*`, {
      stdio: "pipe",
      shell: "/bin/bash",
    });
    lastPackageSignature = null;
    lastResetAt = new Date().toISOString();
  }
  syncToCanvas(WORKSPACE_DIR);
  return startRendererFromSnapshot();
}

app.get("/detect", (_req, res) => {
  const detection = detectCanvas(fs.existsSync(path.join(WEB_CANVAS_DIR, "route.json")) ? WEB_CANVAS_DIR : WORKSPACE_DIR);
  res.json(detection);
});

app.get("/routes", (_req, res) => {
  const detection = routesForSnapshot();
  res.json({
    type: detection.type,
    defaultPath: detection.defaultPath,
    routes: detection.routes,
    total: detection.routes.length,
    source: currentSource,
    scannedAt: new Date().toISOString(),
  });
});

app.get("/health", async (_req, res) => {
  const portAvailable = await checkPort(CANVAS_PORT);
  const processAlive = rendererProcess !== null && !rendererProcess.killed;
  const healthy = portAvailable || staticServer !== null;
  const status = serviceStatus === "manifest_error"
    ? "manifest_error"
    : healthy
      ? "healthy"
      : processAlive
        ? "starting"
        : serviceStatus === "starting"
          ? "starting"
          : "unhealthy";

  res.json({
    status,
    type: currentType,
    renderer: currentRenderer,
    renderer_running: healthy || processAlive,
    port_available: portAvailable,
    manifest_status: manifestStatus,
    message: healthy ? "Canvas is running" : statusMessage || "Canvas is not running",
    source: currentSource,
    last_sync_at: lastSyncAt,
    last_reset_at: lastResetAt,
  });
});

app.get("/status", async (_req, res) => {
  res.json({
    serviceStatus,
    statusMessage,
    type: currentType,
    renderer: currentRenderer,
    portAvailable: await checkPort(CANVAS_PORT),
    currentSource,
    manifestStatus,
    lastSyncAt,
    lastResetAt,
  });
});

app.get("/logs", (_req, res) => {
  res.json({
    logs,
    total: logs.length,
  });
});

app.post("/sync", async (_req, res) => {
  try {
    const detection = await syncAndStart();
    res.json({
      status: "completed",
      type: currentType,
      manifestStatus,
      detection,
      message: statusMessage,
      syncedAt: lastSyncAt,
    });
  } catch (err) {
    serviceStatus = "error";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  }
});

app.post("/reset", async (_req, res) => {
  try {
    const detection = await syncAndStart({ reset: true });
    res.json({
      status: "completed",
      type: currentType,
      manifestStatus,
      detection,
      message: statusMessage,
      resetAt: lastResetAt,
    });
  } catch (err) {
    serviceStatus = "error";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  }
});

app.post("/restart", async (_req, res) => {
  try {
    await stopRenderer();
    await startRendererFromSnapshot();
    res.json({
      status: "completed",
      type: currentType,
      manifestStatus,
      message: statusMessage,
    });
  } catch (err) {
    serviceStatus = "error";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  }
});

app.listen(API_PORT, "0.0.0.0", () => {
  pushLog("management", `Canvas management API listening on port ${API_PORT}`);
  pushLog("management", `Architecture: /workspace -> ${WEB_CANVAS_DIR}`);
});

syncAndStart().catch((err) => {
  serviceStatus = "error";
  statusMessage = err.message;
  pushLog("error", `Auto-start failed: ${err.stack || err.message}`);
});

process.on("SIGTERM", async () => {
  pushLog("management", "Received SIGTERM, shutting down...");
  await stopRenderer();
  process.exit(0);
});

process.on("SIGINT", async () => {
  pushLog("management", "Received SIGINT, shutting down...");
  await stopRenderer();
  process.exit(0);
});
