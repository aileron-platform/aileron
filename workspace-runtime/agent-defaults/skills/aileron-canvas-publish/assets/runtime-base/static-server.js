"use strict";

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const siteRoot = fs.realpathSync(process.env.CANVAS_SITE_DIR || "/opt/canvas/site");
const port = Number.parseInt(process.env.PORT || "8080", 10);
const host = process.env.CANVAS_HOST || "0.0.0.0";

const mimeTypes = new Map([
  [".avif", "image/avif"],
  [".css", "text/css; charset=utf-8"],
  [".gif", "image/gif"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".jpeg", "image/jpeg"],
  [".jpg", "image/jpeg"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".pdf", "application/pdf"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".webp", "image/webp"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
  [".xml", "application/xml; charset=utf-8"],
]);

function isInsideRoot(candidate) {
  return candidate === siteRoot || candidate.startsWith(`${siteRoot}${path.sep}`);
}

function resolveFile(requestUrl) {
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(new URL(requestUrl, "http://canvas.local").pathname);
  } catch {
    return { status: 400 };
  }
  if (decodedPath.includes("\0")) {
    return { status: 400 };
  }
  const segments = decodedPath.split("/");
  if (segments.includes("..")) {
    return { status: 403 };
  }

  const relativePath = decodedPath.replace(/^\/+/, "");
  const candidates = [];
  if (relativePath === "" || relativePath.endsWith("/")) {
    candidates.push(path.join(relativePath, "index.html"));
  } else {
    candidates.push(relativePath);
    candidates.push(path.join(relativePath, "index.html"));
    if (!path.extname(relativePath)) {
      candidates.push(`${relativePath}.html`);
    }
  }

  for (const relativeCandidate of candidates) {
    const lexicalPath = path.resolve(siteRoot, relativeCandidate);
    if (!isInsideRoot(lexicalPath)) {
      return { status: 403 };
    }
    try {
      const realPath = fs.realpathSync(lexicalPath);
      if (!isInsideRoot(realPath)) {
        return { status: 403 };
      }
      if (fs.statSync(realPath).isFile()) {
        return { status: 200, filePath: realPath };
      }
    } catch (error) {
      if (error.code !== "ENOENT" && error.code !== "ENOTDIR") {
        return { status: 404 };
      }
    }
  }
  return { status: 404 };
}

function isPublicationEndpoint(requestUrl) {
  try {
    return decodeURIComponent(
      new URL(requestUrl, "http://canvas.local").pathname,
    ) === "/_aileron/publication.json";
  } catch {
    return false;
  }
}

function sendStatus(response, status) {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "text/plain; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
  });
  response.end(http.STATUS_CODES[status] || "Error");
}

const server = http.createServer((request, response) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.setHeader("Allow", "GET, HEAD");
    sendStatus(response, 405);
    return;
  }

  const resolved = resolveFile(request.url || "/");
  if (resolved.status !== 200 || !resolved.filePath) {
    sendStatus(response, resolved.status);
    return;
  }

  const extension = path.extname(resolved.filePath).toLowerCase();
  const contentType = mimeTypes.get(extension) || "application/octet-stream";
  const cacheControl = isPublicationEndpoint(request.url || "")
    ? "no-store"
    : extension === ".html"
      ? "no-cache"
      : "public, max-age=3600, must-revalidate";
  const stat = fs.statSync(resolved.filePath);
  response.writeHead(200, {
    "Cache-Control": cacheControl,
    "Content-Length": stat.size,
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
  });
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  fs.createReadStream(resolved.filePath)
    .on("error", () => {
      if (!response.headersSent) {
        sendStatus(response, 500);
      } else {
        response.destroy();
      }
    })
    .pipe(response);
});

server.listen(port, host, () => {
  process.stdout.write(`Canvas static server listening on ${host}:${port}\n`);
});
