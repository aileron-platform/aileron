const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const workspaceDir = fs.mkdtempSync(path.join(os.tmpdir(), "aileron-server-workspace-"));
const canvasPort = 43003 + Math.floor(Math.random() * 1000);
process.env.WORKSPACE_DIR = workspaceDir;
process.env.PORT = String(canvasPort);
process.env.NEXT_INTERNAL_PORT = String(canvasPort + 1);

const {
  BRIDGE_MARKER,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  CONTENT_SECURITY_POLICY,
  buildNextjsDevServerConfig,
  detectCanvas,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
  resolveStaticRequest,
  resolveNextjsStartupTimeoutState,
  selectSyncRendererAction,
} = require("./server");

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2));
}

function writeStaticCanvas({ contentDir = "./canvases/demo", title = "Demo" } = {}) {
  const root = path.join(workspaceDir, ".aileron");
  const canvasDir = path.resolve(root, contentDir);
  fs.mkdirSync(canvasDir, { recursive: true });
  fs.writeFileSync(path.join(canvasDir, "index.html"), "<html><body><main>Canvas</main></body></html>");
  writeJson(path.join(root, "canvas.json"), {
    version: 1,
    kind: "static",
    contentDir,
    title,
    owner: { type: "user" },
    routes: [{ path: "/", label: "Home" }],
    defaultPath: "/",
  });
}

function writeNextjsCanvas({ contentDir = "./canvases/next-app", title = "Next App" } = {}) {
  const root = path.join(workspaceDir, ".aileron");
  const canvasDir = path.resolve(root, contentDir);
  fs.mkdirSync(path.join(canvasDir, "app"), { recursive: true });
  fs.writeFileSync(path.join(canvasDir, "package.json"), JSON.stringify({ dependencies: { next: "15.0.0" } }));
  fs.writeFileSync(path.join(canvasDir, "app", "page.tsx"), "export default function Page() { return <main>Next</main>; }");
  writeJson(path.join(root, "canvas.json"), {
    version: 1,
    kind: "nextjs",
    contentDir,
    title,
    owner: { type: "user" },
    routes: [{ path: "/", label: "Home" }],
    defaultPath: "/",
  });
  return canvasDir;
}

test.after(async () => {
  fs.rmSync(workspaceDir, { recursive: true, force: true });
});

test("detectCanvas only uses canvas.json and ignores legacy web-canvas hints", () => {
  fs.rmSync(path.join(workspaceDir, ".aileron"), { recursive: true, force: true });
  fs.mkdirSync(path.join(workspaceDir, "web-canvas", ".next"), { recursive: true });
  fs.writeFileSync(path.join(workspaceDir, "web-canvas", "route.json"), JSON.stringify({ version: 1, type: "html" }));
  fs.writeFileSync(path.join(workspaceDir, "web-canvas", "index.html"), "<html></html>");

  const detection = detectCanvas(workspaceDir);

  assert.equal(detection.type, "default");
  assert.equal(detection.manifestStatus, "missing");
});

test("detectCanvas returns active static manifest metadata", () => {
  writeStaticCanvas({ title: "Static App" });

  const detection = detectCanvas(workspaceDir);

  assert.equal(detection.type, "active");
  assert.equal(detection.kind, "static");
  assert.equal(detection.title, "Static App");
  assert.equal(detection.owner.type, "user");
  assert.equal(detection.manifestStatus, "valid");
  assert.equal(detection.defaultPath, "/");
});

test("detectCanvas rejects invalid static content", () => {
  const root = path.join(workspaceDir, ".aileron");
  const canvasDir = path.join(root, "canvases", "empty");
  fs.mkdirSync(canvasDir, { recursive: true });
  writeJson(path.join(root, "canvas.json"), {
    version: 1,
    kind: "static",
    contentDir: "./canvases/empty",
    title: "Empty",
    owner: { type: "user" },
    routes: [{ path: "/" }],
    defaultPath: "/",
  });

  const detection = detectCanvas(workspaceDir);

  assert.equal(detection.manifestStatus, "invalid");
  assert.equal(detection.errorCode, "STATIC_INDEX_MISSING");
});

test("Next.js dev server config starts from manifest contentDir", () => {
  const canvasDir = writeNextjsCanvas();
  const detection = detectCanvas(workspaceDir);
  const config = buildNextjsDevServerConfig(detection.resolvedContentDir);

  assert.equal(detection.manifestStatus, "valid");
  assert.equal(detection.kind, "nextjs");
  assert.equal(detection.resolvedContentDir, canvasDir);
  assert.equal(config.command, "npx");
  assert.deepEqual(config.args, ["next", "dev", "-p", String(canvasPort + 1)]);
  assert.equal(config.options.cwd, canvasDir);
  assert.doesNotMatch(config.options.cwd, /web-canvas/);
});

test("detectCanvas rejects invalid Next.js content", () => {
  const root = path.join(workspaceDir, ".aileron");
  const canvasDir = path.join(root, "canvases", "not-next");
  fs.mkdirSync(canvasDir, { recursive: true });
  fs.writeFileSync(path.join(canvasDir, "package.json"), JSON.stringify({ dependencies: { react: "19.0.0" } }));
  writeJson(path.join(root, "canvas.json"), {
    version: 1,
    kind: "nextjs",
    contentDir: "./canvases/not-next",
    title: "Invalid Next",
    owner: { type: "user" },
    routes: [{ path: "/" }],
    defaultPath: "/",
  });

  const detection = detectCanvas(workspaceDir);

  assert.equal(detection.manifestStatus, "invalid");
  assert.equal(detection.errorCode, "NEXTJS_PROJECT_INVALID");
});

test("bridge source and HTML injection use the external aileron-canvas-bridge contract", () => {
  const script = getAileronCanvasBridgeSource();
  const injected = injectAileronCanvasBridge("<html><body><main>Canvas</main></body></html>");

  assert.match(script, new RegExp(BRIDGE_SOURCE));
  assert.match(script, new RegExp(`VERSION = ${BRIDGE_VERSION}`));
  assert.match(script, /window\.aileron\.bridge/);
  assert.match(script, /SKILL_EVENT/);
  assert.match(script, /SET_MODE/);
  assert.match(script, /TARGET_SELECTED/);
  assert.match(injected, new RegExp(BRIDGE_MARKER));
  assert.match(injected, /<script src="\/__aileron\/bridge\.js"/);
  assert.doesNotMatch(injected, /aileron-web-canvas-review/);
});

test("selectSyncRendererAction restarts when manifest changes", () => {
  const beforeDetection = {
    type: "active",
    kind: "static",
    manifestStatus: "valid",
    manifestValid: true,
    contentDir: "./A",
    resolvedContentDir: path.join(workspaceDir, ".aileron", "A"),
    title: "A",
    owner: { type: "user" },
    routes: [{ path: "/" }],
    defaultPath: "/",
  };
  const afterDetection = {
    ...beforeDetection,
    contentDir: "./B",
    resolvedContentDir: path.join(workspaceDir, ".aileron", "B"),
  };

  const result = selectSyncRendererAction({
    reset: false,
    beforeState: {
      type: "active",
      kind: "static",
      source: beforeDetection.resolvedContentDir,
      serviceStatus: "running",
      hasRenderer: true,
    },
    beforeDetection,
    afterDetection,
    beforeDependencies: { strategy: "none", signature: null },
    afterDependencies: { strategy: "none", signature: null },
  });

  assert.deepEqual(result, { action: "restarted", reason: "manifest-changed" });
});

test("bridge endpoint source is JavaScript served by management API route", () => {
  const source = getAileronCanvasBridgeSource();

  assert.match(source, /window\.aileron\.bridge/);
  assert.match(CONTENT_SECURITY_POLICY, /script-src 'self' 'unsafe-inline' 'unsafe-eval'/);
  assert.match(CONTENT_SECURITY_POLICY, /style-src 'self' 'unsafe-inline'/);
});

test("Next.js startup timeout preserves an early renderer exit as unhealthy", () => {
  const result = resolveNextjsStartupTimeoutState({
    rendererExited: true,
    runtimeStatus: "unhealthy",
    statusMessage: "Canvas renderer exited with code 1",
  });

  assert.deepEqual(result, {
    preserveExitState: true,
    serviceStatus: "stopped",
    runtimeStatus: "unhealthy",
    statusMessage: "Canvas renderer exited with code 1",
  });
});

test("static request resolver allows contentDir files and rejects traversal", () => {
  writeStaticCanvas();
  const detection = detectCanvas(workspaceDir);

  assert.equal(path.basename(resolveStaticRequest(detection.resolvedContentDir, "/")), "index.html");
  assert.equal(resolveStaticRequest(detection.resolvedContentDir, "/../../etc/passwd"), null);
});

test("static request resolver rejects symlinked directories inside contentDir that resolve outside contentDir", () => {
  writeStaticCanvas();
  const detection = detectCanvas(workspaceDir);
  const outsideDir = path.join(workspaceDir, "outside");
  fs.mkdirSync(outsideDir, { recursive: true });
  fs.writeFileSync(path.join(outsideDir, "secret.txt"), "secret");
  fs.symlinkSync(outsideDir, path.join(detection.resolvedContentDir, "outside-link"), "dir");

  assert.equal(resolveStaticRequest(detection.resolvedContentDir, "/outside-link/secret.txt"), null);
});
