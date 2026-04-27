"""Internal API module - for internal calls by workspace-manager"""

from __future__ import annotations

from .router import router
from .template_install_models import (
    ClaudeMdInstallRequest,
    ClaudeMdInstallResponse,
    HooksInstallRequest,
    HooksInstallResponse,
    McpInstallRequest,
    McpInstallResponse,
    ScriptsInstallRequest,
    ScriptsInstallResponse,
    SlashCommandInstallRequest,
    SlashCommandInstallResponse,
    SubagentInstallRequest,
    SubagentInstallResponse,
    TemplateInstallRequest,
    TemplateInstallResponse,
)
from .template_install_service import TemplateInstallService

__all__ = [
    "router",
    # Template Install Models
    "SlashCommandInstallRequest",
    "SlashCommandInstallResponse",
    "SubagentInstallRequest",
    "SubagentInstallResponse",
    "ClaudeMdInstallRequest",
    "ClaudeMdInstallResponse",
    "McpInstallRequest",
    "McpInstallResponse",
    "HooksInstallRequest",
    "HooksInstallResponse",
    "ScriptsInstallRequest",
    "ScriptsInstallResponse",
    "TemplateInstallRequest",
    "TemplateInstallResponse",
    # Services
    "TemplateInstallService",
]