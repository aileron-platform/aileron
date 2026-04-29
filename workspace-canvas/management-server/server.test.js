const assert = require("node:assert/strict");
const test = require("node:test");

const {
  REVIEW_BRIDGE_MARKER,
  REVIEW_BRIDGE_SOURCE,
  REVIEW_BRIDGE_VERSION,
  canvasReviewBridgeScript,
  injectReviewBridge,
  selectSyncRendererAction,
} = require("./server");

test("injectReviewBridge injects the review bridge before body close", () => {
  const html = "<html><body><main>Canvas</main></body></html>";
  const injected = injectReviewBridge(html);

  assert.match(injected, new RegExp(REVIEW_BRIDGE_MARKER));
  assert.ok(injected.indexOf(REVIEW_BRIDGE_MARKER) < injected.indexOf("</body>"));
});

test("injectReviewBridge is idempotent", () => {
  const html = injectReviewBridge("<html><body></body></html>");

  assert.equal(injectReviewBridge(html), html);
});

test("review bridge script includes protocol constants and selection commands", () => {
  const script = canvasReviewBridgeScript();

  assert.match(script, new RegExp(REVIEW_BRIDGE_SOURCE));
  assert.match(script, new RegExp(`VERSION = ${REVIEW_BRIDGE_VERSION}`));
  assert.match(script, /SET_MODE/);
  assert.match(script, /SET_INTERACTION_PAUSED/);
  assert.match(script, /CLEAR_SELECTION/);
  assert.match(script, /WATCH_TARGETS/);
  assert.match(script, /ROUTE_CHANGED/);
  assert.match(script, /a\[href\]/);
  assert.match(script, /pushState/);
  assert.match(script, /popstate/);
  assert.match(script, /TARGET_SELECTED/);
  assert.match(script, /TARGET_RECTS/);
});

const nextjsDetection = {
  type: "nextjs",
  manifestStatus: "valid",
  manifestValid: true,
};

const nextjsRendererState = {
  type: "nextjs",
  renderer: "nextjs-dev",
  source: "/web-canvas",
  serviceStatus: "running",
  manifestStatus: "valid",
  hasRendererProcess: true,
};

const dependencyState = {
  strategy: "standard",
  signature: "signature-1",
};

test("selectSyncRendererAction reuses healthy Next.js renderer for source-only sync", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: nextjsRendererState,
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "reused", reason: "nextjs-source-only" });
});

test("selectSyncRendererAction restarts for dependency changes", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: nextjsRendererState,
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: { ...dependencyState, signature: "signature-2" },
  });

  assert.deepEqual(result, { action: "restarted", reason: "dependencies-changed" });
});

test("selectSyncRendererAction restarts for Canvas type changes", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: nextjsRendererState,
    beforeDetection: nextjsDetection,
    afterDetection: { type: "html", manifestStatus: "valid", manifestValid: true },
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "canvas-type-changed" });
});

test("selectSyncRendererAction restarts for manifest validity changes", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: nextjsRendererState,
    beforeDetection: nextjsDetection,
    afterDetection: { type: "default", manifestStatus: "invalid", manifestValid: false },
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "manifest-invalid" });
});

test("selectSyncRendererAction restarts when renderer is unavailable", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: { ...nextjsRendererState, hasRendererProcess: false },
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "renderer-unavailable" });
});

test("selectSyncRendererAction restarts unhealthy renderers", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: { ...nextjsRendererState, serviceStatus: "error" },
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "renderer-unavailable" });
});

test("selectSyncRendererAction restarts renderers serving a different source", () => {
  const result = selectSyncRendererAction({
    reset: false,
    beforeState: { ...nextjsRendererState, source: "/workspace" },
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "renderer-source-mismatch" });
});

test("selectSyncRendererAction restarts reset requests", () => {
  const result = selectSyncRendererAction({
    reset: true,
    beforeState: nextjsRendererState,
    beforeDetection: nextjsDetection,
    afterDetection: nextjsDetection,
    beforeDependencies: dependencyState,
    afterDependencies: dependencyState,
  });

  assert.deepEqual(result, { action: "restarted", reason: "reset" });
});
