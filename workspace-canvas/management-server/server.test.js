const assert = require("node:assert/strict");
const test = require("node:test");

const {
  REVIEW_BRIDGE_MARKER,
  REVIEW_BRIDGE_SOURCE,
  REVIEW_BRIDGE_VERSION,
  buildRsyncCommand,
  canvasReviewBridgeScript,
  injectReviewBridge,
  ownershipModeForSync,
  selectDependencyPreparationAction,
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

test("source sync applies ownership during transfer without full-tree chown command", () => {
  const command = buildRsyncCommand("/workspace", "/web-canvas");

  assert.match(command, /--chown=developer:developer/);
  assert.match(command, /--out-format=/);
  assert.doesNotMatch(command, /chown -R/);
  assert.match(command, /--exclude='node_modules'/);
  assert.match(command, /"\/workspace\/" "\/web-canvas\/"/);
});

test("sync ownership mode reserves recursive ownership for reset recovery paths", () => {
  assert.equal(ownershipModeForSync({ recursiveOwnership: false }), "transfer");
  assert.equal(ownershipModeForSync({ recursiveOwnership: true }), "recursive");
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

test("dependency preparation reuses standard dependencies when signature is unchanged", () => {
  const result = selectDependencyPreparationAction({
    execDir: "/web-canvas",
    nodeModulesExists: true,
    lastSignature: "signature-1",
    signature: "signature-1",
    currentStrategy: "standard",
    strategy: "standard",
  });

  assert.deepEqual(result, { action: "reuse", reason: "signature-unchanged" });
});

test("dependency preparation reuses extended dependencies when signature is unchanged", () => {
  const result = selectDependencyPreparationAction({
    execDir: "/web-canvas",
    nodeModulesExists: true,
    lastSignature: "signature-1",
    signature: "signature-1",
    currentStrategy: "extended",
    strategy: "extended",
  });

  assert.deepEqual(result, { action: "reuse", reason: "signature-unchanged" });
});

test("dependency preparation seeds extended dependencies when signature changes", () => {
  const result = selectDependencyPreparationAction({
    execDir: "/web-canvas",
    nodeModulesExists: true,
    lastSignature: "signature-1",
    signature: "signature-2",
    currentStrategy: "extended",
    strategy: "extended",
  });

  assert.deepEqual(result, { action: "seed-standard-and-install", reason: "extended-dependencies" });
});

test("dependency preparation replaces standard symlinks before custom installs", () => {
  const result = selectDependencyPreparationAction({
    execDir: "/default-canvas",
    nodeModulesExists: true,
    nodeModulesIsSymlink: true,
    lastSignature: "signature-1",
    signature: "signature-2",
    currentStrategy: "standard",
    strategy: "custom",
  });

  assert.deepEqual(result, { action: "replace-symlink-and-install", reason: "custom-dependencies" });
});
