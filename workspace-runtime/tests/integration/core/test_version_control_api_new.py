"""核心模組 Version Control API 測試 - 符合實際 API 實作"""

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
)

from .helpers import override_dependency


class StubGitService:
    """可控制的 GitService stub - 符合實際 API 實作"""

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

    def get_status(self, workspace_id: str) -> VersionControlStatus:
        """取得 Git 狀態"""
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

    def list_branches(self, workspace_id: str, include_remote: bool = False, search: Optional[str] = None) -> dict[str, Any]:
        """取得分支列表"""
        branches = self.branches.copy()
        if search:
            branches = [b for b in branches if search.lower() in b["name"].lower()]

        return {"branches": branches}

    def checkout_branch(self, workspace_id: str, branch_name: str, payload) -> dict[str, Any]:
        """切換分支"""
        # 處理 payload 可能是 Pydantic 模型或字典
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        create = payload_dict.get("create", False)

        if create and branch_name not in [b["name"] for b in self.branches]:
            # 建立新分支
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
            # 切換現有分支
            existing = [b for b in self.branches if b["name"] == branch_name]
            if not existing:
                raise VersionControlError("Branch not found")

            # 更新所有分支的 isActive 狀態
            for branch in self.branches:
                branch["isActive"] = branch["name"] == branch_name
            self.current_branch = branch_name
            return {
                "branch": branch_name,
                "created": False,
                "stashedChanges": None
            }

    def get_changes(self, workspace_id: str, page: int = 1, page_size: int = 100) -> ChangesResponse:
        """取得變更列表"""
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

    def stage(self, workspace_id: str, payload) -> dict[str, Any]:
        """暫存檔案"""
        # 處理 payload 可能是 Pydantic 模型或字典
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

    def unstage(self, workspace_id: str, payload) -> dict[str, Any]:
        """取消暫存"""
        # 處理 payload 可能是 Pydantic 模型或字典
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

    def discard(self, workspace_id: str, payload) -> dict[str, Any]:
        """丟棄變更"""
        # 處理 payload 可能是 Pydantic 模型或字典
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

    def commit(self, workspace_id: str, payload) -> dict[str, Any]:
        """建立提交"""
        # 處理 payload 可能是 Pydantic 模型或字典
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

    def list_commits(self, workspace_id: str, page: int = 1, page_size: int = 20,
                     branch: Optional[str] = None, search: Optional[str] = None) -> dict[str, Any]:
        """提交列表"""
        start = (page - 1) * page_size
        end = start + page_size

        # 轉換 commit 資料結構以符合 API 模型
        items = []
        for commit in self.commits[start:end][::-1]:  # 最新的在前
            item = {
                "id": commit["id"],
                "message": commit["message"],
                "author": f"{commit['author']['name']} <{commit['author']['email']}>",  # 字串格式
                "timestamp": int(datetime.now(timezone.utc).timestamp()),  # 整數格式
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

    def get_commit(self, workspace_id: str, commit_id: str) -> dict[str, Any]:
        """取得提交詳細"""
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

    def get_commit_files(self, workspace_id: str, commit_id: str) -> dict[str, Any]:
        """取得提交檔案差異"""
        # 簡化實作
        return {
            "commitId": commit_id,
            "files": []
        }

    def push(self, workspace_id: str, payload) -> dict[str, Any]:
        """推送"""
        # 處理 payload 可能是 Pydantic 模型或字典
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        return {
            "remote": payload_dict.get("remote", "origin"),
            "branch": self.current_branch,
            "updates": []
        }

    def pull(self, workspace_id: str, payload) -> dict[str, Any]:
        """拉取"""
        # 處理 payload 可能是 Pydantic 模型或字典
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

    def fetch(self, workspace_id: str, payload) -> dict[str, Any]:
        """同步遠端引用"""
        # 處理 payload 可能是 Pydantic 模型或字典
        if hasattr(payload, 'model_dump'):
            payload_dict = payload.model_dump()
        else:
            payload_dict = payload

        return {
            "remote": payload_dict.get("remote", "origin"),
            "fetchedRefs": []
        }

    def diff(self, workspace_id: str, path: str, base: Optional[str] = None,
             head: Optional[str] = None, context: int = 3, include_metadata: bool = False) -> dict[str, Any]:
        """取得差異"""
        return {
            "path": path,
            "base": base or "HEAD",
            "head": head or "working",
            "context": context,
            "patch": "@@ -1,3 +1,4 @@\n line 1\n+line 2\n line 3",
            "metadata": {"file": path} if include_metadata else None
        }

    def blob(self, workspace_id: str, path: str, revision: Optional[str] = None) -> dict[str, Any]:
        """讀取檔案內容"""
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
    """取得 GitService stub 的工廠函數"""
    workspace_path = Path("/tmp/workspace")
    return StubGitService(workspace_path)


# ============================================================================
# Tests
# ============================================================================


def test_vc_001_get_git_status_normal(client):
    """VC-001 取得正常 Git 狀態"""
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
    """VC-002 列出本地與遠端分支"""
    service = StubGitService(Path("/tmp/workspace"))

    # 設定分支資料
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
    """VC-003 使用關鍵字過濾分支"""
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
    """VC-004 切換現有分支"""
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
    """VC-005 建立新分支並切換"""
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
    """VC-006 取得全部變更"""
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
    """VC-007 scope 過濾變更"""
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
    """VC-008 暫存檔案"""
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
    """VC-009 取消暫存"""
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
    """VC-010 丟棄未暫存變更"""
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
    """VC-011 建立有效提交"""
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
    """VC-012 缺少訊息被拒絕"""
    service = StubGitService(Path("/tmp/workspace"))
    service.staged_files = ["file1.txt"]

    with override_dependency(get_git_service, lambda: service):
        response = client.post(
            "/api/v1/workspaces/test_ws/version-control/commit",
            json={"message": ""}
        )

    assert response.status_code == 400


def test_vc_013_list_commits(client):
    """VC-013 分頁查詢提交"""
    service = StubGitService(Path("/tmp/workspace"))
    # 建立 5 筆 commit
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
    """VC-014 取得單筆 commit 詳細"""
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
    """VC-015 Commit 不存在"""
    service = StubGitService(Path("/tmp/workspace"))

    with override_dependency(get_git_service, lambda: service):
        response = client.get("/api/v1/workspaces/test_ws/version-control/commits/nonexistent")

    assert response.status_code == 400


def test_vc_016_push_changes(client):
    """VC-016 推送成功"""
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
    """VC-017 拉取遠端更新"""
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
    """VC-018 同步遠端引用"""
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
    """VC-019 差異輸出"""
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
    """VC-020 讀取指定版本檔案"""
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