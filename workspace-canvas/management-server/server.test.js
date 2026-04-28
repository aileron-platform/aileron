const assert = require("node:assert/strict");
const test = require("node:test");

const {
  REVIEW_BRIDGE_MARKER,
  REVIEW_BRIDGE_SOURCE,
  REVIEW_BRIDGE_VERSION,
  canvasReviewBridgeScript,
  injectReviewBridge,
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
  assert.match(script, /TARGET_SELECTED/);
  assert.match(script, /TARGET_RECTS/);
});
