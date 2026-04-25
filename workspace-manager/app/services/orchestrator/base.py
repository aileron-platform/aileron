from abc import ABC, abstractmethod
from typing import Optional, List, Any
from .models import RuntimeInfo, RuntimeStatus, RuntimeContext, ResourceRequirements

class OrchestratorException(Exception):
    """所有編排器異常的基類"""
    pass

class ContainerNotFoundError(OrchestratorException):
    """容器/Pod 不存在"""
    pass

class ContainerCreationError(OrchestratorException):
    """容器/Pod 創建失敗"""
    pass

class ContainerDeletionError(OrchestratorException):
    """容器/Pod 刪除失敗"""
    pass

class NetworkConfigError(OrchestratorException):
    """網絡配置錯誤"""
    pass

class VolumeError(OrchestratorException):
    """Volume 掛載或操作錯誤"""
    pass

class ResourceUpdateError(OrchestratorException):
    """資源更新失敗"""
    pass

class ImagePullError(OrchestratorException):
    """鏡像拉取失敗"""
    pass

class ContainerOrchestrator(ABC):
    """容器編排抽象基類"""

    @abstractmethod
    def create_workspace_runtime(
        self,
        workspace: Any,  # Avoid circular import, pass Workspace object
        context: RuntimeContext
    ) -> RuntimeInfo:
        """創建 workspace runtime 環境"""
        pass

    def create_chrome_runtime(
        self,
        workspace: Any,
        context: RuntimeContext
    ) -> RuntimeInfo:
        """創建 Chrome browser 容器（可選實作）"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support Chrome runtime")

    def create_canvas_runtime(
        self,
        workspace: Any,
        context: RuntimeContext
    ) -> RuntimeInfo:
        """創建 Canvas 容器（可選實作）"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support Canvas runtime")

    @abstractmethod
    def delete_workspace_runtime(self, workspace_id: str) -> bool:
        """刪除 workspace runtime 環境"""
        pass

    @abstractmethod
    def get_runtime_status(self, workspace_id: str) -> RuntimeStatus:
        """獲取 runtime 狀態"""
        pass

    @abstractmethod
    def get_runtime_logs(
        self,
        workspace_id: str,
        container: Optional[str] = None,
        tail: int = 100,
        timestamps: bool = False
    ) -> str:
        """獲取 runtime 日誌"""
        pass

    @abstractmethod
    def update_runtime_resources(
        self,
        workspace_id: str,
        resources: ResourceRequirements
    ) -> bool:
        """更新 runtime 資源配置"""
        pass
