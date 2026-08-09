"""FastAPI dependencies owned by the Workspace module."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from .availability import WorkspaceAvailabilityService
from .browser_credential_access import WorkspaceBrowserCredentialService
from .firewall import WorkspaceFirewallService
from .lifecycle import WorkspaceLifecycleService
from .runtime.access import WorkspaceRuntimeAccessService
from .runtime.provisioning import RuntimeProvisionService
from .catalog import WorkspaceService
from .setup import WorkspaceSetupService


def get_workspace_service(db: Session = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(db)


def get_workspace_firewall_service(
    db: Session = Depends(get_db),
) -> WorkspaceFirewallService:
    return WorkspaceFirewallService(db)


def get_workspace_browser_credential_service(
    db: Session = Depends(get_db),
) -> WorkspaceBrowserCredentialService:
    return WorkspaceBrowserCredentialService(db)


def get_workspace_setup_service(
    db: Session = Depends(get_db),
) -> WorkspaceSetupService:
    return WorkspaceSetupService(db)


def get_runtime_provision_service(
    db: Session = Depends(get_db),
) -> RuntimeProvisionService:
    return RuntimeProvisionService(db)


def get_workspace_runtime_access_service(
    db: Session = Depends(get_db),
) -> WorkspaceRuntimeAccessService:
    return WorkspaceRuntimeAccessService(db)


def get_workspace_availability_service(
    db: Session = Depends(get_db),
) -> WorkspaceAvailabilityService:
    return WorkspaceAvailabilityService(db)


def get_workspace_lifecycle_service(
    db: Session = Depends(get_db),
) -> WorkspaceLifecycleService:
    return WorkspaceLifecycleService(db)
