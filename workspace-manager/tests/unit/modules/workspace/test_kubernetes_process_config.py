from pathlib import Path


def test_kubernetes_supervisor_runs_without_fixed_user_or_system_writable_paths() -> (
    None
):
    manager_root = Path(__file__).resolve().parents[4]
    supervisor = (manager_root / "supervisord.kubernetes.conf").read_text(
        encoding="utf-8"
    )

    assert "user=" not in supervisor
    assert "/var/run" not in supervisor
    assert "/var/log" not in supervisor
    assert "celerybeat-schedule" in supervisor
    assert supervisor.count("[program:celery-beat]") == 1


def test_kubernetes_startup_precedes_rootful_dependency_sync() -> None:
    manager_root = Path(__file__).resolve().parents[4]
    startup = (manager_root / "scripts" / "start_services.sh").read_text(
        encoding="utf-8"
    )
    kubernetes_branch = startup.index(
        'if [ "${AILERON_EXECUTION_PROFILE:-docker}" = "kubernetes" ]'
    )
    kubernetes_exec = startup.index(
        "exec /usr/bin/supervisord -c /workspace-manager/supervisord.kubernetes.conf"
    )
    dependency_sync = startup.index("uv sync --dev")

    assert kubernetes_branch < kubernetes_exec < dependency_sync
    assert "chown" not in startup[kubernetes_branch:kubernetes_exec]


def test_kubernetes_image_exposes_the_standard_supervisor_config_name() -> None:
    manager_root = Path(__file__).resolve().parents[4]
    dockerfile = (manager_root / "Dockerfile").read_text(encoding="utf-8")

    assert (
        "ln -s /workspace-manager/supervisord.kubernetes.conf "
        "/workspace-manager/supervisord.conf"
    ) in dockerfile


def test_kubernetes_image_target_has_numeric_non_root_default_user() -> None:
    manager_root = Path(__file__).resolve().parents[4]
    dockerfile = (manager_root / "Dockerfile").read_text(encoding="utf-8")
    kubernetes_stage = dockerfile.rsplit(
        "\nFROM ${PYTHON_IMAGE} AS kubernetes\n", maxsplit=1
    )[1]

    assert "FROM production AS kubernetes" not in dockerfile
    assert "ARG PYTHON_IMAGE" in dockerfile
    assert "ARG NODE_IMAGE" in dockerfile
    assert "FROM ${PYTHON_IMAGE} AS kubernetes-python-builder" in dockerfile
    assert "FROM ${NODE_IMAGE} AS kubernetes-codex-builder" in dockerfile
    assert "USER 10001:10001" in kubernetes_stage
    assert "uv sync" not in kubernetes_stage
    assert "npm install" not in kubernetes_stage
    assert "docker.io" not in kubernetes_stage
    assert "redis-tools" not in kubernetes_stage
    assert "COPY workspace-manager/.env" not in dockerfile
    assert "chmod -R a+rX ./app ./scripts /packages" in kubernetes_stage


def test_kubernetes_healthcheck_requires_api_and_celery_worker() -> None:
    manager_root = Path(__file__).resolve().parents[4]
    healthcheck = (manager_root / "scripts" / "kubernetes_healthcheck.sh").read_text(
        encoding="utf-8"
    )

    assert "http://127.0.0.1:3001/health" in healthcheck
    assert "status celery-worker" in healthcheck
    assert "inspect ping" not in healthcheck
