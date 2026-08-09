const assert = require("node:assert/strict");
const test = require("node:test");

const {
  ForwardedPrefixError,
  parseForwardedPrefix,
  rewriteCanvasText,
  rewriteLocation,
} = require("./lib/forwardedPrefix");

const WORKSPACE_ID = "e0e4aba0-8442-4851-a9c4-5c45f9e74fb6";
const PREFIX = `/workspaces/${WORKSPACE_ID}/canvas`;

test("parseForwardedPrefix accepts only the canonical workspace Canvas path", () => {
  assert.equal(parseForwardedPrefix(undefined), "");
  assert.equal(parseForwardedPrefix(PREFIX), PREFIX);

  for (const invalid of [
    "/canvas",
    `/workspaces/${WORKSPACE_ID}/canvas/`,
    `/workspaces/${WORKSPACE_ID.toUpperCase()}/canvas`,
    "/workspaces/not-a-uuid/canvas",
    `${PREFIX}/preview`,
    `${PREFIX}, ${PREFIX}`,
  ]) {
    assert.throws(
      () => parseForwardedPrefix(invalid),
      (error) => error instanceof ForwardedPrefixError && error.code === "CANVAS_FORWARDED_PREFIX_INVALID"
    );
  }
});

test("rewriteCanvasText keeps Next HTML and the bridge under the forwarded prefix", () => {
  const html = [
    '<link rel="stylesheet" href="/_next/static/css/app.css">',
    '<script src="/_next/static/chunks/app.js"></script>',
    '<script src="/__aileron/bridge.js"></script>',
    '<img src="/assets/logo.svg">',
  ].join("");

  const rewritten = rewriteCanvasText(html, "text/html; charset=utf-8", PREFIX);

  assert.match(rewritten, new RegExp(`${PREFIX}/_next/static/css/app\\.css`));
  assert.match(rewritten, new RegExp(`${PREFIX}/_next/static/chunks/app\\.js`));
  assert.match(rewritten, new RegExp(`${PREFIX}/__aileron/bridge\\.js`));
  assert.match(rewritten, new RegExp(`${PREFIX}/assets/logo\\.svg`));
  assert.doesNotMatch(rewritten, /(?:src|href)="\/(?:_next|__aileron|assets)\//);
});

test("rewriteCanvasText updates webpack and CSS textual asset references", () => {
  assert.equal(
    rewriteCanvasText('self.__webpack_require__.p="/_next/";', "application/javascript", PREFIX),
    `self.__webpack_require__.p="${PREFIX}/_next/";`
  );
  assert.equal(
    rewriteCanvasText(".hero{background:url('/images/hero.png')}", "text/css", PREFIX),
    `.hero{background:url('${PREFIX}/images/hero.png')}`
  );
  assert.equal(
    rewriteCanvasText('const worker="/assets/render-worker.js";', "application/javascript", PREFIX),
    `const worker="${PREFIX}/assets/render-worker.js";`
  );
  assert.equal(
    rewriteCanvasText('<style>.hero{background:url("/images/hero.png")}</style>', "text/html", PREFIX),
    `<style>.hero{background:url("${PREFIX}/images/hero.png")}</style>`
  );
});

test("rewriteLocation scopes root-relative redirects and preserves direct access", () => {
  assert.equal(rewriteLocation("/login?next=%2F", PREFIX), `${PREFIX}/login?next=%2F`);
  assert.equal(rewriteLocation("https://example.test/login", PREFIX), "https://example.test/login");
  assert.equal(rewriteLocation("/login", ""), "/login");
});
