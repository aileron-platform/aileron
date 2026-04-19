from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


def _find_ops_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "scripts" / "dev" / "docker" / "ops.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("找不到 scripts/dev/docker/ops.py")


OPS_PATH = _find_ops_path()
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
    repo_root = tmp_path
    (repo_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    def fake_run_command(
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ops, "run_command", fake_run_command)

    ops.compose_up(repo_root, build=True, detach=True)

    assert commands == [["docker", "compose", "up", "-d", "--build"]]


@pytest.mark.unit
def test_compose_up_requires_compose_file(tmp_path: Path) -> None:
    with pytest.raises(ops.OpsError):
        ops.compose_up(tmp_path, build=False, detach=True)


@pytest.mark.unit
def test_main_routes_up_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, bool, bool]] = []

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(
        ops,
        "compose_up",
        lambda repo_root, *, build, detach: calls.append((repo_root, build, detach)),
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
    assert calls == [(tmp_path.resolve(), True, False)]


@pytest.mark.unit
def test_main_routes_down_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[Path] = []

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "compose_down", lambda repo_root: calls.append(repo_root))
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
    assert calls == [tmp_path.resolve()]


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
