from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import (
    ExecutionPlaneInfo,
    RuntimeContext,
    RuntimeInfo,
)


class OrchestratorException(Exception):
    """Base class for all orchestrator exceptions"""

    pass


class ContainerCreationError(OrchestratorException):
    """Container/Pod creation failed"""

    pass


class VolumeSourceValidationError(ContainerCreationError):
    """A fenced bind source changed or became unsafe before creation."""

    code = "KB_MOUNT_SOURCE_INVALID"


class WorkspaceRuntimeTerminationUnconfirmedError(ContainerCreationError):
    """The prior execution-plane generation could not be fenced."""

    code = "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"


class ContainerOrchestrator(ABC):
    """Container orchestration abstract base class"""

    @abstractmethod
    def create_workspace_runtime(
        self,
        workspace: Any,  # Avoid circular import, pass Workspace object
        context: RuntimeContext,
    ) -> RuntimeInfo:
        """Create workspace runtime environment"""
        pass

    def create_chrome_runtime(
        self, workspace: Any, context: RuntimeContext
    ) -> RuntimeInfo:
        """Create Chrome browser container (optional implementation)"""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support Chrome runtime"
        )

    def create_canvas_runtime(
        self, workspace: Any, context: RuntimeContext
    ) -> RuntimeInfo:
        """Create canvas container (optional implementation)"""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support Canvas runtime"
        )

    def recreate_workspace_execution_plane(
        self,
        *,
        workspace: Any,
        runtime_instance_id: str,
        runtime_context: RuntimeContext,
        browser_context: RuntimeContext,
        canvas_context: RuntimeContext,
        assert_claim: Any,
        browser_probe_context: RuntimeContext | None = None,
    ) -> ExecutionPlaneInfo:
        """Replace all workloads as one fenced generation."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support execution-plane replacement"
        )

    def replace_workspace_component(
        self,
        *,
        workspace: Any,
        component: str,
        context: RuntimeContext,
        assert_claim: Any,
        browser_probe_context: RuntimeContext | None = None,
    ) -> RuntimeInfo:
        """Replace one workload after fencing its persisted generation."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support component replacement"
        )

    def terminate_execution_plane(
        self,
        execution_plane: ExecutionPlaneInfo,
        *,
        assert_claim: Any,
    ) -> None:
        """Terminate one exact generation and prove every workload absent."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support execution-plane termination"
        )

    def terminate_workspace_execution_plane(
        self,
        workspace: Any,
        *,
        assert_claim: Any,
    ) -> None:
        """Terminate the exact persisted generation of one Workspace."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support persisted execution-plane termination"
        )

    def prove_workspace_execution_plane_absent(
        self,
        workspace: Any,
        *,
        assert_claim: Any,
    ) -> None:
        """Prove all deterministic workload identities are absent."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support absence proof"
        )

    def is_workspace_execution_plane_current(self, workspace: Any) -> bool:
        """Return whether every current-generation workload is observable."""

        raise NotImplementedError(
            f"{self.__class__.__name__} does not support execution-plane observation"
        )
