const assert = require("node:assert/strict");
const http = require("node:http");
const net = require("node:net");
const test = require("node:test");

const { BRIDGE_MARKER, createNextProxyServer } = require("./server");

const WORKSPACE_ID = "e0e4aba0-8442-4851-a9c4-5c45f9e74fb6";
const PREFIX = `/workspaces/${WORKSPACE_ID}/canvas`;
const SECOND_PREFIX = "/workspaces/11111111-2222-4333-8444-555555555555/canvas";

function listen(server) {
  return new Promise((resolve, reject) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
    server.once("error", reject);
  });
}

function close(server) {
  return new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

test("Next proxy scopes default HTML, webpack assets, bridge and redirects per request", async () => {
  const observed = [];
  const upstream = http.createServer((req, res) => {
    observed.push({ path: req.url, prefix: req.headers["x-forwarded-prefix"] });
    if (req.url === "/") {
      res.setHeader("content-type", "text/html; charset=utf-8");
      res.end('<html><head><link href="/_next/static/css/app.css" rel="stylesheet"></head><body><script src="/_next/static/chunks/app.js"></script></body></html>');
      return;
    }
    if (req.url === "/_next/static/chunks/webpack.js") {
      res.setHeader("content-type", "application/javascript; charset=utf-8");
      res.end('self.__webpack_require__.p="/_next/";');
      return;
    }
    if (req.url === "/redirect") {
      res.writeHead(307, { location: "/target" });
      res.end();
      return;
    }
    res.writeHead(404).end();
  });
  const upstreamPort = await listen(upstream);
  const proxy = createNextProxyServer(upstreamPort);
  const proxyPort = await listen(proxy);

  try {
    const headers = { "x-forwarded-prefix": PREFIX };
    const htmlResponse = await fetch(`http://127.0.0.1:${proxyPort}/`, { headers });
    const html = await htmlResponse.text();
    assert.equal(htmlResponse.status, 200);
    assert.match(html, new RegExp(`${PREFIX}/_next/static/css/app\\.css`));
    assert.match(html, new RegExp(`${PREFIX}/_next/static/chunks/app\\.js`));
    assert.match(html, new RegExp(`<script src="${PREFIX}/__aileron/bridge\\.js" ${BRIDGE_MARKER}`));
    assert.doesNotMatch(html, /(?:src|href)="\/(?:_next|__aileron)\//);

    const webpackResponse = await fetch(`http://127.0.0.1:${proxyPort}/_next/static/chunks/webpack.js`, { headers });
    assert.equal(await webpackResponse.text(), `self.__webpack_require__.p="${PREFIX}/_next/";`);

    const bridgeResponse = await fetch(`http://127.0.0.1:${proxyPort}/__aileron/bridge.js`, { headers });
    assert.equal(bridgeResponse.status, 200);
    assert.match(await bridgeResponse.text(), /window\.aileron\.bridge/);

    const redirectResponse = await fetch(`http://127.0.0.1:${proxyPort}/redirect`, {
      headers,
      redirect: "manual",
    });
    assert.equal(redirectResponse.status, 307);
    assert.equal(redirectResponse.headers.get("location"), `${PREFIX}/target`);

    assert.deepEqual(observed, [
      { path: "/", prefix: PREFIX },
      { path: "/_next/static/chunks/webpack.js", prefix: PREFIX },
      { path: "/redirect", prefix: PREFIX },
    ]);
  } finally {
    await close(proxy);
    await close(upstream);
  }
});

test("Next proxy preserves direct access and rejects non-contract prefixes", async () => {
  const upstream = http.createServer((_req, res) => {
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end('<html><body><script src="/_next/app.js"></script></body></html>');
  });
  const upstreamPort = await listen(upstream);
  const proxy = createNextProxyServer(upstreamPort);
  const proxyPort = await listen(proxy);

  try {
    const directResponse = await fetch(`http://127.0.0.1:${proxyPort}/`);
    const directHtml = await directResponse.text();
    assert.match(directHtml, /src="\/_next\/app\.js"/);
    assert.match(directHtml, /src="\/__aileron\/bridge\.js"/);

    const invalidResponse = await fetch(`http://127.0.0.1:${proxyPort}/`, {
      headers: { "x-forwarded-prefix": `${PREFIX}/` },
    });
    assert.equal(invalidResponse.status, 400);
    assert.deepEqual(await invalidResponse.json(), { error: "CANVAS_FORWARDED_PREFIX_INVALID" });
  } finally {
    await close(proxy);
    await close(upstream);
  }
});

test("Next proxy does not expose platform credentials to Workspace code", async () => {
  let observedHeaders;
  const upstream = http.createServer((req, res) => {
    observedHeaders = req.headers;
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(req.headers));
  });
  const upstreamPort = await listen(upstream);
  const proxy = createNextProxyServer(upstreamPort);
  const proxyPort = await listen(proxy);

  try {
    const response = await fetch(`http://127.0.0.1:${proxyPort}/headers`, {
      headers: {
        authorization: "Bearer manager-token",
        cookie: "aileron_session=manager-session; aileron_login_attempt=attempt",
        "proxy-authorization": "Basic c2VjcmV0",
        "x-api-key": "manager-api-key",
        "x-csrf-token": "manager-csrf-token",
        "x-forwarded-prefix": PREFIX,
      },
    });

    assert.equal(response.status, 200);
    for (const name of [
      "authorization",
      "cookie",
      "proxy-authorization",
      "x-api-key",
      "x-csrf-token",
    ]) {
      assert.equal(observedHeaders[name], undefined);
    }
    assert.equal(observedHeaders["x-forwarded-prefix"], PREFIX);
  } finally {
    await close(proxy);
    await close(upstream);
  }
});

test("Next proxy keeps concurrent workspace prefixes isolated", async () => {
  const upstream = http.createServer((_req, res) => {
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end('<html><body><script src="/_next/app.js"></script></body></html>');
  });
  const upstreamPort = await listen(upstream);
  const proxy = createNextProxyServer(upstreamPort);
  const proxyPort = await listen(proxy);

  try {
    const [firstHtml, secondHtml] = await Promise.all([
      fetch(`http://127.0.0.1:${proxyPort}/`, { headers: { "x-forwarded-prefix": PREFIX } }).then((response) => response.text()),
      fetch(`http://127.0.0.1:${proxyPort}/`, { headers: { "x-forwarded-prefix": SECOND_PREFIX } }).then((response) => response.text()),
    ]);
    assert.match(firstHtml, new RegExp(`${PREFIX}/_next/app\\.js`));
    assert.doesNotMatch(firstHtml, new RegExp(SECOND_PREFIX));
    assert.match(secondHtml, new RegExp(`${SECOND_PREFIX}/_next/app\\.js`));
    assert.doesNotMatch(secondHtml, new RegExp(PREFIX));
  } finally {
    await close(proxy);
    await close(upstream);
  }
});

test("Next proxy preserves the stripped request path and forwarded prefix on WebSocket upgrade", async () => {
  let resolveUpgrade;
  const upgradeObserved = new Promise((resolve) => { resolveUpgrade = resolve; });
  const upstream = net.createServer((socket) => {
    socket.once("data", (data) => {
      resolveUpgrade(data.toString("utf8"));
      socket.end("HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n");
    });
  });
  const upstreamPort = await listen(upstream);
  const proxy = createNextProxyServer(upstreamPort);
  const proxyPort = await listen(proxy);
  const client = net.connect(proxyPort, "127.0.0.1");

  try {
    client.write([
      "GET /_next/webpack-hmr?page=%2F HTTP/1.1",
      `Host: 127.0.0.1:${proxyPort}`,
      "Connection: Upgrade",
      "Upgrade: websocket",
      "Authorization: Bearer manager-token",
      "Cookie: aileron_session=manager-session",
      "X-CSRF-Token: manager-csrf-token",
      `X-Forwarded-Prefix: ${PREFIX}`,
      "",
      "",
    ].join("\r\n"));
    const rawUpgrade = await upgradeObserved;
    assert.match(rawUpgrade, /^GET \/_next\/webpack-hmr\?page=%2F HTTP\/1\.1/m);
    assert.match(rawUpgrade.toLowerCase(), new RegExp(`x-forwarded-prefix: ${PREFIX}`));
    assert.doesNotMatch(rawUpgrade.toLowerCase(), /authorization:|cookie:|x-csrf-token:/);
  } finally {
    client.destroy();
    await close(proxy);
    await close(upstream);
  }
});
