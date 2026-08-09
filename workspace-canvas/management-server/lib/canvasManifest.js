const fs = require("fs");
const path = require("path");

const MANIFEST_RELATIVE_PATH = ".aileron/canvas.json";
const MANIFEST_VERSION = 1;
const VALID_KINDS = new Set(["static", "nextjs"]);

class CanvasManifestError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "CanvasManifestError";
    this.code = code;
  }
}

function normalizeRoutePath(routePath) {
  if (!routePath || typeof routePath !== "string") return "/";
  return routePath.startsWith("/") ? routePath : `/${routePath}`;
}

function assertPlainObject(value, field) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CanvasManifestError("INVALID_FIELD", `${field} must be an object`);
  }
}

function assertRequiredString(value, field) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new CanvasManifestError("MISSING_FIELD", `${field} is required`);
  }
  return value;
}

function assertNoTraversal(contentDir) {
  const segments = String(contentDir).split(/[\\/]+/).filter(Boolean);
  if (segments.includes("..")) {
    throw new CanvasManifestError("CONTENT_DIR_TRAVERSAL", "contentDir must not contain traversal segments");
  }
}

function assertUnderWorkspace(targetPath, workspaceDir) {
  const relative = path.relative(workspaceDir, targetPath);
  if (relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))) return;
  throw new CanvasManifestError("CONTENT_DIR_OUTSIDE_WORKSPACE", "contentDir must stay under /workspace");
}

function assertNoSymlink(targetPath, workspaceDir) {
  const relative = path.relative(workspaceDir, targetPath);
  const segments = relative.split(path.sep).filter(Boolean);
  let current = workspaceDir;
  for (const segment of segments) {
    current = path.join(current, segment);
    if (!fs.existsSync(current)) {
      throw new CanvasManifestError("CONTENT_DIR_NOT_FOUND", "contentDir must exist");
    }
    if (fs.lstatSync(current).isSymbolicLink()) {
      throw new CanvasManifestError("CONTENT_DIR_SYMLINK", "contentDir must not include symlinks");
    }
  }
}

function resolveContentDir(contentDir, workspaceDir, manifestDir) {
  assertRequiredString(contentDir, "contentDir");
  assertNoTraversal(contentDir);
  const baseDir = path.isAbsolute(contentDir) ? path.parse(workspaceDir).root : manifestDir;
  const resolved = path.resolve(baseDir, contentDir);
  const workspaceResolved = path.resolve(workspaceDir);
  assertUnderWorkspace(resolved, workspaceResolved);
  assertNoSymlink(resolved, workspaceResolved);
  const stat = fs.statSync(resolved);
  if (!stat.isDirectory()) {
    throw new CanvasManifestError("CONTENT_DIR_NOT_DIRECTORY", "contentDir must be a directory");
  }
  return resolved;
}

function validateOwner(owner) {
  assertPlainObject(owner, "owner");
  if (owner.type != null) {
    throw new CanvasManifestError("INVALID_OWNER_FIELD", "owner.type is not supported");
  }
  const normalized = {};
  if (owner.skillName != null) {
    normalized.skillName = assertRequiredString(owner.skillName, "owner.skillName");
  }
  return normalized;
}

function validateRoutes(rawRoutes, kind) {
  if (rawRoutes == null) {
    if (kind === "static") {
      throw new CanvasManifestError("MISSING_FIELD", "routes is required for static canvas");
    }
    return [];
  }
  if (!Array.isArray(rawRoutes)) {
    throw new CanvasManifestError("INVALID_FIELD", "routes must be an array");
  }
  return rawRoutes.map((route, index) => {
    assertPlainObject(route, `routes[${index}]`);
    const normalized = {
      path: normalizeRoutePath(assertRequiredString(route.path, `routes[${index}].path`)),
    };
    if (route.label != null) normalized.label = String(route.label);
    return normalized;
  });
}

function validateManifest(raw, options) {
  const workspaceDir = options?.workspaceDir || "/workspace";
  const manifestDir = options?.manifestDir || path.join(workspaceDir, ".aileron");

  assertPlainObject(raw, "canvas.json");
  if (raw.version !== MANIFEST_VERSION) {
    throw new CanvasManifestError("INVALID_VERSION", "version must be 1");
  }
  if (!VALID_KINDS.has(raw.kind)) {
    throw new CanvasManifestError("INVALID_KIND", "kind must be static or nextjs");
  }

  const title = assertRequiredString(raw.title, "title");
  const contentDir = assertRequiredString(raw.contentDir, "contentDir");
  const resolvedContentDir = resolveContentDir(contentDir, workspaceDir, manifestDir);
  const owner = validateOwner(raw.owner);
  const routes = validateRoutes(raw.routes, raw.kind);
  const defaultPath = normalizeRoutePath(assertRequiredString(raw.defaultPath, "defaultPath"));

  if (!routes.some((route) => route.path === defaultPath)) {
    throw new CanvasManifestError("DEFAULT_PATH_NOT_IN_ROUTES", "defaultPath must match one routes[].path entry");
  }

  return {
    version: MANIFEST_VERSION,
    kind: raw.kind,
    contentDir,
    resolvedContentDir,
    title,
    owner,
    routes,
    defaultPath,
  };
}

function manifestPathForWorkspace(workspaceDir = "/workspace") {
  return path.join(workspaceDir, MANIFEST_RELATIVE_PATH);
}

function readCanvasManifest(workspaceDir = "/workspace") {
  const manifestPath = manifestPathForWorkspace(workspaceDir);
  if (!fs.existsSync(manifestPath)) return null;
  const raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  return validateManifest(raw, {
    workspaceDir,
    manifestDir: path.dirname(manifestPath),
  });
}

module.exports = {
  CanvasManifestError,
  MANIFEST_RELATIVE_PATH,
  manifestPathForWorkspace,
  normalizeRoutePath,
  readCanvasManifest,
  validateManifest,
};
