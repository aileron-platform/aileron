from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


def _find_ops_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "scripts" / "dev" / "docker" / "ops.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到 scripts/dev/docker/ops.py")


def _find_compose_path() -> Path:
    repo_root_candidate = Path("/repo-root/docker-compose.yml")
    if repo_root_candidate.is_file():
        return repo_root_candidate

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "docker-compose.yml"
        if candidate.is_file() and (parent / "workspace-chrome").is_dir():
            return candidate
    raise FileNotFoundError("Could not find docker-compose.yml")


OPS_PATH = _find_ops_path()
COMPOSE_PATH = _find_compose_path()
OPS_SPEC = importlib.util.spec_from_file_location("host_docker_ops", OPS_PATH)
assert OPS_SPEC is not None and OPS_SPEC.loader is not None
ops = importlib.util.module_from_spec(OPS_SPEC)
sys.modules[OPS_SPEC.name] = ops
OPS_SPEC.loader.exec_module(ops)


@pytest.mark.unit
def test_list_workspace_containers_filters_supported_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path("/tmp/repo")

    monkeypatch.setattr(
        ops,
        "list_all_containers",
        lambda _repo_root: [
            ops.DockerContainer("1", "workspace-runtime-abc"),
            ops.DockerContainer("2", "workspace-browser-abc"),
            ops.DockerContainer("3", "workspace-nextjs-abc"),
            ops.DockerContainer("4", "workspace-manager"),
        ],
    )

    containers = ops.list_workspace_containers(repo_root)

    assert [container.container_id for container in containers] == ["1", "2", "3"]


@pytest.mark.unit
def test_compose_up_builds_detached_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []
    envs: list[dict[str, str]] = []
    repo_root = tmp_path
    (repo_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        envs.append(env or {})
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ops, "run_command", fake_run_command)

    ops.compose_up(repo_root, build=True, detach=True, env={"TEST_ENV": "1"})

    assert commands == [["docker", "compose", "up", "-d", "--build"]]
    assert envs == [{"TEST_ENV": "1"}]


@pytest.mark.unit
def test_build_compose_env_includes_cross_platform_host_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    profile = ops.StartupProfile(
        startup_mode="dockerhub-dev",
        image_arch="arm64",
        runtime_base="lite",
        service_tag="dev-arm64",
        runtime_tag="dev-lite-arm64",
        runtime_base_image="ailerondocker/workspace-runtime-base-lite:dev-arm64",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOST_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("HOST_WORKSPACE_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("HOST_WORKSPACE_MANAGER_DIR", raising=False)
    monkeypatch.delenv("HOST_WORKSPACES_DIR", raising=False)
    monkeypatch.delenv("HOST_WORKSPACE_SCRIPTS_DIR", raising=False)
    monkeypatch.delenv("HOST_CLAUDE_DATA_DIR", raising=False)
    monkeypatch.delenv("HOST_SSH_KEYS_DIR", raising=False)

    env = ops.build_compose_env(profile)

    assert env["HOST_PROJECT_ROOT"] == str(tmp_path.resolve())
    assert env["HOST_WORKSPACE_RUNTIME_DIR"] == str(tmp_path / "workspace-runtime")
    assert env["HOST_WORKSPACE_MANAGER_DIR"] == str(tmp_path / "workspace-manager")
    assert env["HOST_WORKSPACES_DIR"] == str(tmp_path / "data" / "workspace-data")
    assert env["HOST_WORKSPACE_SCRIPTS_DIR"] == str(tmp_path / "data" / "workspace-scripts")
    assert env["HOST_CLAUDE_DATA_DIR"] == str(tmp_path / "data" / "claude-data")
    assert env["HOST_SSH_KEYS_DIR"] == str(tmp_path / "data" / "ssh-keys")


@pytest.mark.unit
def test_compose_up_requires_compose_file(tmp_path: Path) -> None:
    with pytest.raises(ops.OpsError):
        ops.compose_up(tmp_path, build=False, detach=True, env={})


@pytest.mark.unit
def test_main_routes_up_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, bool, bool, dict[str, str]]] = []
    profile = ops.StartupProfile(
        startup_mode="dockerhub-dev",
        image_arch="amd64",
        runtime_base="lite",
        service_tag="dev-amd64",
        runtime_tag="dev-lite-amd64",
        runtime_base_image="ailerondocker/workspace-runtime-base-lite:dev-amd64",
    )
    compose_env = {"WORKSPACE_MANAGER_IMAGE": "ailerondocker/workspace-manager:dev-amd64"}

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "resolve_startup_profile", lambda **kwargs: profile)
    monkeypatch.setattr(ops, "build_compose_env", lambda _profile: compose_env)
    monkeypatch.setattr(ops, "print_startup_profile", lambda _profile, *, build: None)
    monkeypatch.setattr(ops, "compose_pull", lambda repo_root, *, env: None)
    monkeypatch.setattr(
        ops,
        "compose_up",
        lambda repo_root, *, build, detach, env: calls.append((repo_root, build, detach, env)),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "up",
            "--build",
            "--foreground",
        ],
    )

    exit_code = ops.main()

    assert exit_code == 0
    assert calls == [(tmp_path.resolve(), True, False, compose_env)]


@pytest.mark.unit
def test_main_routes_dockerhub_dev_without_implicit_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compose_calls: list[tuple[Path, bool, bool, dict[str, str]]] = []
    pull_calls: list[tuple[Path, dict[str, str]]] = []
    profile = ops.StartupProfile(
        startup_mode="dockerhub-dev",
        image_arch="amd64",
        runtime_base="lite",
        service_tag="dev-amd64",
        runtime_tag="dev-lite-amd64",
        runtime_base_image="ailerondocker/workspace-runtime-base-lite:dev-amd64",
    )
    compose_env = {"WORKSPACE_MANAGER_IMAGE": "ailerondocker/workspace-manager:dev-amd64"}

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "resolve_startup_profile", lambda **kwargs: profile)
    monkeypatch.setattr(ops, "build_compose_env", lambda _profile: compose_env)
    monkeypatch.setattr(ops, "print_startup_profile", lambda _profile, *, build: None)
    monkeypatch.setattr(ops, "compose_pull", lambda repo_root, *, env: pull_calls.append((repo_root, env)))
    monkeypatch.setattr(
        ops,
        "compose_up",
        lambda repo_root, *, build, detach, env: compose_calls.append((repo_root, build, detach, env)),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "up",
            "--no-prompt",
            "--startup-mode",
            "dockerhub-dev",
        ],
    )

    exit_code = ops.main()

    assert exit_code == 0
    assert pull_calls == [(tmp_path.resolve(), compose_env)]
    assert compose_calls == [(tmp_path.resolve(), False, True, compose_env)]


@pytest.mark.unit
def test_default_browser_compose_uses_shared_webrtc_host_port_contract() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    browser_service = compose["services"]["workspace-browser"]

    assert "NEKO_WEBRTC_UDPMUX=${BROWSER_WEBRTC_HOST_UDP_PORT:-52330}" in browser_service["environment"]
    assert (
        "NEKO_WEBRTC_NAT1TO1=${BROWSER_WEBRTC_NAT1TO1_IP:-127.0.0.1}"
        in browser_service["environment"]
    )
    assert "${BROWSER_WEBRTC_HOST_UDP_PORT:-52330}:6080" in browser_service["ports"]
    assert (
        "${BROWSER_WEBRTC_HOST_UDP_PORT:-52330}:${BROWSER_WEBRTC_HOST_UDP_PORT:-52330}/udp"
        in browser_service["ports"]
    )


@pytest.mark.unit
def test_main_routes_down_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, dict[str, str] | None]] = []

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "compose_down", lambda repo_root, *, env=None: calls.append((repo_root, env)))
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "down",
        ],
    )

    exit_code = ops.main()

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0][0] == tmp_path.resolve()
    assert isinstance(calls[0][1], dict)


@pytest.mark.unit
def test_find_container_id_by_ports_returns_matching_container(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ops,
        "run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="abc123\t0.0.0.0:3002->3002/tcp\nother\t0.0.0.0:3001->3001/tcp\n",
            stderr="",
        ),
    )

    container_id = ops.find_container_id_by_ports(tmp_path, port=3002, internal_port=3002)

    assert container_id == "abc123"


@pytest.mark.unit
def test_build_pytest_command_appends_extra_args() -> None:
    config = ops.get_test_service_config("runtime")

    command = ops.build_pytest_command(config, "tests/integration/sample", ["-v", "--lf"])

    assert command == "/workspace-runtime/.venv/bin/python -m pytest tests/integration/sample -v --lf --tb=short"


@pytest.mark.unit
def test_main_routes_test_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, str, str | None, str | None, list[str]]] = []

    monkeypatch.setattr(
        ops,
        "run_test_command",
        lambda repo_root, *, service_type, container_id, test_path, extra_args: calls.append(
            (repo_root, service_type, container_id, test_path, extra_args)
        ) or 0,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "test",
            "runtime",
            "container-1",
            "tests/integration/sample",
            "-v",
            "--lf",
        ],
    )

    exit_code = ops.main()

    assert exit_code == 0
    assert calls == [
        (
            tmp_path.resolve(),
            "runtime",
            "container-1",
            "tests/integration/sample",
            ["-v", "--lf"],
        )
    ]
