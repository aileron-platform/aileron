"""Same-origin public URL projection for Workspace execution services."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class WorkspacePublicUrls:
    runtime: str
    browser: str
    canvas: str

    @classmethod
    def for_workspace(cls, workspace_id: str) -> "WorkspacePublicUrls":
        workspace_segment = quote(str(workspace_id), safe="")
        base_path = f"/workspaces/{workspace_segment}"
        return cls(
            runtime=f"{base_path}/runtime",
            browser=f"{base_path}/browser",
            canvas=f"{base_path}/canvas",
        )


__all__ = ["WorkspacePublicUrls"]
