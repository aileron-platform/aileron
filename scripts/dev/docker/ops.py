#!/usr/bin/env python3
"""Optional host-side convenience commands for Aileron Docker operations.

Docker Buildx Bake and Docker Compose remain the canonical build and runtime
interfaces. This module adds project-specific cleanup and diagnostics without
owning image or package versions.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

WORKSPACE_CONTAINER_PREFIXES = {
    "runtime": "workspace-runtime-",
    "browser": "workspace-browser-",
    "browser-connectivity-probe": "workspace-browser-connectivity-probe-",
    "canvas": "workspace-canvas-",
}
PROJECT_IMAGE_REPOS = (
    "ailerondocker/workspace-manager",
    "ailerondocker/workspace-runtime",
    "ailerondocker/workspace-chrome",
    "ailerondocker/workspace-canvas",
    "ailerondocker/workspace-ui",
    "ailerondocker/workspace-runtime-base-lite",
)
BAKE_FILE = Path("docker-bake.hcl")
DATA_DIRS = (
    "data/postgres",
    "data/redis",
    "data/workspace-data",
    "data/workspace-scripts",
    "data/runtime-home",
    "data/knowledge-bases",
    "data/runtime-assertions",
    "data/turn-config",
    "data/turn-secrets",
)
PRESERVED_FILENAMES = {".gitkeep", "README.md"}

BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


@dataclass(frozen=True)
class DockerContainer:
    container_id: str
    name: str
    workspace_id: str
    workload: str


@dataclass(frozen=True)
class TestServiceConfig:
    service_type: str
    port: int
    service_name: str
    internal_port: int
    default_test_path: str
    container_test_dir: str
    script_dir: str
    work_dir: str
    python_check_command: list[str]
    python_test_command: str


class OpsError(RuntimeError):
    """Raised when an operation cannot continue."""


TEST_SERVICE_CONFIGS: dict[str, TestServiceConfig] = {
    "manager": TestServiceConfig(
        service_type="manager",
        port=3001,
        service_name="workspace-manager",
        internal_port=3001,
        default_test_path="tests/integration",
        container_test_dir="/workspace-manager/tests",
        script_dir="workspace-manager",
        work_dir="/workspace-manager",
        python_check_command=["which", "uv"],
        python_test_command="uv run python -m pytest",
    ),
}


def colorize(color: str, text: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{NC}"
    return text


def print_info(message: str) -> None:
    print(colorize(BLUE, message))


def print_success(message: str) -> None:
    print(colorize(GREEN, message))


def print_warning(message: str) -> None:
    print(colorize(YELLOW, message))


def print_error(message: str) -> None:
    print(colorize(RED, message))


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture_output,
        env=env,
    )


def require_command_success(
    result: subprocess.CompletedProcess[str], *, action: str
) -> None:
    if result.returncode != 0:
        detail = result.stderr.strip()
        suffix = f": {detail}" if detail else ""
        raise OpsError(f"{action}失敗{suffix}")


def stream_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
    action: str,
) -> subprocess.CompletedProcess[str]:
    """Run a long command inheriting parent stdio so the user sees progress in real time."""
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise OpsError(f"{action} failed (exit code {result.returncode})")
    return result


def ensure_docker_available() -> None:
    if shutil.which("docker") is None:
        raise OpsError(
            "找不到 docker 指令，請先安裝並啟動 Docker Desktop 或 Docker Engine。"
        )


def prompt_confirm(
    message: str, *, default_no: bool = True, assume_yes: bool = False
) -> bool:
    if assume_yes:
        return True
    suffix = "[y/N]" if default_no else "[Y/n]"
    try:
        reply = input(f"{message} {suffix}: ").strip().lower()
    except EOFError:
        return False
    if not reply:
        return not default_no
    return reply in {"y", "yes"}


def build_compose_env() -> dict[str, str]:
    env = os.environ.copy()
    repo_root = Path(env.get("HOST_PROJECT_ROOT", Path.cwd()))
    if not repo_root.is_absolute():
        repo_root = repo_root.resolve()
    data_root = repo_root / "data"
    env.update(
        {
            "HOST_PROJECT_ROOT": str(repo_root),
            "HOST_WORKSPACE_RUNTIME_DIR": str(
                env.get("HOST_WORKSPACE_RUNTIME_DIR", repo_root / "workspace-runtime")
            ),
            "HOST_WORKSPACES_DIR": str(
                env.get("HOST_WORKSPACES_DIR", data_root / "workspace-data")
            ),
            "HOST_WORKSPACE_SCRIPTS_DIR": str(
                env.get("HOST_WORKSPACE_SCRIPTS_DIR", data_root / "workspace-scripts")
            ),
            "HOST_RUNTIME_HOME_DIR": str(
                env.get("HOST_RUNTIME_HOME_DIR", data_root / "runtime-home")
            ),
            "HOST_KNOWLEDGE_BASES_DIR": str(
                env.get("HOST_KNOWLEDGE_BASES_DIR", data_root / "knowledge-bases")
            ),
            "HOST_RUNTIME_ASSERTION_DIR": str(
                env.get("HOST_RUNTIME_ASSERTION_DIR", data_root / "runtime-assertions")
            ),
            "HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": str(
                env.get(
                    "HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE",
                    data_root / "runtime-assertions" / "jwks.json",
                )
            ),
            "HOST_TURN_CONFIG_DIR": str(
                env.get("HOST_TURN_CONFIG_DIR", data_root / "turn-config")
            ),
            "HOST_TURN_SECRETS_DIR": str(
                env.get("HOST_TURN_SECRETS_DIR", data_root / "turn-secrets")
            ),
        }
    )
    return env


def ensure_host_storage_directories(repo_root: Path, env: dict[str, str]) -> None:
    host_knowledge_bases_dir = Path(env["HOST_KNOWLEDGE_BASES_DIR"])
    if not host_knowledge_bases_dir.is_absolute():
        host_knowledge_bases_dir = (repo_root / host_knowledge_bases_dir).resolve()
    host_runtime_assertion_dir = Path(env["HOST_RUNTIME_ASSERTION_DIR"])
    if not host_runtime_assertion_dir.is_absolute():
        host_runtime_assertion_dir = (repo_root / host_runtime_assertion_dir).resolve()

    host_knowledge_bases_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(host_knowledge_bases_dir, 0o770)
    host_runtime_assertion_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(host_runtime_assertion_dir, 0o700)
    for variable_name in ("HOST_TURN_CONFIG_DIR", "HOST_TURN_SECRETS_DIR"):
        turn_dir = Path(env[variable_name])
        if not turn_dir.is_absolute():
            turn_dir = (repo_root / turn_dir).resolve()
        turn_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(turn_dir, 0o700)
    if hasattr(os, "chown"):
        try:
            os.chown(host_knowledge_bases_dir, 1000, 1000)
        except PermissionError:
            print_warning(
                f"無法將 {host_knowledge_bases_dir} chown 為 1000:1000，保留現有擁有者。"
            )


def list_workspace_containers(repo_root: Path) -> list[DockerContainer]:
    result = run_command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=aileron.workspace_id",
            "--filter",
            "label=aileron.workload",
            "--format",
            '{{.ID}}\t{{.Names}}\t{{.Label "aileron.workspace_id"}}\t{{.Label "aileron.workload"}}',
        ],
        cwd=repo_root,
    )
    containers: list[DockerContainer] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        container_id, name, workspace_id, workload = parts
        expected_prefix = WORKSPACE_CONTAINER_PREFIXES.get(workload)
        if not workspace_id or expected_prefix is None or not name.startswith(
            expected_prefix
        ):
            continue
        containers.append(
            DockerContainer(
                container_id=container_id,
                name=name,
                workspace_id=workspace_id,
                workload=workload,
            )
        )
    return containers


def stop_and_remove_containers(
    containers: list[DockerContainer], repo_root: Path
) -> int:
    if not containers:
        return 0
    container_ids = [container.container_id for container in containers]
    print_info("停止動態 workspace 容器...")
    stop_result = run_command(
        ["docker", "stop", *container_ids], cwd=repo_root, check=False
    )
    require_command_success(stop_result, action="停止動態 workspace 容器")
    print_info("刪除動態 workspace 容器...")
    remove_result = run_command(
        ["docker", "rm", "-f", *container_ids], cwd=repo_root, check=False
    )
    require_command_success(remove_result, action="刪除動態 workspace 容器")
    return len(container_ids)


def compose_down(repo_root: Path, *, env: dict[str, str] | None = None) -> None:
    compose_file = repo_root / "docker-compose.yml"
    if not compose_file.is_file():
        print_warning("未找到 docker-compose.yml，跳過 compose down。")
        return
    print_info("停止 docker compose 服務...")
    stream_command(
        ["docker", "compose", "down", "--remove-orphans"],
        cwd=repo_root,
        env=env,
        action="docker compose down",
    )
    print_success("docker compose 服務已停止")


def build_local_images(repo_root: Path, *, env: dict[str, str]) -> None:
    """Build and load every image required by the local final stack."""

    bake_file = repo_root / BAKE_FILE
    if not bake_file.is_file():
        raise OpsError(f"找不到 Docker Bake 設定檔: {bake_file}")
    print_info("使用 Docker Bake 建置本機完整映像...")
    stream_command(
        [
            "docker",
            "buildx",
            "bake",
            "--load",
            "local",
        ],
        cwd=repo_root,
        env=env,
        action="docker buildx bake local",
    )
    print_success("本機完整映像已建置並載入 Docker image store")


def compose_up(
    repo_root: Path,
    *,
    detach: bool,
    env: dict[str, str],
) -> None:
    compose_file = repo_root / "docker-compose.yml"
    if not compose_file.is_file():
        raise OpsError("未找到 docker-compose.yml，無法啟動 compose stack。")
    ensure_host_storage_directories(repo_root, env)
    command = ["docker", "compose", "up", "--remove-orphans", "--no-build"]
    if detach:
        command.append("-d")
    print_info("啟動 docker compose 服務...")
    stream_command(command, cwd=repo_root, env=env, action="docker compose up")
    print_success("docker compose 啟動命令已送出")


def get_test_service_config(service_type: str) -> TestServiceConfig:
    try:
        return TEST_SERVICE_CONFIGS[service_type]
    except KeyError as exc:
        raise OpsError(f"不支援的測試服務類型: {service_type}") from exc


def find_container_id_by_ports(
    repo_root: Path, *, port: int, internal_port: int
) -> str | None:
    result = run_command(
        ["docker", "ps", "--format", "{{.ID}}\t{{.Ports}}"],
        cwd=repo_root,
        check=False,
    )
    expected = f"{port}->{internal_port}"
    for line in result.stdout.splitlines():
        container_id, _, ports = line.partition("\t")
        if expected in ports:
            return container_id.strip()
    return None


def assert_container_running(repo_root: Path, container_id: str) -> None:
    inspect_result = run_command(
        ["docker", "inspect", "-f", "{{.State.Status}}", container_id],
        cwd=repo_root,
        check=False,
    )
    if inspect_result.returncode != 0:
        raise OpsError(f"容器 {container_id} 不存在或無法訪問")
    status = inspect_result.stdout.strip()
    if status != "running":
        raise OpsError(f"容器 {container_id} 未在運行（狀態：{status or 'unknown'}）")


def container_has_path(repo_root: Path, container_id: str, path: str) -> bool:
    result = run_command(
        ["docker", "exec", container_id, "test", "-d", path],
        cwd=repo_root,
        check=False,
    )
    return result.returncode == 0


def ensure_container_test_environment(
    repo_root: Path,
    container_id: str,
    config: TestServiceConfig,
) -> bool:
    print_info("步驟 2：檢查測試環境")
    is_mounted = container_has_path(repo_root, container_id, config.container_test_dir)
    if is_mounted:
        print_success(f"容器內已存在測試目錄：{config.container_test_dir}")
    else:
        print_warning("容器內不存在測試目錄，需要複製")
        local_tests_dir = repo_root / config.script_dir / "tests"
        if not local_tests_dir.is_dir():
            raise OpsError(f"本地測試目錄不存在：{local_tests_dir}")
        target_parent = str(Path(config.container_test_dir).parent)
        print_info(f"從 {local_tests_dir} 複製到容器...")
        result = run_command(
            ["docker", "cp", str(local_tests_dir), f"{container_id}:{target_parent}/"],
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            raise OpsError("測試目錄複製失敗")
        print_success("測試目錄複製成功")

    print_info("步驟 3：驗證測試執行環境")
    check_result = run_command(
        ["docker", "exec", container_id, *config.python_check_command],
        cwd=repo_root,
        check=False,
    )
    if check_result.returncode != 0:
        raise OpsError(
            f"容器內缺少測試執行環境：{' '.join(config.python_check_command)}"
        )

    if config.service_type == "manager":
        pyproject_result = run_command(
            [
                "docker",
                "exec",
                container_id,
                "test",
                "-f",
                f"{config.work_dir}/pyproject.toml",
            ],
            cwd=repo_root,
            check=False,
        )
        if pyproject_result.returncode != 0:
            print_warning("容器內找不到 pyproject.toml，可能影響 uv 執行")

    print_success("測試環境檢查通過")
    return is_mounted


def build_pytest_command(
    config: TestServiceConfig, test_path: str, extra_args: list[str]
) -> str:
    command = f"{config.python_test_command} {test_path}"
    if extra_args:
        command = f"{command} {' '.join(extra_args)}"
    return f"{command} --tb=short"


def run_test_command(
    repo_root: Path,
    *,
    service_type: str,
    container_id: str | None,
    test_path: str | None,
    extra_args: list[str],
) -> int:
    ensure_docker_available()
    config = get_test_service_config(service_type)

    print_info(f"開始執行 {config.service_name} 測試")
    resolved_container_id = container_id
    if not resolved_container_id:
        print_info(f"自動尋找 {config.service_name} 容器...")
        resolved_container_id = find_container_id_by_ports(
            repo_root,
            port=config.port,
            internal_port=config.internal_port,
        )
        if not resolved_container_id:
            raise OpsError(
                f"找不到運行中的 {config.service_name} 容器（端口 {config.port}）"
            )
        print_success(f"自動找到容器：{resolved_container_id}")
    else:
        print_info(f"使用指定容器：{resolved_container_id}")

    assert_container_running(repo_root, resolved_container_id)
    effective_test_path = test_path or config.default_test_path
    is_mounted = ensure_container_test_environment(
        repo_root, resolved_container_id, config
    )

    print_info("步驟 4：執行測試")
    print_info(f"測試路徑：{effective_test_path}")
    if extra_args:
        print_info(f"額外參數：{' '.join(extra_args)}")

    pytest_command = build_pytest_command(config, effective_test_path, extra_args)
    start_time = time.monotonic()
    result = stream_command(
        [
            "docker",
            "exec",
            resolved_container_id,
            "bash",
            "-c",
            f"cd {config.work_dir} && {pytest_command}",
        ],
        cwd=repo_root,
        check=False,
        action="pytest in container",
    )
    duration = int(time.monotonic() - start_time)

    if result.returncode == 0:
        print_success("測試執行完成")
    else:
        print_warning("測試命令返回非零狀態，請檢查上方輸出")

    print_info(f"執行時間：{duration} 秒")

    if not is_mounted:
        print_info(
            f"提示：測試目錄已複製到容器內，如需清理可手動執行 docker exec {resolved_container_id} rm -rf {config.container_test_dir}"
        )

    return result.returncode


def list_named_resources(args: list[str], repo_root: Path) -> list[str]:
    result = run_command(args, cwd=repo_root, check=False)
    require_command_success(result, action="列出 Docker 資源")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remove_named_resources(
    label: str, names: list[str], remove_args: list[str], repo_root: Path
) -> int:
    if not names:
        print_info(f"沒有找到相關的 {label}")
        return 0
    print_info(f"刪除 {label}...")
    result = run_command(remove_args + names, cwd=repo_root, check=False)
    require_command_success(result, action=f"刪除 {label}")
    print_success(f"已清理 {len(names)} 個 {label}")
    return len(names)


def list_project_image_ids(repo_root: Path) -> list[str]:
    image_ids: list[str] = []
    for repo in PROJECT_IMAGE_REPOS:
        result = run_command(
            ["docker", "images", "--format", "{{.ID}}", repo],
            cwd=repo_root,
            check=False,
        )
        require_command_success(result, action="列出專案 Docker images")
        image_ids.extend(
            line.strip() for line in result.stdout.splitlines() if line.strip()
        )
    seen: dict[str, None] = {}
    for image_id in image_ids:
        seen.setdefault(image_id, None)
    return list(seen)


def clean_data_directories(repo_root: Path) -> int:
    cleaned = 0
    for relative_dir in DATA_DIRS:
        target_dir = repo_root / relative_dir
        if not target_dir.is_dir():
            continue
        print_info(f"清理目錄: {relative_dir}")
        for path in sorted(
            target_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True
        ):
            if path.is_file() and path.name not in PRESERVED_FILENAMES:
                path.unlink(missing_ok=True)
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        cleaned += 1
    if cleaned:
        print_success(f"已清理 {cleaned} 個 data 目錄")
    else:
        print_info("沒有找到 data 目錄")
    return cleaned


def list_data_residuals(repo_root: Path) -> list[Path]:
    residuals: list[Path] = []
    for relative_dir in DATA_DIRS:
        target_dir = repo_root / relative_dir
        if not target_dir.is_dir():
            continue
        for path in target_dir.rglob("*"):
            if path.is_dir():
                continue
            if path.is_file() and path.name in PRESERVED_FILENAMES:
                continue
            residuals.append(path)
    return residuals


def clean_temp_directories(repo_root: Path) -> int:
    temp_dirs = [
        repo_root / "workspace-runtime" / "tmp",
        Path("/tmp/workspaces"),
        Path("/tmp/runtime-home"),
    ]
    cleaned = 0
    for target_dir in temp_dirs:
        if not target_dir.exists():
            continue
        print_info(f"清理臨時目錄: {target_dir}")
        shutil.rmtree(target_dir, ignore_errors=True)
        cleaned += 1
    if cleaned:
        print_success("臨時文件清理完成")
    else:
        print_info("沒有找到需要清理的臨時文件")
    return cleaned


def full_reset(
    repo_root: Path,
    *,
    assume_yes: bool,
    remove_images: bool | None,
    prune: bool | None,
) -> int:
    ensure_docker_available()

    if not prompt_confirm(
        "警告：這將會刪除所有容器、資料庫資料、緩存資料和工作空間，確定要繼續嗎？",
        assume_yes=assume_yes,
    ):
        print_warning("操作已取消")
        return 1

    print_info("步驟 1: 清理動態 workspace 容器")
    workspace_containers = list_workspace_containers(repo_root)
    removed_count = stop_and_remove_containers(workspace_containers, repo_root)
    if removed_count:
        print_success(f"已清理 {removed_count} 個動態 workspace 容器")
    else:
        print_info("沒有找到動態 workspace 容器")

    print_info("步驟 2: 停止 docker compose 服務")
    compose_down(repo_root)

    print_info("步驟 3: 清理 volumes")
    volumes = list_named_resources(
        ["docker", "volume", "ls", "--filter", "name=aileron", "--format", "{{.Name}}"],
        repo_root,
    )
    remove_named_resources("volumes", volumes, ["docker", "volume", "rm"], repo_root)

    print_info("步驟 4: 清理 networks")
    networks = list_named_resources(
        ["docker", "network", "ls", "--filter", "name=aileron", "--format", "{{.ID}}"],
        repo_root,
    )
    remove_named_resources("networks", networks, ["docker", "network", "rm"], repo_root)

    print_info("步驟 5: 清理 Docker images")
    image_ids = list_project_image_ids(repo_root)
    should_remove_images = remove_images
    if should_remove_images is None:
        should_remove_images = prompt_confirm(
            "是否要刪除專案 Docker images？這需要重新構建。",
            assume_yes=assume_yes,
        )
    if image_ids and should_remove_images:
        image_result = run_command(
            ["docker", "rmi", "-f", *image_ids], cwd=repo_root, check=False
        )
        require_command_success(image_result, action="刪除專案 Docker images")
        print_success(f"已清理 {len(image_ids)} 個 Docker images")
    elif image_ids:
        print_info("跳過 Docker images 清理")
    else:
        print_info("沒有找到相關的 Docker images")

    print_info("步驟 6: 清理 data 目錄容器產生檔案")
    clean_data_directories(repo_root)

    print_info("步驟 7: 清理臨時文件")
    clean_temp_directories(repo_root)

    print_info("步驟 8: Docker 系統清理")
    should_prune = prune
    if should_prune is None:
        should_prune = prompt_confirm(
            "是否要執行 Docker 系統清理（清理未使用的容器、網路、images 等）？",
            assume_yes=assume_yes,
        )
    if should_prune:
        prune_result = run_command(
            ["docker", "system", "prune", "-f", "--volumes"], cwd=repo_root, check=False
        )
        require_command_success(prune_result, action="Docker 系統清理")
        print_success("Docker 系統清理完成")
    else:
        print_info("跳過 Docker 系統清理")

    remaining_containers = list_workspace_containers(repo_root)
    if remaining_containers:
        names = ", ".join(container.name for container in remaining_containers)
        raise OpsError(f"動態 workspace 容器仍有殘留: {names}")
    data_residuals = list_data_residuals(repo_root)
    if data_residuals:
        paths = ", ".join(str(path.relative_to(repo_root)) for path in data_residuals)
        raise OpsError(f"必要清理資料仍有殘留: {paths}")

    print()
    print_success("清理完成")
    print("  - 所有動態 workspace 容器已清理")
    print("  - docker compose 服務已停止")
    print("  - 資料庫和緩存資料已清除")
    print("  - Docker volumes 和 networks 已清理")
    print("  - data 目錄容器產生檔案已清理")
    print("  - 臨時文件已清理")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aileron host-side Docker operations CLI",
        epilog=(
            "常用範例:\n"
            "  python scripts/dev/docker/ops.py up                 # Start from existing local images\n"
            "  python scripts/dev/docker/ops.py up --build         # Build all images with Bake before startup\n"
            "  python scripts/dev/docker/ops.py down\n"
            "  python scripts/dev/docker/ops.py full-reset --yes --keep-images --no-prune\n"
            "  python scripts/dev/docker/ops.py test manager container-id tests/integration/auth -v\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="Repository root path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser(
        "up",
        help="Start docker compose stack",
        description=(
            "啟動 Aileron Docker Compose stack。\n"
            "預設沿用本地既有 image；--build 會先執行 Docker Bake local group。"
        ),
    )
    up_parser.add_argument(
        "--build",
        action="store_true",
        help="啟動前以 docker buildx bake --load local 建置完整本機映像",
    )
    up_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run docker compose up in foreground mode",
    )

    down_parser = subparsers.add_parser(
        "down",
        help="Stop docker compose stack",
        description="停止 Aileron Docker Compose stack。",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="Run container-based tests",
        description="Run container-based tests in an existing workspace-manager container.",
    )
    test_parser.add_argument(
        "service_type", choices=sorted(TEST_SERVICE_CONFIGS), help="Test service type"
    )
    test_parser.add_argument(
        "container_id", nargs="?", help="Optional container ID or name"
    )
    test_parser.add_argument(
        "test_path", nargs="?", help="Optional test path inside the project"
    )

    full_reset_parser = subparsers.add_parser(
        "full-reset",
        help="Full local reset",
        description="執行完整清理，包含 compose stack、動態 workspace、volumes、networks 與 data 目錄。",
    )
    full_reset_parser.add_argument(
        "--yes", action="store_true", help="Skip confirmation prompts"
    )
    full_reset_parser.add_argument(
        "--remove-images",
        dest="remove_images",
        action="store_true",
        help="Force project image cleanup",
    )
    full_reset_parser.add_argument(
        "--keep-images",
        dest="remove_images",
        action="store_false",
        help="Skip project image cleanup",
    )
    full_reset_parser.add_argument(
        "--prune",
        dest="prune",
        action="store_true",
        help="Force docker system prune",
    )
    full_reset_parser.add_argument(
        "--no-prune",
        dest="prune",
        action="store_false",
        help="Skip docker system prune",
    )
    full_reset_parser.set_defaults(remove_images=None, prune=None)

    return parser


def main() -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.command != "test" and unknown:
            raise OpsError(f"不支援的額外參數: {' '.join(unknown)}")
        if args.command == "up":
            ensure_docker_available()
            env = build_compose_env()
            if args.build:
                build_local_images(repo_root, env=env)
            compose_up(
                repo_root,
                detach=not args.foreground,
                env=env,
            )
            return 0
        if args.command == "down":
            ensure_docker_available()
            compose_down(repo_root, env=os.environ.copy())
            return 0
        if args.command == "full-reset":
            return full_reset(
                repo_root,
                assume_yes=args.yes,
                remove_images=args.remove_images,
                prune=args.prune,
            )
        if args.command == "test":
            return run_test_command(
                repo_root,
                service_type=args.service_type,
                container_id=args.container_id,
                test_path=args.test_path,
                extra_args=unknown,
            )
        raise OpsError(f"不支援的命令: {args.command}")
    except OpsError as exc:
        print_error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
