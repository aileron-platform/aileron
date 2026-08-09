#!/bin/sh

set -eu

repo_root="$(CDPATH= cd -- "$(dirname "$0")/../../../../../.." && pwd)"
skill_root="${repo_root}/workspace-runtime/agent-defaults/skills/aileron-canvas-publish"
runtime_assets="${skill_root}/assets/runtime-base"
site_dockerfile="${skill_root}/assets/user-site-repo/ci/Dockerfile.site"
static_context="${skill_root}/tests/container/fixtures/static-build"
next_source="${repo_root}/workspace-canvas/default-canvas"
runtime_image="aileron-canvas-runtime-base:contract-test"
builder_image="aileron-canvas-nextjs-builder:contract-test"
static_image="aileron-canvas-static-site:contract-test"
next_image="aileron-canvas-nextjs-site:contract-test"
static_container="aileron-canvas-static-contract-test"
next_container="aileron-canvas-nextjs-contract-test"
temporary_root="$(mktemp -d)"

cleanup() {
    docker rm -f "${static_container}" "${next_container}" >/dev/null 2>&1 || true
    rm -rf "${temporary_root}"
}
trap cleanup EXIT INT TERM

docker build \
    --file "${runtime_assets}/Dockerfile.runtime" \
    --tag "${runtime_image}" \
    "${runtime_assets}"
docker build \
    --file "${runtime_assets}/Dockerfile.builder" \
    --tag "${builder_image}" \
    "${runtime_assets}"

docker build \
    --file "${site_dockerfile}" \
    --build-arg "RUNTIME_BASE=${runtime_image}" \
    --tag "${static_image}" \
    "${static_context}"
docker run \
    --detach \
    --name "${static_container}" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=16m \
    "${static_image}" >/dev/null

docker exec -i "${static_container}" node - <<'NODE'
const assert = require("node:assert/strict");

async function verify() {
  let root;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      root = await fetch("http://127.0.0.1:8080/");
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  assert.ok(root, "Static server did not become reachable");
  assert.equal(root.status, 200);
  assert.match(await root.text(), /Canvas runtime test/);

  const nested = await fetch("http://127.0.0.1:8080/about/");
  assert.equal(nested.status, 200);
  assert.match(await nested.text(), /About Canvas/);

  const head = await fetch("http://127.0.0.1:8080/app.js", {
    method: "HEAD",
  });
  assert.equal(head.status, 200);
  assert.equal(head.headers.get("content-type"), "text/javascript; charset=utf-8");

  const post = await fetch("http://127.0.0.1:8080/", { method: "POST" });
  assert.equal(post.status, 405);

  const missing = await fetch("http://127.0.0.1:8080/not-found");
  assert.equal(missing.status, 404);

  const traversal = await fetch(
    "http://127.0.0.1:8080/%2e%2e/%2e%2e/etc/passwd",
  );
  assert.ok([403, 404].includes(traversal.status));
}

verify().catch((error) => {
  console.error(error);
  process.exit(1);
});
NODE

test "$(docker exec "${static_container}" id -u)" = "10001"

next_output="${temporary_root}/next-output"
next_context="${temporary_root}/next-context"
mkdir -p "${next_output}" "${next_context}/site"
docker run --rm \
    --volume "${next_source}:/workspace:ro" \
    --volume "${next_output}:/output" \
    "${builder_image}"
test -f "${next_output}/server.js"
test -d "${next_output}/.next/static"
cp -a "${next_output}/." "${next_context}/site/"

docker build \
    --file "${site_dockerfile}" \
    --build-arg "RUNTIME_BASE=${runtime_image}" \
    --tag "${next_image}" \
    "${next_context}"
docker run \
    --detach \
    --name "${next_container}" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m \
    "${next_image}" >/dev/null

docker exec -i "${next_container}" node - <<'NODE'
const assert = require("node:assert/strict");

async function verify() {
  let response;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      response = await fetch("http://127.0.0.1:8080/");
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  assert.ok(response, "Next.js server did not become reachable");
  assert.equal(response.status, 200);
  assert.match(await response.text(), /Canvas Runtime/);
}

verify().catch((error) => {
  console.error(error);
  process.exit(1);
});
NODE

test "$(docker exec "${next_container}" id -u)" = "10001"
echo "Canvas runtime and Next.js builder image contracts passed."
