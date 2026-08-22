const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");

const {
  BRIDGE_MARKER,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
} = require("./lib/aileronCanvasBridge");

function createBridgeHarness({ pathname, scriptSrc }) {
  const messages = [];
  const events = [];
  const windowListeners = new Map();
  const documentListeners = new Map();
  const classNames = new Set();
  const bodyClassNames = new Set();
  const classList = (values) => ({
    add: (value) => values.add(value),
    remove: (value) => values.delete(value),
    toggle: (value, force) => (force ? values.add(value) : values.delete(value)),
    contains: (value) => values.has(value),
  });
  const document = {
    currentScript: { src: scriptSrc },
    documentElement: { classList: classList(classNames), dataset: {}, style: {} },
    body: { classList: classList(bodyClassNames) },
    addEventListener: (type, listener) => documentListeners.set(type, listener),
  };
  const window = {
    addEventListener: (type, listener) => windowListeners.set(type, listener),
    dispatchEvent: (event) => events.push(event),
    parent: { postMessage: (message) => messages.push(message) },
    setTimeout: (callback) => callback(),
    scrollX: 0,
    scrollY: 0,
  };
  window.window = window;

  vm.runInNewContext(getAileronCanvasBridgeSource(), {
    URL,
    CustomEvent: class CustomEvent {
      constructor(type, options) {
        this.type = type;
        this.detail = options?.detail;
      }
    },
    TextEncoder,
    Map,
    console,
    document,
    history: { pushState() {}, replaceState() {} },
    location: {
      pathname,
      origin: "http://localhost:8082",
      href: `http://localhost:8082${pathname}`,
    },
    setTimeout: (callback) => callback(),
    clearTimeout() {},
    window,
  });

  return { bodyClassNames, classNames, document, events, messages, window, windowListeners };
}

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

test("bridge reports Canvas-local route paths behind the workspace gateway", () => {
  const harness = createBridgeHarness({
    pathname: "/workspaces/workspace-1/canvas/",
    scriptSrc: "http://localhost:8082/workspaces/workspace-1/canvas/__aileron/bridge.js",
  });

  assert.equal(harness.messages.at(-1).type, "BRIDGE_READY");
  assert.equal(harness.messages.at(-1).payload.routePath, "/");
});

test("bridge publishes the current theme without mutating application DOM", () => {
  const harness = createBridgeHarness({
    pathname: "/workspaces/workspace-1/canvas/",
    scriptSrc: "http://localhost:8082/workspaces/workspace-1/canvas/__aileron/bridge.js",
  });

  harness.windowListeners.get("message")({
    data: {
      source: BRIDGE_SOURCE,
      version: BRIDGE_VERSION,
      type: "SET_THEME",
      payload: { theme: "dark" },
    },
  });

  assert.equal(harness.window.aileron.theme, "dark");
  assert.equal(harness.events.at(-1).type, "aileron:themechange");
  assert.equal(harness.events.at(-1).detail.theme, "dark");
  assert.equal(harness.classNames.has("dark"), false);
  assert.equal(harness.bodyClassNames.has("dark"), false);
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
