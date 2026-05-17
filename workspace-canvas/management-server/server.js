/**
 * Canvas container management API.
 *
 * Architecture:
 *   /workspace/.aileron/canvas.json  active canvas manifest
 *   /default-canvas                  fallback app
 */

const crypto = require("crypto");
const express = require("express");
const { execSync, spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

const {
  CanvasManifestError,
  manifestPathForWorkspace,
  normalizeRoutePath,
  readCanvasManifest,
} = require("./lib/canvasManifest");
const {
  BRIDGE_MARKER,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
} = require("./lib/aileronCanvasBridge");

const app = express();
app.use(express.json());

const API_PORT = parseInt(process.env.API_PORT || "3013", 10);
const CANVAS_PORT = parseInt(process.env.PORT || "3003", 10);
const NEXT_INTERNAL_PORT = parseInt(process.env.NEXT_INTERNAL_PORT || String(CANVAS_PORT + 1), 10);
const WORKSPACE_DIR = process.env.WORKSPACE_DIR || "/workspace";
const DEFAULT_CANVAS_DIR = "/default-canvas";
const NEXTJS_TEMPLATE_DIR = process.env.NEXTJS_TEMPLATE_DIR || "/opt/canvas-nextjs-template";
const NPM_CACHE_DIR = process.env.npm_config_cache || process.env.NPM_CONFIG_CACHE || "/home/developer/.npm";
const CONTENT_SECURITY_POLICY = "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' ws: wss:; worker-src 'self' blob:;";
const LOG_LIMIT = 500;

let rendererProcess = null;
let staticServer = null;
let currentManifestSignature = null;
let currentSource = null;
let currentType = "default";
let currentKind = null;
let currentRenderer = "default-canvas";
let serviceStatus = "stopped";
let statusMessage = "";
let manifestStatus = "missing";
let runtimeStatus = "unhealthy";
let lastSyncAt = null;
let lastResetAt = null;
let lastPackageSignature = null;
let currentDependencyStrategy = "none";
let syncInProgress = false;
let lastDependencyPreparationMs = 0;
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

function readPackageManifest(dir) {
  const pkgPath = path.join(dir, "package.json");
  if (!fs.existsSync(pkgPath)) return null;
  return readJson(pkgPath);
}

function mergedDependencies(pkg) {
  return {
    ...(pkg.dependencies || {}),
    ...(pkg.devDependencies || {}),
  };
}

function hasNextjsProject(dir) {
  try {
    const pkg = readPackageManifest(dir);
    if (!pkg) return false;
    const deps = mergedDependencies(pkg);
    return Object.prototype.hasOwnProperty.call(deps, "next");
  } catch {
    return false;
  }
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

function manifestSignature(detection) {
  if (detection.manifestStatus !== "valid") return detection.manifestStatus;
  return crypto
    .createHash("sha256")
    .update(JSON.stringify({
      kind: detection.kind,
      contentDir: detection.contentDir,
      resolvedContentDir: detection.resolvedContentDir,
      title: detection.title,
      owner: detection.owner,
      routes: detection.routes,
      defaultPath: detection.defaultPath,
    }))
    .digest("hex");
}

function detectCanvas(workspaceDir = WORKSPACE_DIR) {
  try {
    const manifest = readCanvasManifest(workspaceDir);
    if (!manifest) {
      return {
        type: "default",
        kind: null,
        source: "default",
        defaultPath: "/",
        hasManifest: false,
        manifestValid: true,
        manifestStatus: "missing",
        runtimeStatus,
        routes: [{ path: "/" }],
      };
    }

    if (manifest.kind === "static" && !fs.existsSync(path.join(manifest.resolvedContentDir, "index.html"))) {
      throw new CanvasManifestError("STATIC_INDEX_MISSING", "kind=static requires contentDir/index.html");
    }
    if (manifest.kind === "nextjs" && !hasNextjsProject(manifest.resolvedContentDir)) {
      throw new CanvasManifestError("NEXTJS_PROJECT_INVALID", "kind=nextjs requires package.json with next dependency");
    }

    const routes = manifest.routes.length > 0
      ? manifest.routes
      : scanNextjsRoutes(manifest.resolvedContentDir);

    return {
      type: "active",
      kind: manifest.kind,
      source: "manifest",
      contentDir: manifest.contentDir,
      resolvedContentDir: manifest.resolvedContentDir,
      title: manifest.title,
      owner: manifest.owner,
      defaultPath: manifest.defaultPath,
      hasManifest: true,
      manifestValid: true,
      manifestStatus: "valid",
      runtimeStatus,
      routes,
    };
  } catch (err) {
    return {
      type: "default",
      kind: null,
      source: "manifest",
      defaultPath: "/",
      hasManifest: true,
      manifestValid: false,
      manifestStatus: "invalid",
      runtimeStatus: "unhealthy",
      error: err.message,
      errorCode: err.code || "INVALID_MANIFEST",
      routes: [{ path: "/" }],
    };
  }
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

function elapsedMs(startedAt) {
  return Number(process.hrtime.bigint() - startedAt) / 1_000_000;
}

function roundTiming(value) {
  return Math.round(value * 1000) / 1000;
}

function dependencySignature(dir, strategy) {
  const files = ["package.json", "package-lock.json", "npm-shrinkwrap.json"];
  const hash = crypto.createHash("sha256");
  let found = false;
  hash.update(`strategy:${strategy}`);
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

function classifyDependencyStrategy(execDir) {
  const templateNodeModules = path.join(NEXTJS_TEMPLATE_DIR, "node_modules");
  let templatePkg;
  let workspacePkg;
  try {
    templatePkg = readPackageManifest(NEXTJS_TEMPLATE_DIR);
    workspacePkg = readPackageManifest(execDir);
  } catch (err) {
    return {
      strategy: "custom",
      reason: `package-read-error:${err.message}`,
      extras: [],
    };
  }

  if (!templatePkg || !workspacePkg || !fs.existsSync(templateNodeModules)) {
    return {
      strategy: "custom",
      reason: "template-or-workspace-missing",
      extras: [],
    };
  }

  const standardDeps = mergedDependencies(templatePkg);
  const workspaceDeps = mergedDependencies(workspacePkg);
  const standardNames = Object.keys(standardDeps);
  const incompatible = standardNames.filter((name) => workspaceDeps[name] !== standardDeps[name]);
  if (incompatible.length > 0) {
    return {
      strategy: "custom",
      reason: `incompatible:${incompatible.join(",")}`,
      extras: [],
    };
  }

  const extras = Object.keys(workspaceDeps).filter((name) => !Object.prototype.hasOwnProperty.call(standardDeps, name));
  return {
    strategy: extras.length === 0 && Object.keys(workspaceDeps).length === standardNames.length ? "standard" : "extended",
    reason: extras.length === 0 ? "standard-contract" : "standard-plus-extra",
    extras,
  };
}

function hasDependencyChanged(before, after) {
  return before.strategy !== after.strategy || before.signature !== after.signature;
}

function dependencySnapshot(dir) {
  if (!dir || !fs.existsSync(dir)) return { strategy: "none", signature: null };
  const classification = classifyDependencyStrategy(dir);
  return {
    strategy: classification.strategy,
    signature: dependencySignature(dir, classification.strategy),
  };
}

function selectSyncRendererAction({ reset, beforeState, beforeDetection, afterDetection, beforeDependencies, afterDependencies }) {
  if (reset) return { action: "restarted", reason: "reset" };
  if (!afterDetection.manifestValid) return { action: "restarted", reason: "manifest-invalid" };
  if (beforeDetection.manifestStatus !== afterDetection.manifestStatus) {
    return { action: "restarted", reason: "manifest-status-changed" };
  }
  if (manifestSignature(beforeDetection) !== manifestSignature(afterDetection)) {
    return { action: "restarted", reason: "manifest-changed" };
  }
  if (beforeState.type !== afterDetection.type || beforeState.kind !== afterDetection.kind) {
    return { action: "restarted", reason: "canvas-kind-changed" };
  }
  if (beforeState.source !== (afterDetection.resolvedContentDir || DEFAULT_CANVAS_DIR)) {
    return { action: "restarted", reason: "renderer-source-mismatch" };
  }
  if (afterDetection.kind === "nextjs" && hasDependencyChanged(beforeDependencies, afterDependencies)) {
    return { action: "restarted", reason: "dependencies-changed" };
  }
  if (!beforeState.hasRenderer || beforeState.serviceStatus !== "running") {
    return { action: "restarted", reason: "renderer-unavailable" };
  }
  return { action: "reused", reason: "manifest-unchanged" };
}

function selectDependencyPreparationAction({
  execDir,
  nodeModulesExists,
  nodeModulesIsSymlink = false,
  lastSignature,
  signature,
  currentStrategy,
  strategy,
}) {
  const needsInstall = !nodeModulesExists
    || !lastSignature
    || (signature && signature !== lastSignature)
    || currentStrategy !== strategy;

  if (!needsInstall) return { action: "reuse", reason: "signature-unchanged" };
  if (strategy === "standard") return { action: "link-standard", reason: "standard-dependencies" };
  if (strategy === "extended") return { action: "seed-standard-and-install", reason: "extended-dependencies" };
  if (nodeModulesIsSymlink) return { action: "replace-symlink-and-install", reason: "custom-dependencies" };
  return { action: "install", reason: "custom-dependencies" };
}

function removeNodeModules(nodeModulesPath) {
  if (!fs.existsSync(nodeModulesPath)) return;
  fs.rmSync(nodeModulesPath, { recursive: true, force: true });
}

function runNpmInstall(execDir) {
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
      npm_config_cache: NPM_CACHE_DIR,
    },
  });
}

function ensureDependencies(execDir) {
  const startedAt = process.hrtime.bigint();
  const nodeModulesPath = path.join(execDir, "node_modules");
  const templateNodeModules = path.join(NEXTJS_TEMPLATE_DIR, "node_modules");
  try {
    const existingNodeModules = fs.existsSync(nodeModulesPath) ? fs.lstatSync(nodeModulesPath) : null;
    const classification = classifyDependencyStrategy(execDir);
    const signature = dependencySignature(execDir, classification.strategy);
    const preparationAction = selectDependencyPreparationAction({
      execDir,
      nodeModulesExists: Boolean(existingNodeModules),
      nodeModulesIsSymlink: existingNodeModules?.isSymbolicLink() === true,
      lastSignature: lastPackageSignature,
      signature,
      currentStrategy: currentDependencyStrategy,
      strategy: classification.strategy,
    });
    if (preparationAction.action === "reuse") {
      pushLog("management", `Dependency strategy ${classification.strategy} unchanged for ${execDir}`);
      return;
    }

    pushLog("management", `Dependency strategy for ${execDir}: ${classification.strategy} (${classification.reason})`);
    currentDependencyStrategy = classification.strategy;

    if (preparationAction.action === "link-standard") {
      removeNodeModules(nodeModulesPath);
      fs.symlinkSync(templateNodeModules, nodeModulesPath, "dir");
      pushLog("management", `Linked standard dependencies from ${templateNodeModules}`);
    } else if (preparationAction.action === "seed-standard-and-install") {
      removeNodeModules(nodeModulesPath);
      statusMessage = "Seeding dependencies...";
      pushLog("management", `Seeding standard dependencies for extended project; extras=${classification.extras.join(",") || "none"}`);
      execSync(`cp -a "${templateNodeModules}" "${nodeModulesPath}"`, {
        timeout: 120000,
        stdio: "pipe",
      });
      execSync(`chown -R developer:developer "${nodeModulesPath}"`, {
        timeout: 30000,
        stdio: "pipe",
      });
      runNpmInstall(execDir);
    } else {
      if (preparationAction.action === "replace-symlink-and-install") removeNodeModules(nodeModulesPath);
      runNpmInstall(execDir);
    }

    lastPackageSignature = signature;
  } finally {
    lastDependencyPreparationMs += elapsedMs(startedAt);
  }
}

function buildNextjsDevServerConfig(execDir) {
  return {
    command: "npx",
    args: ["next", "dev", "-p", String(NEXT_INTERNAL_PORT)],
    options: {
      cwd: execDir,
      uid: 1000,
      gid: 1000,
      detached: true,
      env: {
        ...process.env,
        PORT: String(NEXT_INTERNAL_PORT),
        HOME: "/home/developer",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  };
}

function resolveNextjsStartupTimeoutState({ rendererExited, runtimeStatus: currentRuntimeStatus, statusMessage: currentStatusMessage }) {
  if (rendererExited && currentRuntimeStatus === "unhealthy") {
    return {
      preserveExitState: true,
      serviceStatus: "stopped",
      runtimeStatus: "unhealthy",
      statusMessage: currentStatusMessage,
    };
  }
  return {
    preserveExitState: false,
    serviceStatus: "starting",
    runtimeStatus: "starting",
    statusMessage: "Canvas Next.js renderer is still starting...",
  };
}

function rendererState() {
  return {
    type: currentType,
    kind: currentKind,
    renderer: currentRenderer,
    source: currentSource,
    serviceStatus,
    manifestStatus,
    runtimeStatus,
    hasRenderer: (rendererProcess !== null && !rendererProcess.killed) || staticServer !== null,
  };
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
  runtimeStatus = "unhealthy";
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

function setCanvasHeaders(res) {
  res.setHeader("Content-Security-Policy", CONTENT_SECURITY_POLICY);
}

function sendInjectedHtmlFile(res, filePath) {
  fs.readFile(filePath, "utf8", (err, html) => {
    if (err) {
      res.status(404).send("Canvas HTML route not found");
      return;
    }
    setCanvasHeaders(res);
    res.type("html").send(injectAileronCanvasBridge(html));
  });
}

function resolveStaticRequest(contentDir, requestPath) {
  const relativePath = decodeURIComponent(requestPath.split("?")[0]).replace(/^\/+/, "");
  if (relativePath.includes("..")) return null;
  const requested = path.resolve(contentDir, relativePath || "index.html");
  const relative = path.relative(contentDir, requested);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  if (!fs.existsSync(requested)) return null;
  if (fs.lstatSync(requested).isSymbolicLink()) return null;
  const realContentDir = fs.realpathSync(contentDir);
  const realRequested = fs.realpathSync(requested);
  const realRelative = path.relative(realContentDir, realRequested);
  if (realRelative.startsWith("..") || path.isAbsolute(realRelative)) return null;
  return requested;
}

async function startStaticRenderer(detection) {
  const contentDir = detection.resolvedContentDir;
  const routeMap = new Map(detection.routes.map((route) => [normalizeRoutePath(route.path), route.path === "/" ? "index.html" : route.path.replace(/^\/+/, "")]));
  const staticApp = express();

  staticApp.get("/__aileron/bridge.js", (_req, res) => {
    res.type("application/javascript; charset=utf-8").send(getAileronCanvasBridgeSource());
  });
  staticApp.use((req, res, next) => {
    setCanvasHeaders(res);
    next();
  });
  staticApp.get("*", (req, res, next) => {
    const cleanPath = normalizeRoutePath(req.path);
    const mapped = routeMap.get(cleanPath);
    if (!mapped) {
      next();
      return;
    }
    const requested = resolveStaticRequest(contentDir, mapped);
    if (requested && requested.endsWith(".html")) {
      sendInjectedHtmlFile(res, requested);
      return;
    }
    next();
  });
  staticApp.get("*.html", (req, res, next) => {
    const requested = resolveStaticRequest(contentDir, req.path);
    if (requested) {
      sendInjectedHtmlFile(res, requested);
      return;
    }
    next();
  });
  staticApp.get("*", (req, res, next) => {
    const requested = resolveStaticRequest(contentDir, req.path);
    if (!requested) {
      next();
      return;
    }
    setCanvasHeaders(res);
    res.sendFile(requested);
  });
  staticApp.get("*", (_req, res) => {
    const indexPath = path.join(contentDir, "index.html");
    if (fs.existsSync(indexPath)) {
      sendInjectedHtmlFile(res, indexPath);
      return;
    }
    res.status(404).send("Canvas HTML route not found");
  });

  staticServer = staticApp.listen(CANVAS_PORT, "0.0.0.0");
  currentRenderer = "static";
  currentType = "active";
  currentKind = "static";
  currentSource = contentDir;
  serviceStatus = "running";
  runtimeStatus = "healthy";
  statusMessage = "Canvas static renderer is running";
}

function startNextProxy(targetPort) {
  const server = http.createServer((req, res) => {
    if (req.url === "/__aileron/bridge.js") {
      res.writeHead(200, { "content-type": "application/javascript; charset=utf-8" });
      res.end(getAileronCanvasBridgeSource());
      return;
    }

    const upstreamHeaders = {
      ...req.headers,
      host: `127.0.0.1:${targetPort}`,
      connection: "close",
    };
    delete upstreamHeaders["accept-encoding"];

    const proxyReq = http.request(
      {
        hostname: "127.0.0.1",
        port: targetPort,
        path: req.url,
        method: req.method,
        headers: upstreamHeaders,
      },
      (proxyRes) => {
        const contentType = String(proxyRes.headers["content-type"] || "");
        const responseHeaders = {
          ...proxyRes.headers,
          connection: "close",
          "content-security-policy": CONTENT_SECURITY_POLICY,
        };
        delete responseHeaders["transfer-encoding"];

        if (req.method === "HEAD" || !contentType.includes("text/html")) {
          res.writeHead(proxyRes.statusCode || 200, responseHeaders);
          if (req.method === "HEAD") {
            proxyRes.resume();
            res.end();
            return;
          }
          proxyRes.pipe(res);
          return;
        }

        const chunks = [];
        proxyRes.on("data", (chunk) => chunks.push(chunk));
        proxyRes.on("end", () => {
          const body = Buffer.concat(chunks);
          const html = injectAileronCanvasBridge(body.toString("utf8"));
          delete responseHeaders["content-length"];
          res.writeHead(proxyRes.statusCode || 200, {
            ...responseHeaders,
            "content-type": contentType,
            "content-length": Buffer.byteLength(html),
          });
          res.end(html);
        });
      }
    );
    proxyReq.on("error", (err) => {
      res.statusCode = 502;
      res.end(`Canvas proxy error: ${err.message}`);
    });
    proxyReq.setTimeout(15000, () => {
      proxyReq.destroy(new Error("Canvas proxy upstream timeout"));
    });
    if (["GET", "HEAD", "OPTIONS"].includes(req.method || "")) {
      proxyReq.end();
    } else {
      req.pipe(proxyReq);
    }
  });

  server.on("upgrade", (req, socket, head) => {
    const upstream = net.connect(targetPort, "127.0.0.1", () => {
      upstream.write(
        `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n` +
        Object.entries({ ...req.headers, host: `127.0.0.1:${targetPort}` })
          .map(([key, value]) => `${key}: ${value}`)
          .join("\r\n") +
        "\r\n\r\n"
      );
      if (head.length) upstream.write(head);
      socket.pipe(upstream).pipe(socket);
    });
    upstream.on("error", () => socket.destroy());
  });

  staticServer = server.listen(CANVAS_PORT, "0.0.0.0");
}

async function startNextjsRenderer(execDir, { defaultCanvas = false } = {}) {
  ensureDependencies(execDir);
  statusMessage = "Starting Canvas Next.js renderer...";
  runtimeStatus = "starting";
  const nextConfig = buildNextjsDevServerConfig(execDir);
  rendererProcess = spawn(nextConfig.command, nextConfig.args, nextConfig.options);

  rendererProcess.stdout.on("data", (data) => {
    const line = data.toString().trim();
    if (line) pushLog("renderer", line);
    if (line.includes("Ready") || line.includes("ready") || line.includes(`localhost:${NEXT_INTERNAL_PORT}`)) {
      serviceStatus = "running";
      runtimeStatus = "healthy";
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
      runtimeStatus = "unhealthy";
      statusMessage = `Canvas renderer exited with code ${code}`;
    }
  });

  currentRenderer = "nextjs-dev";
  currentType = defaultCanvas ? "default" : "active";
  currentKind = defaultCanvas ? null : "nextjs";
  currentSource = execDir;
  const startTime = Date.now();
  while (Date.now() - startTime < 60000) {
    if (await checkPort(NEXT_INTERNAL_PORT)) {
      startNextProxy(NEXT_INTERNAL_PORT);
      serviceStatus = "running";
      runtimeStatus = "healthy";
      statusMessage = "Canvas Next.js renderer is running";
      return;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  const timeoutState = resolveNextjsStartupTimeoutState({
    rendererExited: rendererProcess === null,
    runtimeStatus,
    statusMessage,
  });
  serviceStatus = timeoutState.serviceStatus;
  runtimeStatus = timeoutState.runtimeStatus;
  statusMessage = timeoutState.statusMessage;
}

async function startRendererFromDetection(detection) {
  manifestStatus = detection.manifestStatus;
  if (!detection.manifestValid) {
    currentType = "default";
    currentKind = null;
    currentSource = DEFAULT_CANVAS_DIR;
    currentRenderer = "manifest-error";
    serviceStatus = "manifest_error";
    runtimeStatus = "unhealthy";
    statusMessage = detection.error || "Invalid canvas.json";
    return detection;
  }

  if (detection.kind === "static") {
    await startStaticRenderer(detection);
  } else if (detection.kind === "nextjs") {
    await startNextjsRenderer(detection.resolvedContentDir);
  } else {
    currentType = "default";
    currentKind = null;
    currentSource = DEFAULT_CANVAS_DIR;
    await startNextjsRenderer(DEFAULT_CANVAS_DIR, { defaultCanvas: true });
  }
  return detection;
}

async function syncAndStart({ reset = false } = {}) {
  const totalStartedAt = process.hrtime.bigint();
  lastDependencyPreparationMs = 0;
  const beforeState = rendererState();
  const beforeDetection = detectCanvas(WORKSPACE_DIR);
  const beforeDependencies = dependencySnapshot(beforeDetection.resolvedContentDir);

  serviceStatus = "starting";
  runtimeStatus = "starting";
  if (reset) {
    await stopRenderer();
    serviceStatus = "starting";
    runtimeStatus = "starting";
    lastPackageSignature = null;
    lastResetAt = new Date().toISOString();
  }

  const detection = detectCanvas(WORKSPACE_DIR);
  const afterDependencies = dependencySnapshot(detection.resolvedContentDir);
  const rendererStartedAt = process.hrtime.bigint();
  const rendererAction = selectSyncRendererAction({
    reset,
    beforeState,
    beforeDetection,
    afterDetection: detection,
    beforeDependencies,
    afterDependencies,
  });

  if (rendererAction.action === "reused") {
    currentType = detection.type;
    currentKind = detection.kind;
    currentSource = detection.resolvedContentDir || DEFAULT_CANVAS_DIR;
    manifestStatus = detection.manifestStatus;
    runtimeStatus = "healthy";
    serviceStatus = "running";
    statusMessage = "Canvas renderer reused";
    lastSyncAt = new Date().toISOString();
    currentManifestSignature = manifestSignature(detection);
    pushLog("management", `Reused Canvas renderer after sync (${rendererAction.reason})`);
    return {
      detection: { ...detection, runtimeStatus },
      rendererAction,
      syncTimings: {
        dependencyPreparationMs: roundTiming(lastDependencyPreparationMs),
        rendererReconciliationMs: roundTiming(elapsedMs(rendererStartedAt)),
        totalMs: roundTiming(elapsedMs(totalStartedAt)),
      },
    };
  }

  pushLog("management", `Restarting Canvas renderer after sync (${rendererAction.reason})`);
  await stopRenderer();
  serviceStatus = "starting";
  runtimeStatus = "starting";
  const startedDetection = await startRendererFromDetection(detection);
  lastSyncAt = new Date().toISOString();
  currentManifestSignature = manifestSignature(startedDetection);
  return {
    detection: { ...startedDetection, runtimeStatus },
    rendererAction,
    syncTimings: {
      dependencyPreparationMs: roundTiming(lastDependencyPreparationMs),
      rendererReconciliationMs: roundTiming(elapsedMs(rendererStartedAt)),
      totalMs: roundTiming(elapsedMs(totalStartedAt)),
    },
  };
}

function routesForCurrentCanvas() {
  const detection = detectCanvas(WORKSPACE_DIR);
  return { ...detection, runtimeStatus };
}

app.get("/__aileron/bridge.js", (_req, res) => {
  res.type("application/javascript; charset=utf-8").send(getAileronCanvasBridgeSource());
});

app.get("/detect", (_req, res) => {
  res.json({ ...detectCanvas(WORKSPACE_DIR), runtimeStatus });
});

app.get("/routes", (_req, res) => {
  const detection = routesForCurrentCanvas();
  res.json({
    type: detection.type,
    kind: detection.kind,
    contentDir: detection.contentDir,
    title: detection.title,
    owner: detection.owner,
    manifestStatus: detection.manifestStatus,
    runtimeStatus,
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
    kind: currentKind,
    renderer: currentRenderer,
    renderer_running: healthy || processAlive,
    port_available: portAvailable,
    manifest_status: manifestStatus,
    runtime_status: runtimeStatus,
    dependency_strategy: currentDependencyStrategy,
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
    kind: currentKind,
    renderer: currentRenderer,
    portAvailable: await checkPort(CANVAS_PORT),
    currentSource,
    manifestStatus,
    runtimeStatus,
    currentManifestSignature,
    dependencyStrategy: currentDependencyStrategy,
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
  if (syncInProgress) {
    res.status(409).json({ status: "busy", error: "CANVAS_SYNC_IN_PROGRESS" });
    return;
  }
  syncInProgress = true;
  try {
    const { detection, rendererAction, syncTimings } = await syncAndStart();
    res.json({
      status: "completed",
      type: currentType,
      kind: currentKind,
      manifestStatus,
      runtimeStatus,
      detection,
      message: statusMessage,
      syncedAt: lastSyncAt,
      rendererAction: rendererAction.action,
      rendererActionReason: rendererAction.reason,
      syncTimings,
    });
  } catch (err) {
    serviceStatus = "error";
    runtimeStatus = "unhealthy";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  } finally {
    syncInProgress = false;
  }
});

app.post("/reset", async (_req, res) => {
  if (syncInProgress) {
    res.status(409).json({ status: "busy", error: "CANVAS_SYNC_IN_PROGRESS" });
    return;
  }
  syncInProgress = true;
  try {
    const { detection, rendererAction, syncTimings } = await syncAndStart({ reset: true });
    res.json({
      status: "completed",
      type: currentType,
      kind: currentKind,
      manifestStatus,
      runtimeStatus,
      detection,
      message: statusMessage,
      resetAt: lastResetAt,
      rendererAction: rendererAction.action,
      rendererActionReason: rendererAction.reason,
      syncTimings,
    });
  } catch (err) {
    serviceStatus = "error";
    runtimeStatus = "unhealthy";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  } finally {
    syncInProgress = false;
  }
});

app.post("/restart", async (_req, res) => {
  try {
    await stopRenderer();
    await startRendererFromDetection(detectCanvas(WORKSPACE_DIR));
    res.json({
      status: "completed",
      type: currentType,
      kind: currentKind,
      manifestStatus,
      runtimeStatus,
      message: statusMessage,
    });
  } catch (err) {
    serviceStatus = "error";
    runtimeStatus = "unhealthy";
    statusMessage = err.message;
    pushLog("error", err.stack || err.message);
    res.status(500).json({ status: "failed", error: err.message });
  }
});

if (require.main === module) {
  app.listen(API_PORT, "0.0.0.0", () => {
    pushLog("management", `Canvas management API listening on port ${API_PORT}`);
    pushLog("management", `Architecture: ${manifestPathForWorkspace(WORKSPACE_DIR)} -> active canvas`);
  });

  syncAndStart().catch((err) => {
    serviceStatus = "error";
    runtimeStatus = "unhealthy";
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
}

module.exports = {
  BRIDGE_MARKER,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  CONTENT_SECURITY_POLICY,
  app,
  buildNextjsDevServerConfig,
  detectCanvas,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
  resolveNextjsStartupTimeoutState,
  resolveStaticRequest,
  selectDependencyPreparationAction,
  selectSyncRendererAction,
  syncAndStart,
};
