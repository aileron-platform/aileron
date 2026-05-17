const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { readCanvasManifest, validateManifest } = require("./lib/canvasManifest");

function makeWorkspace() {
  const workspaceDir = fs.mkdtempSync(path.join(os.tmpdir(), "aileron-manifest-"));
  const manifestDir = path.join(workspaceDir, ".aileron");
  const contentDir = path.join(manifestDir, "canvases", "demo");
  fs.mkdirSync(contentDir, { recursive: true });
  fs.writeFileSync(path.join(contentDir, "index.html"), "<html></html>");
  return { workspaceDir, manifestDir, contentDir };
}

function validManifest(overrides = {}) {
  return {
    version: 1,
    kind: "static",
    contentDir: "./canvases/demo",
    title: "Demo Canvas",
    owner: { type: "skill", skillName: "ppt-image-first" },
    routes: [{ path: "/", label: "Home" }],
    defaultPath: "/",
    ...overrides,
  };
}

test("valid manifest is normalized", () => {
  const { workspaceDir, manifestDir, contentDir } = makeWorkspace();
  const manifest = validateManifest(validManifest(), { workspaceDir, manifestDir });

  assert.equal(manifest.version, 1);
  assert.equal(manifest.kind, "static");
  assert.equal(manifest.resolvedContentDir, contentDir);
  assert.equal(manifest.owner.type, "skill");
  assert.equal(manifest.owner.skillName, "ppt-image-first");
  assert.deepEqual(manifest.routes, [{ path: "/", label: "Home" }]);
});

test("readCanvasManifest returns null when canvas.json is missing", () => {
  const { workspaceDir } = makeWorkspace();

  assert.equal(readCanvasManifest(workspaceDir), null);
});

test("missing required field is rejected", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();
  const raw = validManifest();
  delete raw.title;

  assert.throws(
    () => validateManifest(raw, { workspaceDir, manifestDir }),
    /title is required/,
  );
});

test("invalid kind is rejected", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();

  assert.throws(
    () => validateManifest(validManifest({ kind: "html" }), { workspaceDir, manifestDir }),
    /kind must be static or nextjs/,
  );
});

test("contentDir traversal is rejected", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();

  assert.throws(
    () => validateManifest(validManifest({ contentDir: "./canvases/../../outside" }), { workspaceDir, manifestDir }),
    /contentDir must not contain traversal/,
  );
});

test("contentDir outside workspace is rejected", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();

  assert.throws(
    () => validateManifest(validManifest({ contentDir: "/etc" }), { workspaceDir, manifestDir }),
    /contentDir must stay under \/workspace/,
  );
});

test("contentDir symlink is rejected", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();
  const realDir = path.join(manifestDir, "real");
  const linkDir = path.join(manifestDir, "linked");
  fs.mkdirSync(realDir, { recursive: true });
  fs.symlinkSync(realDir, linkDir, "dir");

  assert.throws(
    () => validateManifest(validManifest({ contentDir: "./linked" }), { workspaceDir, manifestDir }),
    /contentDir must not include symlinks/,
  );
});

test("owner.skillName is required for skill owner", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();

  assert.throws(
    () => validateManifest(validManifest({ owner: { type: "skill" } }), { workspaceDir, manifestDir }),
    /owner.skillName is required/,
  );
});

test("defaultPath must match routes", () => {
  const { workspaceDir, manifestDir } = makeWorkspace();

  assert.throws(
    () => validateManifest(validManifest({ defaultPath: "/missing" }), { workspaceDir, manifestDir }),
    /defaultPath must match/,
  );
});
