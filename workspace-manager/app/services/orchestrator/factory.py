from typing import Type
from .base import ContainerOrchestrator
from .docker_orchestrator import DockerOrchestrator
from .k8s_orchestrator import KubernetesOrchestrator
from ...config.settings import get_settings

class OrchestratorFactory:
    """Container orchestrator factory"""

    _orchestrators = {
        "docker": DockerOrchestrator,
        "kubernetes": KubernetesOrchestrator,
    }

    @classmethod
    def get_orchestrator(cls) -> ContainerOrchestrator:
        """Get orchestrator based on environment variable"""
        settings = get_settings()
        # Default to docker if not set, though settings should handle default
        runtime_type = getattr(settings, "RUNTIME_PROVISIONER", "docker").lower()

        orchestrator_class = cls._orchestrators.get(runtime_type)
        if not orchestrator_class:
            raise ValueError(f"Unknown orchestrator: {runtime_type}")

        return orchestrator_class(settings)
