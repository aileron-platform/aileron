const assert = require("node:assert/strict");
const test = require("node:test");

const {
  BRIDGE_MARKER,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
} = require("./lib/aileronCanvasBridge");

test("bridge source exposes version 2 aileron-canvas-bridge constants", () => {
  const source = getAileronCanvasBridgeSource();

  assert.match(source, new RegExp(BRIDGE_SOURCE));
  assert.match(source, new RegExp(`VERSION = ${BRIDGE_VERSION}`));
  assert.doesNotMatch(source, /aileron-web-canvas-review/);
});

test("bridge source validates SKILL_EVENT event type, size and debounce", () => {
  const source = getAileronCanvasBridgeSource();

  assert.match(source, /\^\[A-Z\]\[A-Z0-9_\]\*\$/);
  assert.match(source, /32 \* 1024/);
  assert.match(source, /SKILL_EVENT_DEBOUNCE_MS = 200/);
  assert.match(source, /skillEventTimers/);
});

test("bridge source provides window.aileron.bridge.emit", () => {
  const source = getAileronCanvasBridgeSource();

  assert.match(source, /window\.aileron\.bridge = \{ emit: emitSkillEvent \}/);
  assert.match(source, /post\("SKILL_EVENT"/);
});

test("injectAileronCanvasBridge injects external script marker before body close", () => {
  const html = "<html><body><main>Canvas</main></body></html>";
  const injected = injectAileronCanvasBridge(html);

  assert.match(injected, new RegExp(BRIDGE_MARKER));
  assert.ok(injected.indexOf(BRIDGE_MARKER) < injected.indexOf("</body>"));
  assert.match(injected, /src="\/__aileron\/bridge\.js"/);
  assert.doesNotMatch(injected, /window\.aileron\.bridge =/);
});

test("injectAileronCanvasBridge is idempotent", () => {
  const html = injectAileronCanvasBridge("<html><body></body></html>");

  assert.equal(injectAileronCanvasBridge(html), html);
});
