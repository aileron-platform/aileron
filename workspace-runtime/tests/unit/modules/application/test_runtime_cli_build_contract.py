"""Runtime CLI image reproducibility contract tests."""

import re
from pathlib import Path

import yaml


def _environment_names(environment: object) -> set[str]:
    if isinstance(environment, dict):
        return {str(name) for name in environment}
    if isinstance(environment, list):
        return {str(entry).split("=", 1)[0] for entry in environment}
    return set()


def _repo_file(runtime_root: Path, filename: str) -> Path:
    container_path = Path("/repo-root") / filename
    if container_path.exists():
        return container_path
    return runtime_root.parent / filename


def test_runtime_cli_versions_come_only_from_docker_bake() -> None:
    runtime_root = Path(__file__).resolve().parents[4]
    dockerfile = (runtime_root / "Dockerfile").read_text(encoding="utf-8")
    bake = _repo_file(runtime_root, "docker-bake.hcl").read_text(encoding="utf-8")

    for argument in (
        "CLAUDE_CLI_VERSION",
        "PLAYWRIGHT_CLI_VERSION",
        "CODEX_CLI_VERSION",
        "OPENCODE_VERSION",
        "OPENCODE_SHA256_AMD64",
        "OPENCODE_SHA256_ARM64",
    ):
        assert dockerfile.count(f"ARG {argument}") == 1
        assert f"ARG {argument}=" not in dockerfile
        assert re.search(
            rf'variable "{argument}" \{{.*?default\s*=\s*"[^"]+"', bake, re.S
        )
        assert re.search(rf"\b{argument}\s*=\s*{argument}\b", bake)

    assert "sha256sum --check --strict" in dockerfile
    assert "mkdir -p /opt/aileron/bin /opt/aileron/npm" in dockerfile
    assert "/opt/aileron/bin/opencode --version)" in dockerfile
    assert ')" = "${OPENCODE_VERSION}"' in dockerfile
    assert "NPM_CONFIG_PREFIX=/opt/aileron/npm" in dockerfile
    assert "/home/developer/.npm-global" not in dockerfile
    assert "/home/developer/.opencode" not in dockerfile
    assert "/home/developer/.cargo" not in dockerfile
    assert "$(opencode --version)" not in dockerfile
    assert "curl -fsSL https://opencode.ai/install | bash" not in dockerfile
    assert "ENV OPENCODE_DISABLE_AUTOUPDATE=1" in dockerfile
    assert "COPY workspace-runtime/.env" not in dockerfile


def test_runtime_image_tools_do_not_depend_on_persistent_home() -> None:
    runtime_root = Path(__file__).resolve().parents[4]
    dockerfile = (runtime_root / "Dockerfile").read_text(encoding="utf-8")
    lite_dockerfile = (runtime_root / "base-images" / "lite" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "UV_UNMANAGED_INSTALL=/usr/local/bin" in lite_dockerfile
    assert "uv tool update-shell" not in lite_dockerfile
    assert "find /home/developer -mindepth 1" in lite_dockerfile
    assert 'tar -xzf "${archive}" -C /opt/aileron/bin opencode' in dockerfile
    assert "NPM_CONFIG_PREFIX=/opt/aileron/npm" in dockerfile
    assert "UV_CACHE_DIR=/tmp/uv-cache uv sync" in dockerfile
    assert "rm -f /usr/local/bin/install-npm-global.sh" in dockerfile
    assert "verification_home" in dockerfile
    assert "find /home/developer -mindepth 1" in dockerfile
    assert "cp -a /home/developer" not in dockerfile


def test_docker_host_runtime_image_includes_firewall_cli() -> None:
    runtime_root = Path(__file__).resolve().parents[4]
    dockerfile = (runtime_root / "Dockerfile").read_text(encoding="utf-8")
    docker_host_stage = dockerfile.split(
        "FROM base-common AS base-devtools", maxsplit=1
    )[1].split("FROM base-devtools AS development", maxsplit=1)[0]

    assert "    iptables \\\n" in docker_host_stage


def test_runtime_compose_services_use_only_scoped_state_and_control_credentials() -> (
    None
):
    runtime_root = Path(__file__).resolve().parents[4]
    compose_paths = (
        Path("/repo-root/docker-compose.yml"),
        runtime_root / "docker-compose.test.yml",
    )
    checked_services = 0
    for compose_path in compose_paths:
        if not compose_path.exists():
            continue
        document = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        for service_name, service in document.get("services", {}).items():
            if not service_name.startswith("workspace-runtime"):
                continue
            checked_services += 1
            names = _environment_names(service.get("environment"))
            assert {
                "AILERON_RUNTIME_STATE_DATABASE_URL_FILE",
                "AILERON_RUNTIME_CONTROL_TOKEN_FILE",
                "AILERON_RUNTIME_INSTANCE_ID",
            } <= names
            assert names.isdisjoint({"DATABASE_URL", "REDIS_URL", "INTERNAL_API_TOKEN"})

    assert checked_services == 1
