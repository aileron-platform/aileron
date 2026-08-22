from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/test/compose-e2e/run.sh"
REVISION = "1" * 40
SOURCE_REPOSITORIES = {
    "ailerondocker/workspace-runtime-base-lite",
    "ailerondocker/workspace-runtime",
    "ailerondocker/workspace-chrome",
    "ailerondocker/workspace-canvas",
    "ailerondocker/workspace-manager",
    "ailerondocker/workspace-ui",
    "ailerondocker/workspace-operator",
    "ailerondocker/platform-coturn",
    "ailerondocker/platform-keycloak",
}
SOURCE_IMAGE = re.compile(
    rf"^({'|'.join(re.escape(item) for item in sorted(SOURCE_REPOSITORIES))})"
    rf":acceptance-{REVISION}-[0-9a-f]{{8}}$"
)


FAKE_DOCKER = r"""
#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
import re
import sys
from pathlib import Path


args = sys.argv[1:]
state = Path(os.environ["FAKE_DOCKER_STATE"])
state.mkdir(parents=True, exist_ok=True)
with (state / "calls.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args, separators=(",", ":")) + "\n")

revision = os.environ["COMPOSE_E2E_SOURCE_REVISION"]
source_image_pattern = re.compile(
    rf"^ailerondocker/(workspace-runtime-base-lite|workspace-runtime|workspace-chrome|workspace-canvas|workspace-manager|workspace-ui|workspace-operator|platform-coturn|platform-keycloak):acceptance-{revision}-[0-9a-f]{{8}}$"
)
preexisting_repository = os.environ.get("FAKE_PREEXISTING_REPOSITORY", "")
referenced_image = os.environ.get("FAKE_REFERENCED_IMAGE", "")
stale_project = os.environ.get("FAKE_STALE_PROJECT", "")
scenario = os.environ.get("FAKE_DOCKER_SCENARIO", "success")
dynamic_container_id = "d" * 64
dynamic_marker = state / "dynamic-container"
dynamic_project_file = state / "dynamic-project"
removed_images_file = state / "removed-images"
builders_file = state / "builders"
built_images_file = state / "built-images.json"


def option_value(name: str) -> str:
    index = args.index(name)
    return args[index + 1]


def project_marker(project: str, suffix: str) -> Path:
    return state / f"{project}.{suffix}"


def compose_project() -> str:
    return option_value("-p")


def project_from_filter() -> str:
    if "--filter" not in args:
        return ""
    value = option_value("--filter")
    prefix = "label=com.docker.compose.project="
    return value.removeprefix(prefix) if value.startswith(prefix) else ""


def project_has_residual(project: str) -> bool:
    if project == stale_project:
        return not project_marker(project, "clean").exists()
    if scenario in {"execution_failure", "execution_failure_dynamic"}:
        return project_marker(project, "started").exists() and not project_marker(
            project, "clean"
        ).exists()
    return scenario == "residual" and project_marker(project, "down-attempted").exists()


def source_image_exists(image: str) -> bool:
    if not source_image_pattern.fullmatch(image):
        return False
    removed = (
        set(removed_images_file.read_text(encoding="utf-8").splitlines())
        if removed_images_file.exists()
        else set()
    )
    if image in removed:
        return False
    repository = image.split(":", maxsplit=1)[0]
    built = (
        json.loads(built_images_file.read_text(encoding="utf-8"))
        if built_images_file.exists()
        else {}
    )
    return repository == preexisting_repository or image in built


def built_image_owner(image: str) -> str:
    if not built_images_file.exists():
        return ""
    return json.loads(built_images_file.read_text(encoding="utf-8")).get(image, "")


def image_id(image: str) -> str:
    return "sha256:" + hashlib.sha256(image.encode()).hexdigest()


def builders() -> set[str]:
    if not builders_file.exists():
        return set()
    return set(builders_file.read_text(encoding="utf-8").splitlines())


def write_builders(items: set[str]) -> None:
    builders_file.write_text("\n".join(sorted(items)) + ("\n" if items else ""), encoding="utf-8")


if args == ["info"]:
    raise SystemExit(0)

if args[:2] == ["compose", "version"] or args[:2] == ["buildx", "version"]:
    print("fake docker version")
    raise SystemExit(0)

if args[:2] == ["buildx", "ls"]:
    if scenario == "builder_query_failure":
        raise SystemExit(76)
    print("\n".join(sorted(builders())))
    raise SystemExit(0)

if args[:2] == ["buildx", "create"]:
    builder_name = option_value("--name")
    current = builders()
    current.add(builder_name)
    write_builders(current)
    print(builder_name)
    raise SystemExit(0)

if args[:2] == ["buildx", "rm"]:
    builder_name = args[-1]
    if scenario == "builder_rm_failure":
        raise SystemExit(77)
    current = builders()
    current.discard(builder_name)
    write_builders(current)
    raise SystemExit(0)

if args[:2] == ["buildx", "bake"]:
    owner = ""
    for item in args:
        marker = "*.labels.io.aileron.compose-e2e.run="
        if marker in item:
            owner = item.split(marker, maxsplit=1)[1]
    (state / "build-owner").write_text(owner, encoding="utf-8")
    suffix = owner.rsplit("-", maxsplit=1)[-1]
    source_tag = f"acceptance-{revision}-{suffix}"
    repositories = {
        "ailerondocker/workspace-runtime-base-lite",
        "ailerondocker/workspace-runtime",
        "ailerondocker/workspace-chrome",
        "ailerondocker/workspace-canvas",
        "ailerondocker/workspace-manager",
        "ailerondocker/workspace-ui",
        "ailerondocker/workspace-operator",
        "ailerondocker/platform-coturn",
        "ailerondocker/platform-keycloak",
    }
    built = (
        json.loads(built_images_file.read_text(encoding="utf-8"))
        if built_images_file.exists()
        else {}
    )
    built.update({f"{repository}:{source_tag}": owner for repository in repositories})
    built_images_file.write_text(json.dumps(built, sort_keys=True), encoding="utf-8")
    raise SystemExit(0)

if args and args[0] == "compose":
    project = compose_project()
    if "up" in args and scenario in {"execution_failure", "execution_failure_dynamic"}:
        project_marker(project, "started").touch()
        raise SystemExit(82)
    if "down" in args:
        project_marker(project, "down-attempted").touch()
        if scenario == "residual" and project != stale_project:
            raise SystemExit(1)
        project_marker(project, "clean").touch()
        if scenario == "down_failure_absent":
            raise SystemExit(79)
        raise SystemExit(0)
    if "config" in args:
        if "--images" in args:
            built = (
                json.loads(built_images_file.read_text(encoding="utf-8"))
                if built_images_file.exists()
                else {}
            )
            compose_images = {
                image
                for image, owner in built.items()
                if owner == project
                if "/workspace-runtime-base-lite:" not in image
            }
            print("\n".join(sorted(compose_images)))
        else:
            print(f"name: {project}-network")
        raise SystemExit(0)
    if "logs" in args:
        if args[-1] == "workspace-manager":
            print("workspace-manager-final-diagnostic")
        else:
            print("all-services-diagnostic")
        raise SystemExit(0)
    if "ps" in args:
        raise SystemExit(0)

if args and args[0] == "ps":
    filter_value = option_value("--filter") if "--filter" in args else ""
    if filter_value.startswith("label=aileron.workspace_id="):
        if scenario == "dynamic_query_failure":
            raise SystemExit(72)
        if dynamic_marker.exists():
            print(dynamic_container_id)
        raise SystemExit(0)
    project = project_from_filter()
    if project:
        if scenario == "inventory_query_failure" and project_marker(
            project, "down-attempted"
        ).exists():
            raise SystemExit(74)
        if project_has_residual(project):
            print("c" * 64)
        raise SystemExit(0)
    if referenced_image:
        print("preexisting-container")
    raise SystemExit(0)

if args[:3] == ["volume", "ls", "-q"]:
    project = project_from_filter()
    if project_has_residual(project):
        print(f"{project}-volume")
    raise SystemExit(0)

if args[:2] == ["network", "ls"]:
    project = project_from_filter()
    if scenario == "network_query_failure" and project_marker(
        project, "down-attempted"
    ).exists():
        raise SystemExit(75)
    dynamic_project = (
        dynamic_project_file.read_text(encoding="utf-8")
        if dynamic_project_file.exists()
        else ""
    )
    if project_has_residual(project) or (
        dynamic_marker.exists() and project == dynamic_project
    ):
        print(f"{project}-network")
    raise SystemExit(0)

if args[:2] == ["network", "inspect"]:
    network = args[-1]
    project = network.removesuffix("-network")
    dynamic_project = (
        dynamic_project_file.read_text(encoding="utf-8")
        if dynamic_project_file.exists()
        else ""
    )
    exists = project_has_residual(project) or (
        dynamic_marker.exists() and project == dynamic_project
    )
    raise SystemExit(0 if exists else 1)

if args[:2] == ["image", "ls"]:
    if scenario == "image_query_failure":
        raise SystemExit(78)
    image = args[-1]
    exists = "@sha256:" in image or source_image_exists(image)
    if exists:
        print(image_id(image))
    raise SystemExit(0)

if args[:2] == ["image", "inspect"]:
    image = args[-1]
    exists = "@sha256:" in image or source_image_exists(image)
    if not exists:
        raise SystemExit(1)
    format_value = option_value("--format") if "--format" in args else ""
    if (
        "org.opencontainers.image.revision" in format_value
        and "io.aileron.compose-e2e.run" in format_value
    ):
        owner = built_image_owner(image)
        print(f"amd64 {revision} {owner}")
    elif "io.aileron.compose-e2e.run" in format_value:
        repository = image.split(":", maxsplit=1)[0]
        if repository == preexisting_repository and not built_image_owner(image):
            print("preexisting-owner")
        else:
            print(built_image_owner(image))
    elif "org.opencontainers.image.revision" in format_value:
        print(f"amd64 {revision}")
    elif ".Architecture" in format_value:
        print("amd64")
    raise SystemExit(0)

if args[:2] == ["image", "rm"]:
    image = args[-1]
    with removed_images_file.open("a", encoding="utf-8") as stream:
        stream.write(f"{image}\n")
    raise SystemExit(0)

if args[:2] == ["rm", "-f"] and args[2:] == [dynamic_container_id]:
    if scenario == "dynamic_rm_failure":
        raise SystemExit(73)
    dynamic_marker.unlink(missing_ok=True)
    raise SystemExit(0)

if args and args[0] == "logs" and args[-1] == dynamic_container_id:
    print("workspace-runtime-dynamic-log")
    raise SystemExit(0)

if args and args[0] == "run":
    if any(item.endswith("/render_compose.py") for item in args):
        output = Path(args[args.index("--output") + 1])
        network = args[args.index("--network-name") + 1]
        if scenario == "keycloak_secret_contract":
            keycloak_secret = (
                output.parent
                / "root/data/platform-secrets/keycloak-bootstrap-admin-password"
            )
            metadata = keycloak_secret.stat()
            if (
                metadata.st_uid != 1000
                or metadata.st_gid != 1000
                or metadata.st_mode & 0o777 != 0o400
            ):
                print(
                    "Keycloak bootstrap Secret is not restricted to uid/gid 1000",
                    file=sys.stderr,
                )
                raise SystemExit(80)
        output.write_text(
            f"services: {{}}\nnetworks:\n  aileron-network-dev:\n    name: {network}\n",
            encoding="utf-8",
        )
        if scenario in {
            "dynamic_rm_failure",
            "dynamic_query_failure",
            "execution_failure_dynamic",
        }:
            result_root = output.parent / "results"
            result_root.mkdir(exist_ok=True)
            workspace_id = result_root / "workspace-id"
            workspace_id.write_text(
                "00000000-0000-4000-8000-000000000123\n", encoding="utf-8"
            )
            workspace_id.chmod(0o600)
            dynamic_marker.touch()
            dynamic_project_file.write_text(
                network.removesuffix("-network"), encoding="utf-8"
            )
    raise SystemExit(0)

if args and args[0] == "inspect":
    format_value = ""
    if "--format" in args:
        format_value = option_value("--format")
    elif "-f" in args:
        format_value = option_value("-f")
    if "aileron.workload" in format_value and args[-1] == dynamic_container_id:
        print("runtime")
    elif ".Config.Image" in format_value and args[-1] == dynamic_container_id:
        dynamic_project = dynamic_project_file.read_text(encoding="utf-8")
        suffix = dynamic_project.rsplit("-", maxsplit=1)[-1]
        print(f"ailerondocker/workspace-runtime:acceptance-{revision}-{suffix}")
    elif ".State.Status" in format_value and args[-1] == dynamic_container_id:
        print("exited")
    elif ".State.ExitCode" in format_value and args[-1] == dynamic_container_id:
        print("42")
    elif ".Config.Image" in format_value:
        print(referenced_image)
    elif ".State.Running" in format_value:
        print("true")
    raise SystemExit(0)

print(f"unsupported fake docker call: {args}", file=sys.stderr)
raise SystemExit(98)
"""


@dataclass(frozen=True)
class RunnerResult:
    completed: subprocess.CompletedProcess[str]
    calls: list[list[str]]
    state_parent: Path


def _run_runner(
    tmp_path: Path,
    *,
    preflight_only: bool = True,
    scenario: str = "success",
    preexisting_repository: str = "",
    referenced_image: str = "",
    stale_project: str = "",
    state_parent_owner: int | None = None,
    state_parent_symlink: bool = False,
) -> RunnerResult:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(textwrap.dedent(FAKE_DOCKER).lstrip(), encoding="utf-8")
    fake_docker.chmod(0o755)
    fake_state = tmp_path / "fake-docker-state"
    state_parent = tmp_path / "compose-state"
    if state_parent_symlink:
        symlink_target = tmp_path / "attacker-owned-compose-state"
        symlink_target.mkdir()
        state_parent.symlink_to(symlink_target, target_is_directory=True)
    else:
        state_parent.mkdir(exist_ok=True)
    if state_parent_owner is not None:
        os.chown(state_parent.resolve(), state_parent_owner, state_parent_owner)
    if stale_project:
        stale_root = state_parent / "run-20260811010101-42-deadbeef-ABCDEF"
        stale_root.mkdir(mode=0o700)
        stale_files = {
            ".compose-project": f"{stale_project}\n",
            ".buildx-builder": f"{stale_project}-builder\n",
            ".initial-containers": "",
            ".owned-source-images": "",
            "compose.env": "COMPOSE_E2E_RECOVERY=1\n",
            "compose.yml": "services: {}\n",
        }
        for name, content in stale_files.items():
            path = stale_root / name
            path.write_text(content, encoding="utf-8")
            path.chmod(0o600)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "COMPOSE_E2E_HOST_REPO_ROOT": str(ROOT),
            "COMPOSE_E2E_SOURCE_REVISION": REVISION,
            "COMPOSE_E2E_STATE_PARENT": str(state_parent),
            "FAKE_DOCKER_STATE": str(fake_state),
            "FAKE_DOCKER_SCENARIO": scenario,
            "FAKE_PREEXISTING_REPOSITORY": preexisting_repository,
            "FAKE_REFERENCED_IMAGE": referenced_image,
            "FAKE_STALE_PROJECT": stale_project,
        }
    )
    command = ["sh", str(RUNNER)]
    if preflight_only:
        command.append("--preflight-only")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    call_file = fake_state / "calls.jsonl"
    calls = (
        [
            json.loads(line)
            for line in call_file.read_text(encoding="utf-8").splitlines()
        ]
        if call_file.exists()
        else []
    )
    return RunnerResult(completed=completed, calls=calls, state_parent=state_parent)


def _assert_success(result: RunnerResult) -> None:
    assert result.completed.returncode == 0, (
        f"stdout:\n{result.completed.stdout}\nstderr:\n{result.completed.stderr}"
    )


def _removed_images(result: RunnerResult) -> set[str]:
    return {
        call[2]
        for call in result.calls
        if len(call) == 3 and call[:2] == ["image", "rm"]
    }


def test_failure_diagnostics_finish_with_workspace_manager_logs() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    cleanup = source[
        source.index("cleanup() {") : source.index("trap cleanup EXIT HUP INT TERM")
    ]
    all_services = "--profile local-oidc logs --no-color --tail 200 >&2"
    manager_capture = (
        "--profile local-oidc logs --no-color --tail 200 workspace-manager 2>&1"
    )
    final_output = "printf '%s\\n' \"$manager_diagnostics\" >&2"

    assert all_services in cleanup
    assert manager_capture in cleanup
    assert final_output in cleanup
    assert cleanup.index(all_services) < cleanup.index(manager_capture)
    assert cleanup.index('rm -rf "$state_root"') < cleanup.index(final_output)
    assert cleanup.index('remove_owned_builder "$project"') < cleanup.index(
        final_output
    )
    assert cleanup.index(final_output) < cleanup.rindex(
        'if [ "$original_status" -ne 0 ]'
    )


def test_failed_execution_prints_manager_diagnostic_after_cleanup(
    tmp_path: Path,
) -> None:
    result = _run_runner(
        tmp_path,
        preflight_only=False,
        scenario="execution_failure",
    )

    assert result.completed.returncode != 0
    assert list(result.state_parent.glob("run-*")) == []
    assert result.completed.stderr.rstrip().endswith(
        "workspace-manager-final-diagnostic"
    )


def test_failed_execution_prints_dynamic_diagnostics_before_exact_cleanup(
    tmp_path: Path,
) -> None:
    result = _run_runner(
        tmp_path,
        preflight_only=False,
        scenario="execution_failure_dynamic",
    )

    assert result.completed.returncode != 0
    assert list(result.state_parent.glob("run-*")) == []
    assert "Final bounded dynamic Workspace diagnostics" in result.completed.stdout
    assert "Workspace runtime logs" in result.completed.stderr
    assert "state=exited exitCode=42 tail=200" in result.completed.stderr
    assert result.completed.stderr.rstrip().endswith("workspace-runtime-dynamic-log")
    log_call = ["logs", "--tail", "200", "d" * 64]
    remove_call = ["rm", "-f", "d" * 64]
    assert log_call in result.calls
    assert remove_call in result.calls
    assert result.calls.index(log_call) < result.calls.index(remove_call)


def test_exact_source_run_injects_all_dynamic_component_images() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for assignment in (
        "WORKSPACE_RUNTIME_IMAGE=ailerondocker/workspace-runtime:$source_tag",
        "WORKSPACE_BROWSER_IMAGE=ailerondocker/workspace-chrome:$source_tag",
        "WORKSPACE_CANVAS_IMAGE=ailerondocker/workspace-canvas:$source_tag",
    ):
        assert assignment in source


def test_non_root_or_symlink_state_parent_is_rejected(tmp_path: Path) -> None:
    non_root = _run_runner(tmp_path / "non-root", state_parent_owner=65534)
    linked = _run_runner(tmp_path / "linked", state_parent_symlink=True)

    assert non_root.completed.returncode != 0
    assert "state parent" in non_root.completed.stderr
    assert linked.completed.returncode != 0
    assert "state parent" in linked.completed.stderr
    assert not any(call[:2] == ["buildx", "bake"] for call in non_root.calls)
    assert not any(call[:2] == ["buildx", "bake"] for call in linked.calls)


def test_keycloak_secret_is_restricted_to_image_runtime_identity(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path, scenario="keycloak_secret_contract")

    _assert_success(result)


def test_dynamic_workspace_cleanup_failure_is_recovered_by_the_next_run(
    tmp_path: Path,
) -> None:
    first = _run_runner(tmp_path, scenario="dynamic_rm_failure")

    assert first.completed.returncode != 0
    retained = list(first.state_parent.glob("run-*"))
    assert len(retained) == 1
    workspace_id = retained[0] / "results/workspace-id"
    assert stat.S_IMODE(workspace_id.stat().st_mode) == 0o600

    recovered = _run_runner(tmp_path)

    _assert_success(recovered)
    assert list(recovered.state_parent.glob("run-*")) == []
    dynamic_rm_calls = [call for call in recovered.calls if call[:2] == ["rm", "-f"]]
    assert len(dynamic_rm_calls) >= 2


def test_docker_inventory_query_failure_preserves_recovery_state(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path, scenario="inventory_query_failure")

    assert result.completed.returncode != 0
    assert len(list(result.state_parent.glob("run-*"))) == 1
    assert "inventory" in result.completed.stderr.lower()


def test_successful_cleanup_removes_state_only_after_project_resources_are_zero(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path)

    _assert_success(result)
    assert list(result.state_parent.glob("run-*")) == []
    assert any("down" in call for call in result.calls)
    assert any(call[:2] == ["volume", "ls"] for call in result.calls)
    assert any(call[:2] == ["network", "ls"] for call in result.calls)


def test_down_failure_with_residual_resources_preserves_private_recovery_state(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path, scenario="residual")

    assert result.completed.returncode != 0
    state_roots = list(result.state_parent.glob("run-*"))
    assert len(state_roots) == 1
    state_root = state_roots[0]
    assert stat.S_IMODE(state_root.stat().st_mode) == 0o700
    for relative_path in ("compose.env", "compose.yml", ".compose-project"):
        metadata = state_root / relative_path
        assert metadata.is_file()
        assert stat.S_IMODE(metadata.stat().st_mode) == 0o600


def test_down_failure_converges_when_authoritative_inventory_is_empty(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path, scenario="down_failure_absent")

    _assert_success(result)
    assert list(result.state_parent.glob("run-*")) == []
    assert any("down" in call for call in result.calls)


def test_next_run_recovers_stale_project_before_deleting_its_state(
    tmp_path: Path,
) -> None:
    stale_project = "aileron-compose-e2e-20260811010101-42-deadbeef"
    result = _run_runner(tmp_path, stale_project=stale_project)

    _assert_success(result)
    assert list(result.state_parent.glob("run-*")) == []
    stale_down_calls = [
        call
        for call in result.calls
        if call and call[0] == "compose" and "down" in call and stale_project in call
    ]
    assert len(stale_down_calls) == 1
    stale_down = stale_down_calls[0]
    assert stale_down[stale_down.index("--env-file") + 1].endswith("/compose.env")
    assert stale_down[stale_down.index("-f") + 1].endswith("/compose.yml")


def test_run_unique_source_tag_collision_fails_before_build(tmp_path: Path) -> None:
    result = _run_runner(
        tmp_path,
        preexisting_repository="ailerondocker/workspace-runtime",
    )

    assert result.completed.returncode != 0
    assert "already exists" in result.completed.stderr
    assert not any(call[:2] == ["buildx", "bake"] for call in result.calls)


def test_cleanup_removes_only_the_nine_run_owned_exact_source_tags(
    tmp_path: Path,
) -> None:
    result = _run_runner(tmp_path)

    _assert_success(result)
    removed = _removed_images(result)
    assert len(removed) == 9
    assert {image.split(":", maxsplit=1)[0] for image in removed} == SOURCE_REPOSITORIES
    assert all(SOURCE_IMAGE.fullmatch(image) for image in removed)
    assert len({image.rsplit("-", maxsplit=1)[1] for image in removed}) == 1
    assert all("prune" not in call for call in result.calls)
    assert all("--force" not in call for call in result.calls)


def test_run_owned_pinned_builder_is_used_and_removed(tmp_path: Path) -> None:
    result = _run_runner(tmp_path)

    _assert_success(result)
    create_calls = [call for call in result.calls if call[:2] == ["buildx", "create"]]
    bake_calls = [call for call in result.calls if call[:2] == ["buildx", "bake"]]
    remove_calls = [call for call in result.calls if call[:2] == ["buildx", "rm"]]
    assert len(create_calls) == len(bake_calls) == len(remove_calls) == 1
    builder = create_calls[0][create_calls[0].index("--name") + 1]
    assert builder.endswith("-builder")
    assert bake_calls[0][bake_calls[0].index("--builder") + 1] == builder
    assert remove_calls[0] == ["buildx", "rm", builder]
    assert (
        "image=moby/buildkit:buildx-stable-1@sha256:"
        "2f5adac4ecd194d9f8c10b7b5d7bceb5186853db1b26e5abd3a657af0b7e26ec"
    ) in create_calls[0]


def test_builder_remove_failure_is_recovered_by_the_next_run(tmp_path: Path) -> None:
    first = _run_runner(tmp_path, scenario="builder_rm_failure")

    assert first.completed.returncode != 0
    assert len(list(first.state_parent.glob("run-*"))) == 1

    recovered = _run_runner(tmp_path)

    _assert_success(recovered)
    assert list(recovered.state_parent.glob("run-*")) == []
    builder_remove_calls = [
        call for call in recovered.calls if call[:2] == ["buildx", "rm"]
    ]
    assert len(builder_remove_calls) >= 2
