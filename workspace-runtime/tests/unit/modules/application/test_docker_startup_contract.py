"""Docker-host Runtime startup performance contracts."""

import configparser
import re
from pathlib import Path


def _runtime_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_docker_startup_does_not_mutate_image_managed_dependencies() -> None:
    startup = (_runtime_root() / "start_services.sh").read_text(encoding="utf-8")

    assert "uv sync" not in startup
    assert "chown -R developer:developer /workspace-runtime/.venv" not in startup
    assert "chmod -R u+x /workspace-runtime/.venv" not in startup


def test_docker_startup_repairs_only_unwritable_mounts() -> None:
    startup = (_runtime_root() / "start_services.sh").read_text(encoding="utf-8")

    assert "ensure_developer_writable()" in startup
    assert 'runuser -u developer -- test -w "${path}"' in startup
    assert 'ensure_developer_writable "/workspace"' in startup
    assert 'ensure_developer_writable "${HOME}"' in startup
    assert "chown -R developer:developer /workspace /workspace-terminal" not in startup
    assert "chown -R developer:developer /workspace 2>/dev/null" not in startup


def test_docker_startup_repairs_all_fixed_runtime_user_roots() -> None:
    startup = (_runtime_root() / "start_services.sh").read_text(encoding="utf-8")

    for path in (
        "${CODEX_HOME}",
        "${HOME}/.codex-sessions",
        "${HOME}/.claude",
        "${NPM_CONFIG_PREFIX}",
        "${XDG_CONFIG_HOME}",
        "${XDG_DATA_HOME}",
        "${XDG_STATE_HOME}",
        "${UV_CACHE_DIR}",
        "${NPM_CONFIG_CACHE}",
    ):
        assert f'ensure_developer_writable "{path}"' in startup


def test_docker_startup_handoffs_root_only_runtime_secrets_to_developer() -> None:
    startup = (_runtime_root() / "start_services.sh").read_text(encoding="utf-8")

    assert "prepare_runtime_secret()" in startup
    assert "install -d -o developer -g developer -m 0700" in startup
    assert "install -o developer -g developer -m 0400" in startup
    assert "/run/aileron-runtime-secrets" in startup
    assert "AILERON_RUNTIME_DATABASE_CONNECTION_FILE" in startup
    assert "runtime-database-connection" in startup
    assert "AILERON_RUNTIME_CONTROL_TOKEN_FILE" in startup


def test_runtime_ready_message_is_emitted_by_health_probe() -> None:
    runtime_root = _runtime_root()
    startup = (runtime_root / "start_services.sh").read_text(encoding="utf-8")
    readiness = (runtime_root / "scripts" / "wait_for_runtime_ready.sh").read_text(
        encoding="utf-8"
    )

    assert "Workspace Runtime is ready" not in startup
    assert "curl --fail --silent --output /dev/null" in readiness
    assert "http://127.0.0.1:3002/health" in readiness
    assert "Workspace Runtime is ready" in readiness

    for config_name in ("supervisord.conf", "supervisord.dev.conf"):
        config = configparser.ConfigParser(interpolation=None)
        config.read(runtime_root / config_name)
        section = config["program:runtime-readiness"]
        assert (
            section["command"] == "/workspace-runtime/scripts/wait_for_runtime_ready.sh"
        )
        assert section["user"] == "developer"
        assert section["autorestart"] == "false"


def test_runtime_images_use_fast_bounded_healthchecks() -> None:
    dockerfile = (_runtime_root() / "Dockerfile").read_text(encoding="utf-8")
    healthchecks = re.findall(r"^HEALTHCHECK .+$", dockerfile, re.MULTILINE)

    assert len(healthchecks) == 3
    for healthcheck in healthchecks:
        assert "--interval=5s" in healthcheck
        assert "--timeout=5s" in healthcheck
        assert "--start-period=15s" in healthcheck
        assert "--retries=12" in healthcheck


def test_packaged_runtime_stages_do_not_recursively_chown_virtualenv() -> None:
    dockerfile = (_runtime_root() / "Dockerfile").read_text(encoding="utf-8")

    assert "chown -R developer:developer /workspace-runtime" not in dockerfile


def test_docker_host_image_installs_client_without_daemon_packages() -> None:
    dockerfile = (_runtime_root() / "Dockerfile").read_text(encoding="utf-8")

    assert "\n    docker-cli \\" in dockerfile
    assert "\n    docker-buildx \\" in dockerfile
    assert "\n    docker.io \\" not in dockerfile
