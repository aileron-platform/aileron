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
const http = require("http");
const net = require("net");
const path = require("path");

const app = express();
app.use(express.json());

const API_PORT = parseInt(process.env.API_PORT || "3013", 10);
const CANVAS_PORT = parseInt(process.env.PORT || "3003", 10);
const NEXT_INTERNAL_PORT = parseInt(process.env.NEXT_INTERNAL_PORT || String(CANVAS_PORT + 1), 10);
const WORKSPACE_DIR = process.env.WORKSPACE_DIR || "/workspace";
const WEB_CANVAS_DIR = "/web-canvas";
const DEFAULT_CANVAS_DIR = "/default-canvas";
const NEXTJS_TEMPLATE_DIR = process.env.NEXTJS_TEMPLATE_DIR || "/opt/canvas-nextjs-template";
const NEXTJS_TEMPLATE_NODE_MODULES = path.join(NEXTJS_TEMPLATE_DIR, "node_modules");
const NPM_CACHE_DIR = process.env.npm_config_cache || process.env.NPM_CONFIG_CACHE || "/home/developer/.npm";
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
let currentDependencyStrategy = "none";
let syncInProgress = false;
const logs = [];

const REVIEW_BRIDGE_MARKER = "data-aileron-web-canvas-review-bridge";
const REVIEW_BRIDGE_SOURCE = "aileron-web-canvas-review";
const REVIEW_BRIDGE_VERSION = 1;
const ENABLE_REVIEW_BRIDGE = process.env.ENABLE_CANVAS_REVIEW_BRIDGE !== "false";

function canvasReviewBridgeScript() {
  return `<script ${REVIEW_BRIDGE_MARKER}="true">
(() => {
  const SOURCE = "${REVIEW_BRIDGE_SOURCE}";
  const VERSION = ${REVIEW_BRIDGE_VERSION};
  const MAX_ELEMENTS = 20;
  const MAX_PREVIEW = 2000;
  if (window.__aileronWebCanvasReviewBridgeInstalled) return;
  window.__aileronWebCanvasReviewBridgeInstalled = true;

  let mode = "default";
  let interactionPaused = false;
  let selected = [];
  let watched = [];
  let dragStart = null;
  let hoverBox = null;
  let selectionBox = null;
  let dragBox = null;
  let lastRoutePath = location.pathname || "/";

  const post = (type, payload = {}) => {
    window.parent?.postMessage({ source: SOURCE, version: VERSION, type, payload }, "*");
  };
  const emitRouteChanged = () => {
    const routePath = location.pathname || "/";
    if (routePath === lastRoutePath) return;
    lastRoutePath = routePath;
    clear();
    post("ROUTE_CHANGED", { routePath });
    measureWatched();
  };
  const announceRoutePath = (routePath) => {
    if (!routePath || routePath === lastRoutePath) return;
    lastRoutePath = routePath;
    clear();
    post("ROUTE_CHANGED", { routePath });
  };
  const clampText = (value) => String(value || "").replace(/\\s+/g, " ").trim().slice(0, MAX_PREVIEW);
  const rectPayload = (rect, coordinateSpace = "viewport") => ({
    x: rect.x,
    y: rect.y,
    width: rect.width,
    height: rect.height,
    coordinateSpace,
  });
  const documentRect = (rect) => rectPayload({
    x: rect.x + window.scrollX,
    y: rect.y + window.scrollY,
    width: rect.width,
    height: rect.height,
  }, "document");
  const cssEscape = (value) => {
    if (window.CSS?.escape) return window.CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\\\$&");
  };
  const isBridgeElement = (element) => element?.closest?.("[data-aileron-review-ui]");
  const selectorFor = (element) => {
    const canvasId = element.getAttribute("data-canvas-id");
    if (canvasId) return { selector: \`[data-canvas-id="\${cssEscape(canvasId)}"]\`, selectorKind: "data-canvas-id" };
    if (element.id) return { selector: \`#\${cssEscape(element.id)}\`, selectorKind: "id" };
    const parts = [];
    let node = element;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (!parent) break;
      const siblings = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
      const nth = siblings.length > 1 ? \`:nth-of-type(\${siblings.indexOf(node) + 1})\` : "";
      parts.unshift(\`\${tag}\${nth}\`);
      const selector = parts.join(" > ");
      try {
        if (document.querySelectorAll(selector).length === 1) return { selector, selectorKind: "css" };
      } catch {}
      node = parent;
    }
    return { selector: xpathFor(element), selectorKind: "xpath" };
  };
  const xpathFor = (element) => {
    const parts = [];
    let node = element;
    while (node && node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      const siblings = node.parentElement ? Array.from(node.parentElement.children).filter((child) => child.tagName === node.tagName) : [];
      const index = siblings.length > 1 ? \`[\${siblings.indexOf(node) + 1}]\` : "";
      parts.unshift(\`\${tag}\${index}\`);
      node = node.parentElement;
    }
    return \`/\${parts.join("/")}\`;
  };
  const elementTarget = (element) => {
    const rect = element.getBoundingClientRect();
    const selector = selectorFor(element);
    return {
      type: "element",
      ...selector,
      tagName: element.tagName.toLowerCase(),
      textPreview: clampText(element.innerText || element.textContent || ""),
      htmlPreview: clampText(element.outerHTML || ""),
      parentHtmlPreview: clampText(element.parentElement?.outerHTML || ""),
      rect: rectPayload(rect),
      documentRect: documentRect(rect),
    };
  };
  const ensureBox = (kind) => {
    let box = kind === "hover" ? hoverBox : kind === "drag" ? dragBox : selectionBox;
    if (box) return box;
    box = document.createElement("div");
    box.dataset.aileronReviewUi = kind;
    box.style.cssText = "position:fixed;z-index:2147483647;pointer-events:none;border:2px solid #2563eb;background:rgba(37,99,235,.08);box-shadow:0 0 0 1px rgba(255,255,255,.8);display:none;";
    if (kind === "hover") box.style.borderStyle = "dashed";
    if (kind === "drag") box.style.background = "rgba(14,165,233,.12)";
    document.documentElement.appendChild(box);
    if (kind === "hover") hoverBox = box;
    else if (kind === "drag") dragBox = box;
    else selectionBox = box;
    return box;
  };
  const paintBox = (box, rect) => {
    box.style.display = rect && rect.width >= 0 && rect.height >= 0 ? "block" : "none";
    if (!rect) return;
    box.style.left = \`\${rect.x}px\`;
    box.style.top = \`\${rect.y}px\`;
    box.style.width = \`\${rect.width}px\`;
    box.style.height = \`\${rect.height}px\`;
  };
  const boundingRect = (targets) => {
    const rects = targets.map((target) => target.rect).filter(Boolean);
    const left = Math.min(...rects.map((rect) => rect.x));
    const top = Math.min(...rects.map((rect) => rect.y));
    const right = Math.max(...rects.map((rect) => rect.x + rect.width));
    const bottom = Math.max(...rects.map((rect) => rect.y + rect.height));
    return { x: left, y: top, width: right - left, height: bottom - top, coordinateSpace: "viewport" };
  };
  const emitSelection = (target) => {
    post("TARGET_SELECTED", { routePath: location.pathname || "/", target });
  };
  const selectElement = (element, event) => {
    const target = elementTarget(element);
    const multi = event.shiftKey || event.metaKey || event.ctrlKey;
    if (!multi) {
      selected = [target];
      paintBox(ensureBox("selection"), target.rect);
      emitSelection(target);
      return;
    }
    const existing = selected.findIndex((item) => item.selector === target.selector);
    if (existing >= 0) selected.splice(existing, 1);
    else if (selected.length < MAX_ELEMENTS) selected.push(target);
    if (selected.length === 0) {
      paintBox(ensureBox("selection"), null);
      post("TARGET_SELECTED", { routePath: location.pathname || "/", target: null });
      return;
    }
    const rect = boundingRect(selected);
    paintBox(ensureBox("selection"), rect);
    emitSelection(selected.length === 1 ? selected[0] : { type: "multi-element", elements: selected, rect });
  };
  const clear = () => {
    selected = [];
    dragStart = null;
    paintBox(ensureBox("hover"), null);
    paintBox(ensureBox("selection"), null);
    paintBox(ensureBox("drag"), null);
  };
  const elementFromEvent = (event) => {
    const element = document.elementFromPoint(event.clientX, event.clientY);
    if (!element || element === document.documentElement || element === document.body || isBridgeElement(element)) return null;
    return element;
  };
  document.addEventListener("pointermove", (event) => {
    if (mode !== "select" || interactionPaused) return;
    if (dragStart) {
      const rect = {
        x: Math.min(dragStart.x, event.clientX),
        y: Math.min(dragStart.y, event.clientY),
        width: Math.abs(event.clientX - dragStart.x),
        height: Math.abs(event.clientY - dragStart.y),
      };
      paintBox(ensureBox("drag"), rect);
      return;
    }
    const element = elementFromEvent(event);
    paintBox(ensureBox("hover"), element ? element.getBoundingClientRect() : null);
  }, true);
  document.addEventListener("pointerdown", (event) => {
    if (mode !== "select" || interactionPaused || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    dragStart = { x: event.clientX, y: event.clientY };
  }, true);
  document.addEventListener("pointerup", (event) => {
    if (mode !== "select" || interactionPaused || !dragStart) return;
    event.preventDefault();
    event.stopPropagation();
    const dx = Math.abs(event.clientX - dragStart.x);
    const dy = Math.abs(event.clientY - dragStart.y);
    const start = dragStart;
    dragStart = null;
    paintBox(ensureBox("drag"), null);
    if (dx > 6 || dy > 6) {
      const rect = {
        x: Math.min(start.x, event.clientX),
        y: Math.min(start.y, event.clientY),
        width: dx,
        height: dy,
        coordinateSpace: "viewport",
      };
      selected = [];
      paintBox(ensureBox("selection"), rect);
      emitSelection({ type: "area", rect, documentRect: { ...rect, x: rect.x + window.scrollX, y: rect.y + window.scrollY, coordinateSpace: "document" } });
      return;
    }
    const element = elementFromEvent(event);
    if (element) selectElement(element, event);
  }, true);
  document.addEventListener("keydown", (event) => {
    if (mode === "select" && event.key === "Escape") clear();
  }, true);
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target?.closest?.("a[href]");
    if (!link || link.target || link.hasAttribute("download")) return;
    let url;
    try {
      url = new URL(link.getAttribute("href"), location.href);
    } catch {
      return;
    }
    if (url.origin !== location.origin) return;
    announceRoutePath(url.pathname || "/");
  }, true);
  const measureWatched = () => {
    if (mode !== "select" || watched.length === 0) return;
    const rects = watched.slice(0, MAX_ELEMENTS).map((item) => {
      try {
        const element = document.querySelector(item.selector);
        if (!element) return { id: item.id, selector: item.selector, resolved: false };
        const rect = element.getBoundingClientRect();
        return { id: item.id, selector: item.selector, resolved: true, rect: rectPayload(rect), documentRect: documentRect(rect) };
      } catch {
        return { id: item.id, selector: item.selector, resolved: false };
      }
    });
    post("TARGET_RECTS", { routePath: location.pathname || "/", rects });
  };
  window.addEventListener("scroll", measureWatched, true);
  window.addEventListener("resize", measureWatched);
  const wrapHistoryMethod = (methodName) => {
    const original = history[methodName];
    if (typeof original !== "function") return;
    history[methodName] = function wrappedHistoryMethod(...args) {
      const result = original.apply(this, args);
      window.setTimeout(emitRouteChanged, 0);
      return result;
    };
  };
  wrapHistoryMethod("pushState");
  wrapHistoryMethod("replaceState");
  window.addEventListener("popstate", () => window.setTimeout(emitRouteChanged, 0));
  window.addEventListener("hashchange", () => window.setTimeout(emitRouteChanged, 0));
  window.addEventListener("message", (event) => {
    const message = event.data;
    if (!message || message.source !== SOURCE || message.version !== VERSION || !message.type) return;
    if (message.type === "SET_MODE") {
      mode = message.payload?.mode === "select" ? "select" : "default";
      if (mode !== "select") clear();
      document.documentElement.style.cursor = mode === "select" && !interactionPaused ? "crosshair" : "";
    } else if (message.type === "SET_INTERACTION_PAUSED") {
      interactionPaused = message.payload?.paused === true;
      dragStart = null;
      paintBox(ensureBox("hover"), null);
      paintBox(ensureBox("drag"), null);
      document.documentElement.style.cursor = mode === "select" && !interactionPaused ? "crosshair" : "";
    } else if (message.type === "CLEAR_SELECTION") {
      clear();
    } else if (message.type === "WATCH_TARGETS") {
      watched = Array.isArray(message.payload?.targets) ? message.payload.targets : [];
      measureWatched();
    }
  });
  post("BRIDGE_READY", { routePath: lastRoutePath });
})();
</script>`;
}

function injectReviewBridge(html) {
  if (!ENABLE_REVIEW_BRIDGE) return html;
  if (typeof html !== "string" || html.includes(REVIEW_BRIDGE_MARKER)) return html;
  const script = canvasReviewBridgeScript();
  if (html.includes("</body>")) return html.replace("</body>", `${script}</body>`);
  return `${html}${script}`;
}

function sendInjectedHtmlFile(res, filePath) {
  fs.readFile(filePath, "utf8", (err, html) => {
    if (err) {
      res.status(404).send("Canvas HTML route not found");
      return;
    }
    res.type("html").send(injectReviewBridge(html));
  });
}

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

function dependencySnapshot(dir) {
  const classification = classifyDependencyStrategy(dir);
  return {
    strategy: classification.strategy,
    signature: dependencySignature(dir, classification.strategy),
  };
}

function hasDependencyChanged(before, after) {
  return before.strategy !== after.strategy || before.signature !== after.signature;
}

function rendererState() {
  return {
    type: currentType,
    renderer: currentRenderer,
    source: currentSource,
    serviceStatus,
    manifestStatus,
    hasRendererProcess: rendererProcess !== null && !rendererProcess.killed,
  };
}

function selectSyncRendererAction({ reset, beforeState, beforeDetection, afterDetection, beforeDependencies, afterDependencies }) {
  if (reset) {
    return { action: "restarted", reason: "reset" };
  }
  if (!afterDetection.manifestValid) {
    return { action: "restarted", reason: "manifest-invalid" };
  }
  if (beforeState.type !== afterDetection.type) {
    return { action: "restarted", reason: "canvas-type-changed" };
  }
  if (beforeDetection.manifestStatus !== afterDetection.manifestStatus) {
    return { action: "restarted", reason: "manifest-status-changed" };
  }
  if (hasDependencyChanged(beforeDependencies, afterDependencies)) {
    return { action: "restarted", reason: "dependencies-changed" };
  }
  if (afterDetection.type !== "nextjs") {
    return { action: "restarted", reason: `${afterDetection.type}-renderer-refresh` };
  }
  if (beforeState.renderer !== "nextjs-dev" || beforeState.source !== WEB_CANVAS_DIR) {
    return { action: "restarted", reason: "renderer-source-mismatch" };
  }
  if (!beforeState.hasRendererProcess || beforeState.serviceStatus !== "running") {
    return { action: "restarted", reason: "renderer-unavailable" };
  }
  return { action: "reused", reason: "nextjs-source-only" };
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

  if (!templatePkg || !workspacePkg || !fs.existsSync(NEXTJS_TEMPLATE_NODE_MODULES)) {
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

function chownDeveloper(targetPath) {
  execSync(`chown -R developer:developer "${targetPath}"`, {
    timeout: 30000,
    stdio: "pipe",
  });
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
      sendInjectedHtmlFile(res, path.join(WEB_CANVAS_DIR, mappedFile));
      return;
    }
    next();
  });
  staticApp.get("*.html", (req, res, next) => {
    const relativePath = req.path.replace(/^\/+/, "");
    const requested = path.resolve(WEB_CANVAS_DIR, relativePath);
    if (fs.existsSync(requested) && requested.startsWith(`${WEB_CANVAS_DIR}${path.sep}`)) {
      sendInjectedHtmlFile(res, requested);
      return;
    }
    next();
  });
  staticApp.use(express.static(WEB_CANVAS_DIR));
  staticApp.get("*", (_req, res) => {
    const indexPath = path.join(WEB_CANVAS_DIR, "index.html");
    if (fs.existsSync(indexPath)) {
      sendInjectedHtmlFile(res, indexPath);
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
  const classification = execDir === WEB_CANVAS_DIR
    ? classifyDependencyStrategy(execDir)
    : { strategy: "custom", reason: "non-web-canvas", extras: [] };
  const signature = dependencySignature(execDir, classification.strategy);
  const needsInstall = !fs.existsSync(nodeModulesPath)
    || !lastPackageSignature
    || (signature && signature !== lastPackageSignature)
    || currentDependencyStrategy !== classification.strategy;
  if (!needsInstall) {
    pushLog("management", `Dependency strategy ${classification.strategy} unchanged for ${execDir}`);
    return;
  }

  pushLog("management", `Dependency strategy for ${execDir}: ${classification.strategy} (${classification.reason})`);
  currentDependencyStrategy = classification.strategy;

  if (execDir === WEB_CANVAS_DIR && classification.strategy === "standard") {
    removeNodeModules(nodeModulesPath);
    fs.symlinkSync(NEXTJS_TEMPLATE_NODE_MODULES, nodeModulesPath, "dir");
    pushLog("management", `Linked standard dependencies from ${NEXTJS_TEMPLATE_NODE_MODULES}`);
  } else if (execDir === WEB_CANVAS_DIR && classification.strategy === "extended") {
    removeNodeModules(nodeModulesPath);
    statusMessage = "Seeding dependencies...";
    pushLog("management", `Seeding standard dependencies for extended project; extras=${classification.extras.join(",") || "none"}`);
    execSync(`cp -a "${NEXTJS_TEMPLATE_NODE_MODULES}" "${nodeModulesPath}"`, {
      timeout: 120000,
      stdio: "pipe",
    });
    chownDeveloper(nodeModulesPath);
    runNpmInstall(execDir);
  } else {
    const existingNodeModules = fs.existsSync(nodeModulesPath) ? fs.lstatSync(nodeModulesPath) : null;
    if (existingNodeModules?.isSymbolicLink()) {
      removeNodeModules(nodeModulesPath);
    }
    runNpmInstall(execDir);
  }

  lastPackageSignature = signature;
}

function startNextProxy(targetPort) {
  const server = http.createServer((req, res) => {
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
          const html = injectReviewBridge(body.toString("utf8"));
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

async function startNextjsRenderer(execDir) {
  ensureDependencies(execDir);
  statusMessage = "Starting Canvas Next.js renderer...";
  rendererProcess = spawn("npx", ["next", "dev", "-p", String(NEXT_INTERNAL_PORT)], {
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
  });

  rendererProcess.stdout.on("data", (data) => {
    const line = data.toString().trim();
    if (line) pushLog("renderer", line);
    if (line.includes("Ready") || line.includes("ready") || line.includes(`localhost:${NEXT_INTERNAL_PORT}`)) {
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
    if (await checkPort(NEXT_INTERNAL_PORT)) {
      startNextProxy(NEXT_INTERNAL_PORT);
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
  const beforeState = rendererState();
  const beforeDetection = detectCanvas(WEB_CANVAS_DIR);
  const beforeDependencies = dependencySnapshot(WEB_CANVAS_DIR);

  serviceStatus = "starting";
  if (reset) {
    await stopRenderer();
    serviceStatus = "starting";
    pushLog("management", "Resetting Canvas snapshot and caches");
    execSync(`rm -rf "${WEB_CANVAS_DIR}"/* "${WEB_CANVAS_DIR}"/.[!.]* "${WEB_CANVAS_DIR}"/..?*`, {
      stdio: "pipe",
      shell: "/bin/bash",
    });
    lastPackageSignature = null;
    lastResetAt = new Date().toISOString();
  }
  syncToCanvas(WORKSPACE_DIR);
  const detection = detectCanvas(WEB_CANVAS_DIR);
  const afterDependencies = dependencySnapshot(WEB_CANVAS_DIR);
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
    currentSource = WEB_CANVAS_DIR;
    manifestStatus = detection.manifestStatus;
    serviceStatus = "running";
    statusMessage = "Canvas Next.js renderer reused";
    pushLog("management", `Reused Canvas renderer after sync (${rendererAction.reason})`);
    return { detection, rendererAction };
  }

  pushLog("management", `Restarting Canvas renderer after sync (${rendererAction.reason})`);
  await stopRenderer();
  serviceStatus = "starting";
  const startedDetection = await startRendererFromSnapshot();
  return { detection: startedDetection, rendererAction };
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
    renderer: currentRenderer,
    portAvailable: await checkPort(CANVAS_PORT),
    currentSource,
    manifestStatus,
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
    const { detection, rendererAction } = await syncAndStart();
    res.json({
      status: "completed",
      type: currentType,
      manifestStatus,
      detection,
      message: statusMessage,
      syncedAt: lastSyncAt,
      rendererAction: rendererAction.action,
      rendererActionReason: rendererAction.reason,
    });
  } catch (err) {
    serviceStatus = "error";
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
    const { detection, rendererAction } = await syncAndStart({ reset: true });
    res.json({
      status: "completed",
      type: currentType,
      manifestStatus,
      detection,
      message: statusMessage,
      resetAt: lastResetAt,
      rendererAction: rendererAction.action,
      rendererActionReason: rendererAction.reason,
    });
  } catch (err) {
    serviceStatus = "error";
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

if (require.main === module) {
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
}

module.exports = {
  REVIEW_BRIDGE_MARKER,
  REVIEW_BRIDGE_SOURCE,
  REVIEW_BRIDGE_VERSION,
  ENABLE_REVIEW_BRIDGE,
  canvasReviewBridgeScript,
  selectSyncRendererAction,
  injectReviewBridge,
};
