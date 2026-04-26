"""Template installation related models"""

from typing import Optional

from pydantic import BaseModel, Field


class TemplateInstallRequest(BaseModel):
    """Template installation request"""

    template_id: str = Field(..., alias="templateId", description="Template ID")
    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class TemplateInstallItemResult(BaseModel):
    """Single installation result"""

    success: bool = Field(..., description="Whether successful")
    created: int = Field(default=0, description="Number created")
    updated: int = Field(default=0, description="Number updated")
    failed: int = Field(default=0, description="Number failed")


class TemplateInstallResults(BaseModel):
    """Template installation result details"""

    agentsMd: Optional[TemplateInstallItemResult] = Field(default=None, alias="agentsMd")
    commands: Optional[TemplateInstallItemResult] = Field(default=None, alias="commands")
    agents: Optional[TemplateInstallItemResult] = Field(default=None, alias="agents")
    mcp: Optional[TemplateInstallItemResult] = Field(default=None, alias="mcp")
    hooks: Optional[TemplateInstallItemResult] = Field(default=None, alias="hooks")
    scripts: Optional[TemplateInstallItemResult] = Field(default=None, alias="scripts")
    skills: Optional[TemplateInstallItemResult] = Field(default=None, alias="skills")

    model_config = {"populate_by_name": True}


class TemplateInstallResponse(BaseModel):
    """Template installation response"""

    success: bool = Field(..., description="Whether successful")
    message: str = Field(..., description="Message")
    templateId: str = Field(..., alias="templateId", description="Template ID")
    templateName: str = Field(..., alias="templateName", description="Template name")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: Optional[TemplateInstallResults] = Field(default=None, description="Installation result details")
    error: Optional[str] = Field(default=None, description="Error message")

    model_config = {"populate_by_name": True}
