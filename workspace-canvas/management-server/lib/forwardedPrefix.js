const CANONICAL_WORKSPACE_CANVAS_PREFIX = /^\/workspaces\/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/canvas$/;

class ForwardedPrefixError extends Error {
  constructor(value) {
    super(`Invalid X-Forwarded-Prefix: ${String(value)}`);
    this.name = "ForwardedPrefixError";
    this.code = "CANVAS_FORWARDED_PREFIX_INVALID";
  }
}

function parseForwardedPrefix(value) {
  if (value === undefined) return "";
  if (typeof value !== "string" || !CANONICAL_WORKSPACE_CANVAS_PREFIX.test(value)) {
    throw new ForwardedPrefixError(value);
  }
  return value;
}

function prefixRootPath(value, forwardedPrefix) {
  if (!forwardedPrefix || !value.startsWith("/") || value.startsWith("//")) return value;
  if (value === forwardedPrefix || value.startsWith(`${forwardedPrefix}/`)) return value;
  return `${forwardedPrefix}${value}`;
}

function rewriteRootNamespaces(value, forwardedPrefix) {
  return value.replace(
    /(^|[^A-Za-z0-9_\/-])(\/(?:_next|__aileron)(?=\/|["'`]))/g,
    (_match, boundary, rootPath) => `${boundary}${forwardedPrefix}${rootPath}`
  );
}

function rewriteQuotedAssetReferences(value, forwardedPrefix) {
  return value.replace(
    /(["'`])(\/(?!\/)[^"'`\r\n]*?\.(?:avif|css|gif|ico|jpe?g|js|map|mjs|png|svg|ttf|webp|woff2?)(?:[?#][^"'`\r\n]*)?)\1/gi,
    (_match, quote, rootPath) => `${quote}${prefixRootPath(rootPath, forwardedPrefix)}${quote}`
  );
}

function rewriteHtml(value, forwardedPrefix) {
  let rewritten = rewriteRootNamespaces(value, forwardedPrefix);
  rewritten = rewritten.replace(
    /(\b(?:src|href|action|poster)\s*=\s*["'])(\/[^"']*)/gi,
    (_match, opening, rootPath) => `${opening}${prefixRootPath(rootPath, forwardedPrefix)}`
  );
  rewritten = rewritten.replace(
    /(\bsrcset\s*=\s*["'])([^"']*)(["'])/gi,
    (_match, opening, candidates, closing) => {
      const scoped = candidates
        .split(",")
        .map((candidate) => candidate.replace(/^(\s*)(\/\S*)/, (_part, space, rootPath) => `${space}${prefixRootPath(rootPath, forwardedPrefix)}`))
        .join(",");
      return `${opening}${scoped}${closing}`;
    }
  );
  return rewriteQuotedAssetReferences(rewriteCss(rewritten, forwardedPrefix), forwardedPrefix);
}

function rewriteCss(value, forwardedPrefix) {
  const rewritten = rewriteRootNamespaces(value, forwardedPrefix);
  return rewritten.replace(
    /(url\(\s*["']?)(\/[^)"']*)/gi,
    (_match, opening, rootPath) => `${opening}${prefixRootPath(rootPath, forwardedPrefix)}`
  );
}

function rewriteCanvasText(value, contentType, forwardedPrefix) {
  if (!forwardedPrefix || typeof value !== "string") return value;
  const normalizedType = String(contentType || "").toLowerCase();
  if (normalizedType.includes("text/html") || normalizedType.includes("application/xhtml+xml")) {
    return rewriteHtml(value, forwardedPrefix);
  }
  if (normalizedType.includes("text/css")) return rewriteCss(value, forwardedPrefix);
  return rewriteQuotedAssetReferences(
    rewriteRootNamespaces(value, forwardedPrefix),
    forwardedPrefix
  );
}

function rewriteLocation(location, forwardedPrefix) {
  if (typeof location !== "string") return location;
  return prefixRootPath(location, forwardedPrefix);
}

module.exports = {
  CANONICAL_WORKSPACE_CANVAS_PREFIX,
  ForwardedPrefixError,
  parseForwardedPrefix,
  rewriteCanvasText,
  rewriteLocation,
};
