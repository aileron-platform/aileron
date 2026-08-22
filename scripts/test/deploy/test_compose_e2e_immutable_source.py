from __future__ import annotations

import http.client
import importlib.util
import json
import os
import shutil
import socket
import tempfile
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
RENDERER_PATH = ROOT / "scripts/test/compose-e2e/render_compose.py"
RUNNER_PATH = ROOT / "scripts/test/compose-e2e/run.sh"
RUNTIME_DOCKERFILE_PATH = ROOT / "workspace-runtime/Dockerfile"
RENDERER_SPEC = importlib.util.spec_from_file_location(
    "compose_e2e_renderer", RENDERER_PATH
)
assert RENDERER_SPEC and RENDERER_SPEC.loader
RENDERER = importlib.util.module_from_spec(RENDERER_SPEC)
RENDERER_SPEC.loader.exec_module(RENDERER)

HOST_PROJECT_ROOT = "${HOST_PROJECT_ROOT:?HOST_PROJECT_ROOT must be set}"
RUNTIME_PROBE_IMAGE_ENV = "COMPOSE_E2E_RUNTIME_PROBE_IMAGE"
WORKSPACE_RUNTIME_IMAGE_ENV = "COMPOSE_E2E_WORKSPACE_RUNTIME_IMAGE"
SHARED_ROOT_ENV = "COMPOSE_E2E_TEST_SHARED_ROOT"


class _UnixSocketConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str) -> None:
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class DockerEngine:
    def __init__(self, socket_path: str = "/var/run/docker.sock") -> None:
        self.socket_path = socket_path

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        expected: set[int],
    ) -> bytes:
        connection = _UnixSocketConnection(self.socket_path)
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, f"/v1.44{path}", body=body, headers=headers)
        response = connection.getresponse()
        content = response.read()
        connection.close()
        if response.status not in expected:
            detail = content.decode("utf-8", errors="replace")
            raise AssertionError(
                f"Docker Engine {method} {path} returned {response.status}: {detail}"
            )
        return content

    def run(
        self,
        *,
        image: str,
        command: list[str],
        binds: list[str],
        mounts: list[dict[str, Any]],
        user: str | None = None,
    ) -> None:
        name = f"aileron-immutable-source-probe-{uuid.uuid4().hex}"
        configuration: dict[str, Any] = {
            "Image": image,
            "Cmd": command,
            "HostConfig": {"Binds": binds, "Mounts": mounts},
        }
        if user is not None:
            configuration["User"] = user
        created = json.loads(
            self.request(
                "POST",
                f"/containers/create?name={urllib.parse.quote(name)}",
                configuration,
                expected={201},
            )
        )
        container_id = created["Id"]
        try:
            self.request("POST", f"/containers/{container_id}/start", expected={204})
            waited = json.loads(
                self.request(
                    "POST",
                    f"/containers/{container_id}/wait?condition=not-running",
                    expected={200},
                )
            )
            if waited.get("StatusCode") != 0:
                logs = self.request(
                    "GET",
                    f"/containers/{container_id}/logs?stdout=1&stderr=1",
                    expected={200},
                ).decode("utf-8", errors="replace")
                raise AssertionError(
                    f"runtime probe exited with {waited.get('StatusCode')}: {logs}"
                )
        finally:
            self.request(
                "DELETE",
                f"/containers/{container_id}?force=1&v=1",
                expected={204},
            )


@dataclass(frozen=True)
class RenderedFixture:
    document: dict[str, Any]
    source_root: Path
    state_root: Path


def _runtime_configuration() -> tuple[str, Path]:
    image = os.environ.get(RUNTIME_PROBE_IMAGE_ENV)
    shared_root = os.environ.get(SHARED_ROOT_ENV)
    if not image or not shared_root:
        pytest.skip(
            f"set {RUNTIME_PROBE_IMAGE_ENV} and {SHARED_ROOT_ENV} for Docker runtime probes"
        )
    root = Path(shared_root).resolve(strict=True)
    if not root.is_dir():
        raise AssertionError("shared runtime probe root must be a directory")
    return image, root


def _workspace_runtime_image() -> str:
    image = os.environ.get(WORKSPACE_RUNTIME_IMAGE_ENV)
    if not image:
        pytest.skip(
            f"set {WORKSPACE_RUNTIME_IMAGE_ENV} for the image-baked Runtime probe"
        )
    return image


def _make_archive_shaped_source(shared_root: Path) -> RenderedFixture:
    case_root = Path(tempfile.mkdtemp(prefix="immutable-source-", dir=shared_root))
    source_root = case_root / "source"
    state_root = case_root / "state"
    source_root.mkdir(mode=0o700)
    state_root.mkdir(mode=0o700)
    shutil.copyfile(ROOT / "docker-compose.yml", source_root / "docker-compose.yml")
    shutil.copyfile(
        ROOT / "docker-compose.bundled-data-services.yml",
        source_root / "docker-compose.bundled-data-services.yml",
    )
    for directory in ("workspace-manager", "frontend", "init-sql"):
        (source_root / directory).mkdir(mode=0o700)
    (source_root / "workspace-manager" / "tracked.py").write_text(
        "TRACKED = True\n", encoding="utf-8"
    )
    (source_root / "frontend" / "tracked.js").write_text(
        "export const tracked = true;\n", encoding="utf-8"
    )
    shutil.copyfile(
        ROOT / "init-sql/000_create_databases.sql",
        source_root / "init-sql/000_create_databases.sql",
    )
    for path in source_root.rglob("*"):
        path.chmod(0o500 if path.is_dir() else 0o400)
    source_root.chmod(0o500)

    output = state_root / "compose.yml"
    RENDERER.render(
        source_root / "docker-compose.yml",
        source_root / "docker-compose.bundled-data-services.yml",
        output,
        "aileron-compose-e2e-immutable-source-network",
        str(source_root),
        str(state_root),
    )
    return RenderedFixture(
        document=yaml.safe_load(output.read_text(encoding="utf-8")),
        source_root=source_root,
        state_root=state_root,
    )


def _selected_runtime_mounts(
    fixture: RenderedFixture, service_name: str, targets: set[str]
) -> tuple[list[str], list[dict[str, Any]]]:
    volumes = fixture.document["services"][service_name].get("volumes", [])
    binds: list[str] = []
    mounts: list[dict[str, Any]] = []
    for volume in volumes:
        if isinstance(volume, str):
            rendered = volume.replace(HOST_PROJECT_ROOT, str(fixture.source_root))
            if ":" not in rendered:
                if rendered in targets:
                    mounts.append({"Type": "volume", "Target": rendered})
                continue
            source, target, *options = rendered.split(":")
            if target not in targets:
                continue
            mode = options[0] if options else "rw"
            binds.append(f"{source}:{target}:{mode}")
            continue
        if not isinstance(volume, dict) or volume.get("target") not in targets:
            continue
        if volume.get("type") != "bind":
            raise AssertionError("runtime probe supports only explicit bind mounts")
        mounts.append(
            {
                "Type": "bind",
                "Source": volume["source"],
                "Target": volume["target"],
                "ReadOnly": volume.get("read_only") is True,
                "BindOptions": {
                    "CreateMountpoint": volume.get("bind", {}).get(
                        "create_host_path", True
                    )
                },
            }
        )
    return binds, mounts


def _assert_source_remains_immutable(source_root: Path) -> None:
    assert not (source_root / "workspace-manager/.venv").exists()
    assert not (source_root / "frontend/node_modules").exists()
    assert (source_root.stat().st_mode & 0o777) == 0o500
    for path in source_root.rglob("*"):
        expected = 0o500 if path.is_dir() else 0o400
        assert (path.stat().st_mode & 0o777) == expected, path


def test_manager_runtime_uses_exact_source_image_without_nested_venv_mount() -> None:
    image, shared_root = _runtime_configuration()
    fixture = _make_archive_shaped_source(shared_root)
    binds, mounts = _selected_runtime_mounts(
        fixture,
        "turn-readiness-preflight",
        {"/workspace-manager", "/workspace-manager/.venv"},
    )

    DockerEngine().run(
        image=image,
        command=["python", "-c", "print('manager runtime probe passed')"],
        binds=binds,
        mounts=mounts,
    )

    assert binds == []
    assert mounts == []
    _assert_source_remains_immutable(fixture.source_root)


def test_frontend_runtime_uses_exact_source_image_without_nested_node_modules_mount() -> (
    None
):
    image, shared_root = _runtime_configuration()
    fixture = _make_archive_shaped_source(shared_root)
    binds, mounts = _selected_runtime_mounts(
        fixture, "frontend", {"/app", "/app/node_modules"}
    )

    DockerEngine().run(
        image=image,
        command=["python", "-c", "print('frontend runtime probe passed')"],
        binds=binds,
        mounts=mounts,
    )

    _assert_source_remains_immutable(fixture.source_root)
    assert binds == []
    assert mounts == []


def test_postgres_init_sql_copy_is_explicitly_read_only_and_non_root_readable() -> None:
    image, shared_root = _runtime_configuration()
    fixture = _make_archive_shaped_source(shared_root)
    binds, mounts = _selected_runtime_mounts(
        fixture, "postgres", {"/docker-entrypoint-initdb.d"}
    )

    DockerEngine().run(
        image=image,
        command=[
            "python",
            "-c",
            (
                "from pathlib import Path; "
                "data = Path('/docker-entrypoint-initdb.d/000_create_databases.sql').read_bytes(); "
                "assert data"
            ),
        ],
        binds=binds,
        mounts=mounts,
        user="65534:65534",
    )

    assert binds == []
    assert mounts == [
        {
            "Type": "bind",
            "Source": str(fixture.state_root / "init-sql"),
            "Target": "/docker-entrypoint-initdb.d",
            "ReadOnly": True,
            "BindOptions": {"CreateMountpoint": False},
        }
    ]
    assert (fixture.state_root / "init-sql").stat().st_mode & 0o777 == 0o555
    for path in (fixture.state_root / "init-sql").iterdir():
        assert path.stat().st_mode & 0o777 == 0o444
    _assert_source_remains_immutable(fixture.source_root)


def test_local_keycloak_explicitly_selects_the_dev_file_database() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        fixture = _make_archive_shaped_source(Path(temporary_directory))

    keycloak_environment = fixture.document["services"]["keycloak"]["environment"]
    assert keycloak_environment["KC_DB"] == "dev-file"


def test_dynamic_supporting_images_are_explicit_compose_inputs() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        fixture = _make_archive_shaped_source(Path(temporary_directory))

    manager_environment = fixture.document["services"]["workspace-manager"][
        "environment"
    ]
    assert manager_environment["WORKSPACE_BROWSER_IMAGE"] == (
        "${WORKSPACE_BROWSER_IMAGE:?WORKSPACE_BROWSER_IMAGE must be set}"
    )
    assert manager_environment["WORKSPACE_CANVAS_IMAGE"] == (
        "${WORKSPACE_CANVAS_IMAGE:?WORKSPACE_CANVAS_IMAGE must be set}"
    )


def test_dynamic_workspace_runtime_uses_image_baked_source_without_archive_mounts() -> (
    None
):
    _, shared_root = _runtime_configuration()
    runtime_image = _workspace_runtime_image()
    fixture = _make_archive_shaped_source(shared_root)
    manager_environment = fixture.document["services"]["workspace-manager"][
        "environment"
    ]

    assert "HOST_WORKSPACE_RUNTIME_DIR" not in manager_environment
    for data_setting in (
        "HOST_WORKSPACES_DIR",
        "HOST_WORKSPACE_SCRIPTS_DIR",
        "HOST_RUNTIME_HOME_DIR",
        "HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE",
    ):
        assert data_setting in manager_environment

    DockerEngine().run(
        image=runtime_image,
        command=[
            "/workspace-runtime/.venv/bin/python",
            "-c",
            (
                "from pathlib import Path; "
                "assert Path('/workspace-runtime/app/main.py').read_bytes(); "
                "assert Path('/workspace-runtime/scripts/initialize_workspace_runtime.py').read_bytes()"
            ),
        ],
        binds=[],
        mounts=[],
        user="1000:1000",
    )

    _assert_source_remains_immutable(fixture.source_root)


def test_compose_runner_selects_image_baked_workspace_runtime_production() -> None:
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    dockerfile = RUNTIME_DOCKERFILE_PATH.read_text(encoding="utf-8")
    production_stage = dockerfile.split("FROM base-devtools AS production", maxsplit=1)[
        1
    ].split("FROM base-common AS kubernetes", maxsplit=1)[0]

    assert (
        "workspace-runtime-production.tags=ailerondocker/workspace-runtime:$source_tag"
        in runner
    )
    assert "runtime-base-lite workspace-runtime-production" in runner
    assert "workspace-runtime:$source_tag-lite" not in runner
    assert "COPY --chown=developer:developer workspace-runtime/app/ ./app/" in (
        production_stage
    )
    assert (
        "COPY --chown=developer:developer workspace-runtime/scripts/ "
        "/workspace-runtime/scripts/"
    ) in production_stage
