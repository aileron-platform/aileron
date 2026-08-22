from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


def _find_ops_path() -> Path:
    container_ops_path = Path("/repo-root/scripts/dev/docker/ops.py")
    if container_ops_path.is_file():
        return container_ops_path

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "scripts" / "dev" / "docker" / "ops.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("scripts/dev/docker/ops.py not found")


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


def _completed(
    args: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.mark.unit
def test_full_reset_removes_only_labeled_workspace_containers_and_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    container_listings = iter(
        [
            "owned\tworkspace-runtime-owned\tworkspace-1\truntime\n"
            "unlabeled\tworkspace-runtime-unlabeled\t\t\n"
            "mismatch\tworkspace-runtime-mismatch\tworkspace-2\tcanvas\n"
            "unrelated\tworkspace-manager\tworkspace-3\truntime\n",
            "",
        ]
    )

    def fake_run_command(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args[:3] == ["docker", "ps", "-a"]:
            return _completed(args, stdout=next(container_listings))
        return _completed(args)

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "run_command", fake_run_command)
    monkeypatch.setattr(ops, "compose_down", lambda _repo_root: None)
    monkeypatch.setattr(ops, "clean_temp_directories", lambda _repo_root: 0)

    for relative_dir in ops.DATA_DIRS:
        data_dir = tmp_path / relative_dir
        data_dir.mkdir(parents=True)
        (data_dir / "payload").write_text("remove me", encoding="utf-8")
        (data_dir / ".gitkeep").touch()

    exit_code = ops.full_reset(
        tmp_path,
        assume_yes=True,
        remove_images=False,
        prune=False,
    )

    assert exit_code == 0
    assert [
        command for command in commands if command[:3] == ["docker", "rm", "-f"]
    ] == [["docker", "rm", "-f", "owned"]]
    container_list_commands = [
        command for command in commands if command[:3] == ["docker", "ps", "-a"]
    ]
    assert all(
        "label=aileron.workspace_id" in command for command in container_list_commands
    )
    assert all(
        "label=aileron.workload" in command for command in container_list_commands
    )
    for relative_dir in ops.DATA_DIRS:
        data_dir = tmp_path / relative_dir
        assert sorted(path.name for path in data_dir.iterdir()) == [".gitkeep"]


@pytest.mark.unit
def test_full_reset_command_returns_nonzero_when_workspace_container_stop_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_command(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["docker", "ps", "-a"]:
            return _completed(
                args,
                stdout="owned\tworkspace-runtime-owned\tworkspace-1\truntime\n",
            )
        if args[:2] == ["docker", "stop"]:
            return _completed(args, returncode=1, stderr="stop failed")
        return _completed(args)

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "run_command", fake_run_command)
    monkeypatch.setattr(ops, "compose_down", lambda _repo_root: None)
    monkeypatch.setattr(ops, "clean_temp_directories", lambda _repo_root: 0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "full-reset",
            "--yes",
            "--keep-images",
            "--no-prune",
        ],
    )

    assert ops.main() == 1


@pytest.mark.unit
def test_full_reset_command_returns_nonzero_when_workspace_container_remains(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_command(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["docker", "ps", "-a"]:
            return _completed(
                args,
                stdout="owned\tworkspace-runtime-owned\tworkspace-1\truntime\n",
            )
        return _completed(args)

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "run_command", fake_run_command)
    monkeypatch.setattr(ops, "compose_down", lambda _repo_root: None)
    monkeypatch.setattr(ops, "clean_temp_directories", lambda _repo_root: 0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "full-reset",
            "--yes",
            "--keep-images",
            "--no-prune",
        ],
    )

    assert ops.main() == 1


@pytest.mark.unit
def test_full_reset_command_returns_nonzero_when_required_data_remains(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run_command(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return _completed(args)

    postgres_dir = tmp_path / "data" / "postgres"
    postgres_dir.mkdir(parents=True)
    (postgres_dir / "broken-link").symlink_to(postgres_dir / "missing-target")

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "run_command", fake_run_command)
    monkeypatch.setattr(ops, "compose_down", lambda _repo_root: None)
    monkeypatch.setattr(ops, "clean_temp_directories", lambda _repo_root: 0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "full-reset",
            "--yes",
            "--keep-images",
            "--no-prune",
        ],
    )

    assert ops.main() == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("failed_prefix", "remove_images", "prune"),
    [
        (("docker", "volume", "rm"), False, False),
        (("docker", "network", "rm"), False, False),
        (("docker", "rmi", "-f"), True, False),
        (("docker", "system", "prune"), False, True),
    ],
)
def test_full_reset_command_returns_nonzero_when_docker_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed_prefix: tuple[str, ...],
    remove_images: bool,
    prune: bool,
) -> None:
    def fake_run_command(
        args: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if tuple(args[: len(failed_prefix)]) == failed_prefix:
            return _completed(args, returncode=1, stderr="cleanup failed")
        if args[:3] == ["docker", "volume", "ls"]:
            return _completed(args, stdout="aileron-volume\n")
        if args[:3] == ["docker", "network", "ls"]:
            return _completed(args, stdout="aileron-network\n")
        if args[:2] == ["docker", "images"]:
            return _completed(args, stdout="image-id\n")
        return _completed(args)

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "run_command", fake_run_command)
    monkeypatch.setattr(ops, "compose_down", lambda _repo_root: None)
    monkeypatch.setattr(ops, "clean_temp_directories", lambda _repo_root: 0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "full-reset",
            "--yes",
            "--remove-images" if remove_images else "--keep-images",
            "--prune" if prune else "--no-prune",
        ],
    )

    assert ops.main() == 1


@pytest.mark.unit
def test_compose_up_uses_prebuilt_images_and_removes_project_orphans(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    envs: list[dict[str, str]] = []
    repo_root = tmp_path
    (repo_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (repo_root / "docker-compose.bundled-data-services.yml").write_text(
        "services: {}\n",
        encoding="utf-8",
    )

    def fake_stream_command(
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        env: dict[str, str] | None = None,
        action: str,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        commands.append(args)
        envs.append(env or {})
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(ops, "stream_command", fake_stream_command)
    monkeypatch.setattr(
        ops, "ensure_host_storage_directories", lambda *_args, **_kwargs: None
    )

    ops.compose_up(repo_root, detach=True, env={"TEST_ENV": "1"})

    assert commands == [
        [
            "docker",
            "compose",
            "-f",
            str(repo_root / "docker-compose.yml"),
            "-f",
            str(repo_root / "docker-compose.bundled-data-services.yml"),
            "up",
            "--remove-orphans",
            "--no-build",
            "-d",
        ]
    ]
    assert envs == [{"TEST_ENV": "1"}]


@pytest.mark.unit
def test_build_compose_env_includes_cross_platform_host_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HOST_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("HOST_WORKSPACE_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("HOST_WORKSPACES_DIR", raising=False)
    monkeypatch.delenv("HOST_WORKSPACE_SCRIPTS_DIR", raising=False)
    monkeypatch.delenv("HOST_RUNTIME_HOME_DIR", raising=False)
    monkeypatch.delenv("HOST_KNOWLEDGE_BASES_DIR", raising=False)
    monkeypatch.delenv("HOST_RUNTIME_ASSERTION_DIR", raising=False)
    monkeypatch.delenv(
        "HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE",
        raising=False,
    )
    monkeypatch.delenv("HOST_TURN_CONFIG_DIR", raising=False)
    monkeypatch.delenv("HOST_TURN_SECRETS_DIR", raising=False)

    env = ops.build_compose_env()

    assert env["HOST_PROJECT_ROOT"] == str(tmp_path.resolve())
    assert env["HOST_WORKSPACE_RUNTIME_DIR"] == str(tmp_path / "workspace-runtime")
    assert env["HOST_WORKSPACES_DIR"] == str(tmp_path / "data" / "workspace-data")
    assert env["HOST_WORKSPACE_SCRIPTS_DIR"] == str(
        tmp_path / "data" / "workspace-scripts"
    )
    assert env["HOST_RUNTIME_HOME_DIR"] == str(tmp_path / "data" / "runtime-home")
    assert env["HOST_KNOWLEDGE_BASES_DIR"] == str(tmp_path / "data" / "knowledge-bases")
    assert env["HOST_RUNTIME_ASSERTION_DIR"] == str(
        tmp_path / "data" / "runtime-assertions"
    )
    assert env["HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE"] == str(
        tmp_path / "data" / "runtime-assertions" / "jwks.json"
    )
    assert env["HOST_TURN_CONFIG_DIR"] == str(tmp_path / "data" / "turn-config")
    assert env["HOST_TURN_SECRETS_DIR"] == str(tmp_path / "data" / "turn-secrets")


@pytest.mark.unit
def test_ensure_host_storage_directories_prepares_knowledge_base_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chmod_calls: list[tuple[Path, int]] = []
    chown_calls: list[tuple[Path, int, int]] = []
    target_dir = tmp_path / "data" / "knowledge-bases"
    assertion_dir = tmp_path / "data" / "runtime-assertions"
    turn_config_dir = tmp_path / "data" / "turn-config"
    turn_secrets_dir = tmp_path / "data" / "turn-secrets"

    monkeypatch.setattr(
        ops.os, "chmod", lambda path, mode: chmod_calls.append((Path(path), mode))
    )
    monkeypatch.setattr(
        ops.os,
        "chown",
        lambda path, uid, gid: chown_calls.append((Path(path), uid, gid)),
    )

    ops.ensure_host_storage_directories(
        tmp_path,
        {
            "HOST_KNOWLEDGE_BASES_DIR": str(target_dir),
            "HOST_RUNTIME_ASSERTION_DIR": str(assertion_dir),
            "HOST_TURN_CONFIG_DIR": str(turn_config_dir),
            "HOST_TURN_SECRETS_DIR": str(turn_secrets_dir),
        },
    )

    assert target_dir.is_dir()
    assert assertion_dir.is_dir()
    assert turn_config_dir.is_dir()
    assert turn_secrets_dir.is_dir()
    assert chmod_calls == [
        (target_dir, 0o770),
        (assertion_dir, 0o700),
        (turn_config_dir, 0o700),
        (turn_secrets_dir, 0o700),
    ]
    assert chown_calls == [(target_dir, 1000, 1000)]


@pytest.mark.unit
def test_compose_up_requires_compose_file(tmp_path: Path) -> None:
    with pytest.raises(ops.OpsError):
        ops.compose_up(tmp_path, detach=True, env={})


def _stub_up_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    compose_env: dict[str, str],
) -> tuple[
    list[tuple[Path, bool, dict[str, str]]],
    list[tuple[Path, dict[str, str]]],
]:
    compose_calls: list[tuple[Path, bool, dict[str, str]]] = []
    build_calls: list[tuple[Path, dict[str, str]]] = []

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(ops, "build_compose_env", lambda: compose_env)
    monkeypatch.setattr(
        ops,
        "build_local_images",
        lambda repo_root, *, env: build_calls.append((repo_root, env)),
    )
    monkeypatch.setattr(
        ops,
        "compose_up",
        lambda repo_root, *, detach, env: compose_calls.append(
            (repo_root, detach, env)
        ),
    )
    return compose_calls, build_calls


@pytest.mark.unit
def test_main_up_with_build_runs_bake_then_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compose_env = {"HOST_PROJECT_ROOT": str(tmp_path)}
    compose_calls, build_calls = _stub_up_dependencies(
        monkeypatch, compose_env=compose_env
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
    assert build_calls == [(tmp_path.resolve(), compose_env)]
    assert compose_calls == [(tmp_path.resolve(), False, compose_env)]


@pytest.mark.unit
def test_main_up_default_reuses_local_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    compose_env = {"HOST_PROJECT_ROOT": str(tmp_path)}
    compose_calls, build_calls = _stub_up_dependencies(
        monkeypatch, compose_env=compose_env
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "up",
        ],
    )

    exit_code = ops.main()

    assert exit_code == 0
    assert build_calls == []
    assert compose_calls == [(tmp_path.resolve(), True, compose_env)]


@pytest.mark.unit
def test_root_compose_does_not_define_static_execution_plane() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = compose["services"]

    assert {"workspace-runtime", "workspace-browser", "workspace-canvas"}.isdisjoint(
        services
    )


@pytest.mark.unit
def test_build_local_images_uses_bake_local_group(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    (tmp_path / ops.BAKE_FILE).write_text('group "local" {}\n', encoding="utf-8")

    monkeypatch.setattr(
        ops,
        "stream_command",
        lambda args, **_kwargs: commands.append(args),
    )

    ops.build_local_images(tmp_path, env={"TEST_ENV": "1"})

    assert commands == [
        [
            "docker",
            "buildx",
            "bake",
            "--load",
            "local",
        ]
    ]


@pytest.mark.unit
def test_main_routes_down_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, dict[str, str] | None]] = []

    monkeypatch.setattr(ops, "ensure_docker_available", lambda: None)
    monkeypatch.setattr(
        ops,
        "compose_down",
        lambda repo_root, *, env=None: calls.append((repo_root, env)),
    )
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
@pytest.mark.parametrize("removed_command", ["cleanup-workspaces", "cleanup"])
def test_cli_does_not_expose_removed_cleanup_commands(removed_command: str) -> None:
    help_result = subprocess.run(
        [sys.executable, str(OPS_PATH), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    removed_command_result = subprocess.run(
        [sys.executable, str(OPS_PATH), removed_command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert help_result.returncode == 0
    assert removed_command not in help_result.stdout
    assert "full-reset" in help_result.stdout
    assert removed_command_result.returncode == 2


@pytest.mark.unit
def test_find_container_id_by_ports_returns_matching_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        ops,
        "run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="abc123\t0.0.0.0:3001->3001/tcp\nother\t0.0.0.0:8082->8082/tcp\n",
            stderr="",
        ),
    )

    container_id = ops.find_container_id_by_ports(
        tmp_path, port=3001, internal_port=3001
    )

    assert container_id == "abc123"


@pytest.mark.unit
def test_build_pytest_command_appends_extra_args() -> None:
    config = ops.get_test_service_config("manager")

    command = ops.build_pytest_command(
        config, "tests/integration/sample", ["-v", "--lf"]
    )

    assert command == (
        "uv run python -m pytest tests/integration/sample -v --lf --tb=short"
    )


@pytest.mark.unit
def test_main_routes_test_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, str, str | None, str | None, list[str]]] = []

    monkeypatch.setattr(
        ops,
        "run_test_command",
        lambda repo_root, *, service_type, container_id, test_path, extra_args: calls.append(
            (repo_root, service_type, container_id, test_path, extra_args)
        )
        or 0,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ops.py",
            "--repo-root",
            str(tmp_path),
            "test",
            "manager",
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
            "manager",
            "container-1",
            "tests/integration/sample",
            ["-v", "--lf"],
        )
    ]
