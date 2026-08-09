from app.config.settings import get_settings
from .base import ContainerOrchestrator
from .docker_orchestrator import DockerOrchestrator


class OrchestratorFactory:
    """Container orchestrator factory"""

    _orchestrators = {
        "docker": DockerOrchestrator,
    }

    @classmethod
    def get_orchestrator(cls, provisioner: str) -> ContainerOrchestrator:
        """Get the immutable provisioner selected for a Workspace."""
        settings = get_settings()
        runtime_type = provisioner.lower()

        orchestrator_class = cls._orchestrators.get(runtime_type)
        if not orchestrator_class:
            raise ValueError(f"Unknown orchestrator: {runtime_type}")

        return orchestrator_class(settings)
