"""Core module Version Control API tests - Matches actual API implementation"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock

from app.modules.version_control.service import GitService, VersionControlError
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.models import (
    VersionControlStatus,
    BranchInfo,
    ChangesResponse,
    FileChange,
    GitContext,
    GitContextListResponse,
)

from .helpers import override_dependency


class StubGitService:
    """Controllable GitService stub - Matches actual API implementation"""

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.is_repo = True
        self.current_branch = "main"
        self.ahead = 0
        self.behind = 0
        self.detached = False
        self.has_conflicts = False
        self.staged_files = []
        self.unstaged_files = []
        self.untracked_files = []
        self.branches = []
        self.commits = []

    def list_contexts(self, workspace_id: str) -> GitContextListResponse:
        return GitContextListResponse(
            activeContextId="primary",
            contexts=[
                GitContext(
                    id="primary",
                    kind="primary",
                    displayName="main",
                    repoPath=str(self.workspace_path),
                    branch=self.current_branch,
                    detached=self.detached,
                    headSha="abcdef1",
                    locked=False,
                    prunable=False,
                )
            ],
        )

    def get_status(self, workspace_id: str, context_id: Optional[str] = None) -> VersionControlStatus:
        """Get Git status"""
        return VersionControlStatus(
            branch=self.current_branch,
            ahead=self.ahead,
            behind=self.behind,
            detached=self.detached,
            hasConflicts=self.has_conflicts,
            stagedCount=len(self.staged_files),
            unstagedCount=len(self.unstaged_files),
            untrackedCount=len(self.untracked_files),
            lastFetchedAt=None,
        )

    def list_branches(
        self,
        workspace_id: str,
        include_remote: bool = False,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Get branch list"""
        branches = self.branches.copy()
        if search:
            branches = [b for b in branches if search.lower() in b["name"].lower()]

        return {"branches": branches}

    def checkout_branch(self, workspace_id: str, branch_name: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Switch branch"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        create = payload_dict.get("create", False)

        if create and branch_name not in [b["name"] for b in self.branches]:
            # Create new branch.
            new_branch = BranchInfo(
                name=branch_name,
                displayName=branch_name,
                isActive=True,
                isRemote=False,
                ahead=0,
                behind=0,
                lastCommit=None
            )
            self.branches.append(new_branch.model_dump())
            self.current_branch = branch_name
            return {
                "branch": branch_name,
                "created": True,
                "stashedChanges": None
            }
        else:
            # Switch existing branch
            existing = [b for b in self.branches if b["name"] == branch_name]
            if not existing:
                raise VersionControlError("Branch not found")

            # Update isActive status for all branches
            for branch in self.branches:
                branch["isActive"] = branch["name"] == branch_name
            self.current_branch = branch_name
            return {
                "branch": branch_name,
                "created": False,
                "stashedChanges": None
            }

    def get_changes(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 100,
        context_id: Optional[str] = None,
    ) -> ChangesResponse:
        """Get changes list"""
        staged_changes = [FileChange(
            name=path,
            path=path,
            status="M",
            type="modified",
            additions=5,
            deletions=2
        ) for path in self.staged_files]

        unstaged_changes = [FileChange(
            name=path,
            path=path,
            status="M",
            type="modified",
            additions=3,
            deletions=1
        ) for path in self.unstaged_files]

        untracked_changes = [FileChange(
            name=path,
            path=path,
            status="??",
            type="untracked",
            additions=0,
            deletions=0
        ) for path in self.untracked_files]

        return ChangesResponse(
            staged=staged_changes,
            unstaged=unstaged_changes,
            untracked=untracked_changes,
            untrackedTotal=len(self.untracked_files),
            untrackedPage=page,
            untrackedPageSize=page_size,
            untrackedHasMore=False
        )

    def stage(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Stage file"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        paths = payload_dict.get("paths", [])
        staged = []

        for path in paths:
            if path in self.untracked_files:
                self.untracked_files.remove(path)
                self.staged_files.append(path)
                staged.append(path)
            elif path in self.unstaged_files:
                self.unstaged_files.remove(path)
                self.staged_files.append(path)
                staged.append(path)

        return {
            "staged": staged,
            "unstaged": []
        }

    def unstage(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Unstage file"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        paths = payload_dict.get("paths", [])
        unstaged = []

        for path in paths:
            if path in self.staged_files:
                self.staged_files.remove(path)
                self.unstaged_files.append(path)
                unstaged.append(path)

        return {
            "unstaged": unstaged,
            "remainingStaged": len(self.staged_files)
        }

    def discard(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Discard changes"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        paths = payload_dict.get("paths", [])
        discarded = []

        for path in paths:
            if path in self.unstaged_files:
                self.unstaged_files.remove(path)
                discarded.append(path)

        return {
            "discarded": discarded,
            "warnings": []
        }

    def commit(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Create commit"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        message = payload_dict.get("message")
        if not message:
            raise VersionControlError("Commit message is required")

        if not self.staged_files:
            raise VersionControlError("No staged changes")

        commit_id = f"commit_{len(self.commits) + 1}"
        commit = {
            "id": commit_id,
            "message": message,
            "author": payload_dict.get("author", {"name": "Test User", "email": "test@example.com"}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.commits.append(commit)
        self.staged_files.clear()

        return {
            "commit": {
                "id": commit_id,
                "message": message,
                "author": commit["author"],
                "timestamp": commit["timestamp"],
                "additions": 0,
                "deletions": 0
            }
        }

    def list_commits(
        self,
        workspace_id: str,
        page: int = 1,
        page_size: int = 20,
        branch: Optional[str] = None,
        search: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Commits list"""
        start = (page - 1) * page_size
        end = start + page_size

        # Convert commit data structure to match API model
        items = []
        for commit in self.commits[start:end][::-1]:  # Newest first
            item = {
                "id": commit["id"],
                "message": commit["message"],
                "author": f"{commit['author']['name']} <{commit['author']['email']}>",  # String format
                "timestamp": int(datetime.now(timezone.utc).timestamp()),  # Integer format
                "branch": self.current_branch,
                "additions": 0,
                "deletions": 0,
                "files": 0
            }
            items.append(item)

        return {
            "page": page,
            "pageSize": page_size,
            "total": len(self.commits),
            "items": items
        }

    def get_commit(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> dict[str, Any]:
        """Get commit details"""
        for commit in self.commits:
            if commit["id"] == commit_id:
                return {
                    "id": commit["id"],
                    "message": commit["message"],
                    "author": commit["author"],
                    "timestamp": commit["timestamp"],
                    "branch": self.current_branch,
                    "stats": {"additions": 0, "deletions": 0, "files": 0},
                    "changes": []
                }
        raise VersionControlError("Commit not found")

    def get_commit_files(self, workspace_id: str, commit_id: str, context_id: Optional[str] = None) -> dict[str, Any]:
        """Get commit file diff"""
        # Simplified implementation
        return {
            "commitId": commit_id,
            "files": []
        }

    def push(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Push"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        return {
            "remote": payload_dict.get("remote", "origin"),
            "branch": self.current_branch,
            "updates": []
        }

    def pull(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Pull"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        return {
            "remote": payload_dict.get("remote", "origin"),
            "branch": self.current_branch,
            "fastForward": True,
            "commits": []
        }

    def fetch(self, workspace_id: str, payload, context_id: Optional[str] = None) -> dict[str, Any]:
        """Sync remote refs"""
        # Handle payload possibly being Pydantic model or dict
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        return {
            "remote": payload_dict.get("remote", "origin"),
            "fetchedRefs": []
        }

    def diff(
        self,
        workspace_id: str,
        path: str,
        base: Optional[str] = None,
        head: Optional[str] = None,
        context: int = 3,
        include_metadata: bool = False,
        context_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get diff"""
        return {
            "path": path,
            "base": base or "HEAD",
            "head": head or "working",
            "context": context,
            "patch": "@@ -1,3 +1,4 @@\n line 1\n+line 2\n line 3",
            "metadata": {"file": path} if include_metadata else None
        }

    def blob(
        self,
        workspace_id: str,
        path: str,
        revision: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Read file content"""
        import base64
        content = base64.b64encode(b"file content").decode()

        return {
            "path": path,
            "revision": revision or "HEAD",
            "encoding": "utf-8",
            "content": content,
            "isBase64": True
        }


def _get_git_service_stub():
    """Get GitService stub factory function"""
    workspace_path = Path("/tmp/workspace")
    return StubGitService(workspace_path)


# ============================================================================
# Tests
# ============================================================================


def test_vc_001_get_git_status_normal(client):
    """VC-001 Get normal Git status"""
    service = StubGitService(Path("/tmp/workspace"))
    service.current_branch = "main"
    service.staged_files = ["file1.txt"]
    service.untracked_files = ["file2.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["branch"] == "main"
    assert payload["stagedCount"] == 1
    assert payload["unstagedCount"] == 0
    assert payload["untrackedCount"] == 1
    assert payload["ahead"] == 0
    assert payload["behind"] == 0


def test_vc_002_list_branches_with_remote(client):
    """VC-002 List local and remote branches"""
    service = StubGitService(Path("/tmp/workspace"))

    # Set branch data
    service.branches = [
        {
            "name": "main",
            "displayName": "main",
            "isActive": True,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        },
        {
            "name": "origin/main",
            "displayName": "origin/main",
            "isActive": False,
            "isRemote": True,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        }
    ]

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/branches?includeRemote=true")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["branches"]) == 2
    remote_branches = [b for b in payload["branches"] if b["isRemote"]]
    assert len(remote_branches) == 1


def test_vc_003_branches_search_filter(client):
    """VC-003 Filter branches by keyword"""
    service = StubGitService(Path("/tmp/workspace"))

    service.branches = [
        {
            "name": "main",
            "displayName": "main",
            "isActive": True,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        },
        {
            "name": "feature/login",
            "displayName": "feature/login",
            "isActive": False,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        }
    ]

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/branches?search=feature")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["branches"]) == 1
    assert "feature" in payload["branches"][0]["name"]


def test_vc_004_checkout_existing_branch(client):
    """VC-004 Switch existing branch"""
    service = StubGitService(Path("/tmp/workspace"))

    service.branches = [
        {
            "name": "main",
            "displayName": "main",
            "isActive": True,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        },
        {
            "name": "develop",
            "displayName": "develop",
            "isActive": False,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        }
    ]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/branches/develop/checkout",
            json={"create": False}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["branch"] == "develop"
    assert payload["created"] is False


def test_vc_005_create_and_checkout_new_branch(client):
    """VC-005 Create new branch and switch"""
    service = StubGitService(Path("/tmp/workspace"))

    service.branches = [
        {
            "name": "main",
            "displayName": "main",
            "isActive": True,
            "isRemote": False,
            "ahead": 0,
            "behind": 0,
            "lastCommit": None
        }
    ]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/branches/feature/api/checkout",
            json={"create": True}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["branch"] == "feature/api"
    assert payload["created"] is True


def test_vc_006_get_all_changes(client):
    """VC-006 Get all changes"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt", "file2.txt"]
    service.unstaged_files = ["file3.txt"]
    service.untracked_files = ["file4.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/changes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["staged"]) == 2
    assert len(payload["unstaged"]) == 1
    assert len(payload["untracked"]) == 1
    assert payload["untrackedTotal"] == 1


def test_vc_007_scope_filter_changes(client):
    """VC-007 Scope filter changes"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt"]
    service.unstaged_files = ["file2.txt"]
    service.untracked_files = ["file3.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/changes?scope=staged")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["staged"]) == 1
    assert len(payload["unstaged"]) == 0
    assert len(payload["untracked"]) == 0


def test_vc_008_stage_files(client):
    """VC-008 Stage file"""
    service = StubGitService(Path("/tmp/workspace"))
    service.unstaged_files = ["file1.txt", "file2.txt"]
    service.untracked_files = ["dir/"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/stage",
            json={"paths": ["file1.txt", "dir/"]}
        )

    assert response.status_code == 200
    payload = response.json()
    assert "file1.txt" in payload["staged"]
    assert len(service.staged_files) >= 1


def test_vc_009_unstage_files(client):
    """VC-009 Unstage"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt", "file2.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/unstage",
            json={"paths": ["file1.txt", "file2.txt"]}
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["unstaged"]) == 2
    assert len(service.staged_files) == 0


def test_vc_010_discard_changes(client):
    """VC-010 Discard unstaged changes"""
    service = StubGitService(Path("/tmp/workspace"))
    service.unstaged_files = ["README.md"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/discard",
            json={"paths": ["README.md"], "resetMode": "mixed"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert "README.md" in payload["discarded"]


def test_vc_011_create_commit(client):
    """VC-011 Create valid commit"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/commit",
            json={
                "message": "feat: add api",
                "author": {"name": "Tester", "email": "test@example.com"}
            }
        )

    assert response.status_code == 201
    payload = response.json()
    assert "commit" in payload
    assert payload["commit"]["message"] == "feat: add api"
    assert len(service.commits) == 1


def test_vc_012_commit_missing_message(client):
    """VC-012 Missing message rejected"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/commit",
            json={"message": ""}
        )

    assert response.status_code == 400


def test_vc_013_list_commits(client):
    """VC-013 Paginated commits query"""
    service = StubGitService(Path("/tmp/workspace"))
    # Create 5 commits
    for i in range(5):
        service.commits.append({
            "id": f"commit_{i+1}",
            "message": f"Commit {i+1}",
            "author": {"name": "Tester", "email": "test@example.com"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    with override_dependency(get_git_service, lambda: service):
        response = client.get(
            "/api/v1/workspaces/test_ws/version-control/commits?page=2&pageSize=2"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert len(payload["items"]) == 2


def test_vc_014_get_commit_detail(client):
    """VC-014 Get single commit details"""
    service = StubGitService(Path("/tmp/workspace"))
    commit = {
        "id": "commit_123",
        "message": "Test commit",
        "author": {"name": "Tester", "email": "test@example.com"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    service.commits.append(commit)

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/commits/commit_123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "commit_123"
    assert payload["message"] == "Test commit"


def test_vc_015_commit_not_found(client):
    """VC-015 Commit does not exist"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/commits/nonexistent")

    assert response.status_code == 400


def test_vc_016_push_changes(client):
    """VC-016 Push successful"""
    service = StubGitService(Path("/tmp/workspace"))
    service.current_branch = "main"

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/push",
            json={"remote": "origin", "branch": "main"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remote"] == "origin"
    assert payload["branch"] == "main"


def test_vc_017_pull_changes(client):
    """VC-017 Pull remote updates"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/pull",
            json={"remote": "origin", "branch": "main"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remote"] == "origin"
    assert payload["branch"] == "main"
    assert payload["fastForward"] is True


def test_vc_018_fetch_changes(client):
    """VC-018 Sync remote refs"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/fetch",
            json={"remote": "origin"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remote"] == "origin"


def test_vc_019_get_diff(client):
    """VC-019 Diff output"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.get(
            "/api/v1/workspaces/test_ws/version-control/diff?path=README.md&includeMetadata=true"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "README.md"
    assert "patch" in payload
    assert payload["metadata"] is not None


def test_vc_020_read_blob(client):
    """VC-020 Read file at specific version"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.get(
            "/api/v1/workspaces/test_ws/version-control/blob?path=README.md&revision=commit_123"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "README.md"
    assert payload["revision"] == "commit_123"
    assert payload["isBase64"] is True
