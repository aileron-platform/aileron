"use strict";

const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");

const siteRoot = process.env.CANVAS_SITE_DIR || "/opt/canvas/site";
const upstreamPort = 3000;
const port = Number.parseInt(process.env.PORT || "8080", 10);
const host = process.env.CANVAS_HOST || "0.0.0.0";

function isPublicationEndpoint(requestUrl) {
  try {
    return decodeURIComponent(
      new URL(requestUrl, "http://canvas.local").pathname,
    ) === "/_aileron/publication.json";
  } catch {
    return false;
  }
}

const child = spawn(process.execPath, [path.join(siteRoot, "server.js")], {
  cwd: siteRoot,
  env: {
    ...process.env,
    HOSTNAME: "127.0.0.1",
    PORT: String(upstreamPort),
  },
  stdio: "inherit",
});

const server = http.createServer((request, response) => {
  const upstream = http.request(
    {
      hostname: "127.0.0.1",
      port: upstreamPort,
      method: request.method,
      path: request.url,
      headers: {
        ...request.headers,
        host: `127.0.0.1:${upstreamPort}`,
      },
    },
    (upstreamResponse) => {
      const headers = { ...upstreamResponse.headers };
      if (isPublicationEndpoint(request.url || "")) {
        headers["cache-control"] = "no-store";
        delete headers.etag;
        delete headers.expires;
      }
      response.writeHead(upstreamResponse.statusCode || 502, headers);
      upstreamResponse.pipe(response);
    },
  );
  upstream.on("error", () => {
    if (!response.headersSent) {
      response.writeHead(502, {
        "Cache-Control": "no-store",
        "Content-Type": "text/plain; charset=utf-8",
      });
    }
    response.end("upstream unavailable");
  });
  request.pipe(upstream);
});

function shutdown() {
  server.close(() => child.kill("SIGTERM"));
  child.kill("SIGTERM");
}

child.on("exit", (code, signal) => {
  if (code !== 0 && signal !== "SIGTERM") {
    process.exit(code || 1);
  }
});
process.once("SIGTERM", shutdown);
process.once("SIGINT", shutdown);

server.listen(port, host, () => {
  process.stdout.write(`Canvas Next proxy listening on ${host}:${port}\n`);
});
