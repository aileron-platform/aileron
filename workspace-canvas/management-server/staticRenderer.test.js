const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { BRIDGE_MARKER, createStaticRendererApp } = require("./server");

const WORKSPACE_ID = "e0e4aba0-8442-4851-a9c4-5c45f9e74fb6";
const PREFIX = `/workspaces/${WORKSPACE_ID}/canvas`;

function listen(app) {
  return new Promise((resolve, reject) => {
    const server = app.listen(0, "127.0.0.1", () => resolve(server));
    server.once("error", reject);
  });
}

function close(server) {
  return new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

test("static renderer scopes HTML, bridge and CSS asset references per request", async () => {
  const contentDir = fs.mkdtempSync(path.join(os.tmpdir(), "aileron-static-prefix-"));
  fs.mkdirSync(path.join(contentDir, "assets"));
  fs.writeFileSync(
    path.join(contentDir, "index.html"),
    '<html><head><link href="/assets/app.css" rel="stylesheet"></head><body><img src="/images/logo.svg"></body></html>'
  );
  fs.writeFileSync(path.join(contentDir, "assets", "app.css"), ".hero{background:url('/images/hero.png')}");
  const app = createStaticRendererApp({
    resolvedContentDir: contentDir,
    routes: [{ path: "/" }],
  });
  const server = await listen(app);
  const port = server.address().port;

  try {
    const headers = { "x-forwarded-prefix": PREFIX };
    const html = await (await fetch(`http://127.0.0.1:${port}/`, { headers })).text();
    assert.match(html, new RegExp(`${PREFIX}/assets/app\\.css`));
    assert.match(html, new RegExp(`${PREFIX}/images/logo\\.svg`));
    assert.match(html, new RegExp(`<script src="${PREFIX}/__aileron/bridge\\.js" ${BRIDGE_MARKER}`));
    assert.doesNotMatch(html, /(?:src|href)="\/(?:assets|images|__aileron)\//);

    const css = await (await fetch(`http://127.0.0.1:${port}/assets/app.css`, { headers })).text();
    assert.equal(css, `.hero{background:url('${PREFIX}/images/hero.png')}`);

    const directHtml = await (await fetch(`http://127.0.0.1:${port}/`)).text();
    assert.match(directHtml, /href="\/assets\/app\.css"/);
    assert.match(directHtml, /src="\/__aileron\/bridge\.js"/);

    const invalid = await fetch(`http://127.0.0.1:${port}/`, {
      headers: { "x-forwarded-prefix": "/canvas" },
    });
    assert.equal(invalid.status, 400);
    assert.deepEqual(await invalid.json(), { error: "CANVAS_FORWARDED_PREFIX_INVALID" });
  } finally {
    await close(server);
    fs.rmSync(contentDir, { recursive: true, force: true });
  }
});
