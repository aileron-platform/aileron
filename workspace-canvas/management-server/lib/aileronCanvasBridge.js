const BRIDGE_MARKER = "data-aileron-canvas-bridge";
const BRIDGE_SOURCE = "aileron-canvas-bridge";
const BRIDGE_VERSION = 2;
const BRIDGE_SCRIPT_TAG = `<script src="/__aileron/bridge.js" ${BRIDGE_MARKER}="true"></script>`;

const bridgeSource = `(() => {
  const SOURCE = "${BRIDGE_SOURCE}";
  const VERSION = ${BRIDGE_VERSION};
  const MAX_ELEMENTS = 20;
  const MAX_PREVIEW = 2000;
  const MAX_SKILL_EVENT_BYTES = 32 * 1024;
  const SKILL_EVENT_DEBOUNCE_MS = 200;
  const SKILL_EVENT_TYPE = /^[A-Z][A-Z0-9_]*$/;
  if (window.__aileronCanvasBridgeInstalled) return;
  window.__aileronCanvasBridgeInstalled = true;

  let mode = "default";
  let interactionPaused = false;
  let selected = [];
  let watched = [];
  let dragStart = null;
  let hoverBox = null;
  let selectionBox = null;
  let dragBox = null;
  let lastRoutePath = location.pathname || "/";
  const skillEventTimers = new Map();

  const post = (type, payload = {}) => {
    window.parent?.postMessage({ source: SOURCE, version: VERSION, type, payload }, "*");
  };
  const warn = (message) => console.warn("[aileron-canvas-bridge]", message);
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
  const emitSkillEvent = (eventType, data = {}) => {
    if (!SKILL_EVENT_TYPE.test(String(eventType || ""))) {
      warn("Rejected SKILL_EVENT with invalid eventType");
      return;
    }
    let serialized;
    try {
      serialized = JSON.stringify(data ?? {});
    } catch {
      warn("Rejected SKILL_EVENT with non-serializable data");
      return;
    }
    if (new TextEncoder().encode(serialized).length > MAX_SKILL_EVENT_BYTES) {
      warn("Rejected SKILL_EVENT with payload over 32 KB");
      return;
    }
    if (skillEventTimers.has(eventType)) {
      clearTimeout(skillEventTimers.get(eventType));
    }
    skillEventTimers.set(eventType, setTimeout(() => {
      skillEventTimers.delete(eventType);
      post("SKILL_EVENT", { eventType, data });
    }, SKILL_EVENT_DEBOUNCE_MS));
  };

  window.aileron = window.aileron || {};
  window.aileron.bridge = { emit: emitSkillEvent };
  document.addEventListener("pointermove", (event) => {
    if (mode !== "select" || interactionPaused) return;
    if (dragStart) {
      paintBox(ensureBox("drag"), {
        x: Math.min(dragStart.x, event.clientX),
        y: Math.min(dragStart.y, event.clientY),
        width: Math.abs(event.clientX - dragStart.x),
        height: Math.abs(event.clientY - dragStart.y),
      });
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
})();`;

function getAileronCanvasBridgeSource() {
  return bridgeSource;
}

function injectAileronCanvasBridge(html) {
  if (typeof html !== "string" || html.includes(BRIDGE_MARKER)) return html;
  if (html.includes("</body>")) return html.replace("</body>", `${BRIDGE_SCRIPT_TAG}</body>`);
  return `${html}${BRIDGE_SCRIPT_TAG}`;
}

module.exports = {
  BRIDGE_MARKER,
  BRIDGE_SCRIPT_TAG,
  BRIDGE_SOURCE,
  BRIDGE_VERSION,
  getAileronCanvasBridgeSource,
  injectAileronCanvasBridge,
};
