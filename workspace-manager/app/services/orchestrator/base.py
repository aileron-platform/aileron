from abc import ABC, abstractmethod
from typing import Optional, List, Any
from .models import RuntimeInfo, RuntimeStatus, RuntimeContext, ResourceRequirements

class OrchestratorException(Exception):
    """Base class for all orchestrator exceptions"""
    pass

class ContainerNotFoundError(OrchestratorException):
    """Container/Pod does not exist"""
    pass

class ContainerCreationError(OrchestratorException):
    """Container/Pod creation failed"""
    pass

class ContainerDeletionError(OrchestratorException):
    """Container/Pod DeleteFailed"""
    pass

class NetworkConfigError(OrchestratorException):
    """Network configuration error"""
    pass

class VolumeError(OrchestratorException):
    """Volume mount or operation error"""
    pass

class ResourceUpdateError(OrchestratorException):
    """Resource update failed"""
    pass

class ImagePullError(OrchestratorException):
    """Image pull failed"""
    pass

class ContainerOrchestrator(ABC):
    """Container orchestration abstract base class"""

    @abstractmethod
    def create_workspace_runtime(
        self,
        workspace: Any,  # Avoid circular import, pass Workspace object
        context: RuntimeContext
    ) -> RuntimeInfo:
        """Create workspace runtime environment"""
        pass

    def create_chrome_runtime(
        self,
        workspace: Any,
        context: RuntimeContext
    ) -> RuntimeInfo:
        """Create Chrome browser container (optional implementation)"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support Chrome runtime")

    def create_canvas_runtime(
        self,
        workspace: Any,
        context: RuntimeContext
    ) -> RuntimeInfo:
        """Create canvas container (optional implementation)"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support Canvas runtime")

    @abstractmethod
    def delete_workspace_runtime(self, workspace_id: str) -> bool:
        """Delete workspace runtime Environment"""
        pass

    @abstractmethod
    def get_runtime_status(self, workspace_id: str) -> RuntimeStatus:
        """Get runtime Status"""
        pass

    @abstractmethod
    def get_runtime_logs(
        self,
        workspace_id: str,
        container: Optional[str] = None,
        tail: int = 100,
        timestamps: bool = False
    ) -> str:
        """Get runtime log"""
        pass

    @abstractmethod
    def update_runtime_resources(
        self,
        workspace_id: str,
        resources: ResourceRequirements
    ) -> bool:
        """Update runtime resource configuration"""
        pass
