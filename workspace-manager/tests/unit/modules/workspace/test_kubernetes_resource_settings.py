import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_docker_settings_do_not_define_kubernetes_resource_defaults() -> None:
    settings = Settings(
        _env_file=None,
        RUNTIME_PROVISIONER="docker",
        RUNTIME_K8S_RUNTIME_RESOURCES=None,
        RUNTIME_K8S_BROWSER_RESOURCES=None,
        RUNTIME_K8S_CANVAS_RESOURCES=None,
    )

    assert settings.RUNTIME_K8S_RUNTIME_RESOURCES is None
    assert settings.RUNTIME_K8S_BROWSER_RESOURCES is None
    assert settings.RUNTIME_K8S_CANVAS_RESOURCES is None


def test_kubernetes_settings_require_all_deployment_injected_resources() -> None:
    with pytest.raises(
        ValidationError,
        match="Kubernetes component resources must be injected by deployment",
    ):
        Settings(
            _env_file=None,
            RUNTIME_PROVISIONER="kubernetes",
            RUNTIME_K8S_RUNTIME_RESOURCES=None,
            RUNTIME_K8S_BROWSER_RESOURCES=None,
            RUNTIME_K8S_CANVAS_RESOURCES=None,
        )


def test_kubernetes_settings_accept_complete_deployment_resource_profile() -> None:
    settings = Settings(
        _env_file=None,
        RUNTIME_PROVISIONER="kubernetes",
        RUNTIME_K8S_RUNTIME_RESOURCES={
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "3Gi"},
        },
        RUNTIME_K8S_BROWSER_RESOURCES={
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        RUNTIME_K8S_CANVAS_RESOURCES={
            "requests": {"cpu": "100m", "memory": "1Gi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
    )

    assert settings.RUNTIME_K8S_RUNTIME_RESOURCES["limits"]["memory"] == "3Gi"
    assert settings.RUNTIME_K8S_CANVAS_RESOURCES["requests"]["cpu"] == "100m"
