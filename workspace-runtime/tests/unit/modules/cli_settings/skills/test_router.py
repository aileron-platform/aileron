from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cli_settings.skills.config import SkillTool
from app.modules.cli_settings.skills.router import create_skills_router
from app.modules.file_system.exceptions import FileManagementException


class FakeSkillService:
    def __init__(self):
        self.fail_with = None
        self.write_calls = []
        self.create_calls = []
        self.upload_calls = []
        self.extract_calls = []
        self.preflight_calls = []

    def _maybe_fail(self):
        if self.fail_with:
            raise self.fail_with

    def get_tree(self, path, scope, include_hidden, max_depth):
        self._maybe_fail()
        return {"path": path, "scope": scope, "nodes": [], "total": 0}

    def read_file(self, path, scope):
        self._maybe_fail()
        return {
            "path": path,
            "scope": scope,
            "content": "hello",
            "size": 5,
            "updatedAt": "2026-03-28T00:00:00Z",
        }

    def write_file(self, path, content, scope, expected_version_id):
        self._maybe_fail()
        self.write_calls.append((path, content, scope, expected_version_id))
        return {"updatedAt": "2026-03-28T00:00:00Z", "revision": "v1"}

    def create_entry(self, path, type, scope, content):
        self._maybe_fail()
        self.create_calls.append((path, type, scope, content))
        return {"path": path, "scope": scope, "type": type}

    def delete_entry(self, path, scope, recursive):
        self._maybe_fail()
        return {"type": "file"}

    def move_entry(self, source_path, dest_path, source_scope, dest_scope):
        self._maybe_fail()
        return {"type": "file"}

    def batch_delete(self, paths, scope, recursive):
        self._maybe_fail()
        return {
            "total": len(paths),
            "succeeded": len(paths),
            "failed": 0,
            "results": [],
        }

    def clear_tree_cache(self, scope=None):
        return None

    def is_readonly_scope(self, scope):
        return scope == "plugin"

    def preflight_upload_files(self, **kwargs):
        self.preflight_calls.append(("upload", kwargs))
        return {"conflicts": [], "total": len(kwargs["filenames"])}

    def preflight_copy_entries(self, **kwargs):
        self.preflight_calls.append(("paste", kwargs))
        return {
            "conflicts": [
                {
                    "sourcePath": kwargs["source_paths"][0],
                    "targetPath": f"{kwargs['target_path'].rstrip('/')}/copied.md",
                    "sourceType": "file",
                    "targetType": "file",
                    "canReplace": True,
                }
            ],
            "total": len(kwargs["source_paths"]),
        }

    def preflight_extract_archive(self, **kwargs):
        self.preflight_calls.append(("extract", kwargs))
        return {"conflicts": [], "total": 1}

    def upload_file_streams(
        self, *, target_path, files, default_strategy, resolutions, scope=None
    ):
        self.upload_calls.append(
            (target_path, files, default_strategy, resolutions, scope)
        )
        return {
            "items": [
                {
                    "sourcePath": files[0][0],
                    "finalPath": f"{target_path.rstrip('/')}/{files[0][0]}",
                    "status": "created",
                    "size": files[0][2],
                    "type": "file",
                    "error": None,
                }
            ],
            "total": 1,
            "succeeded": 1,
            "skipped": 0,
            "failed": 0,
        }

    def extract_archive_path(
        self, *, archive_path, target_path, default_strategy, resolutions, scope=None
    ):
        self.extract_calls.append(
            (archive_path, target_path, default_strategy, resolutions, scope)
        )
        return {
            "items": [
                {
                    "sourcePath": "demo/SKILL.md",
                    "finalPath": f"{target_path.rstrip('/')}/demo/SKILL.md",
                    "status": "created",
                    "size": 6,
                    "type": "file",
                    "error": None,
                }
            ],
            "total": 1,
            "succeeded": 1,
            "skipped": 0,
            "failed": 0,
        }


def _client(
    service: FakeSkillService, monkeypatch, tool: SkillTool = SkillTool.CODEX
) -> TestClient:
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.router.make_skill_service_dependency",
        lambda t: (lambda workspace_id: service),
    )
    app = FastAPI()
    app.include_router(
        create_skills_router(tool), prefix="/workspaces/{workspace_id}/cli-settings"
    )
    return TestClient(app)


def test_skills_router_happy_paths(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    assert (
        client.get("/workspaces/ws-1/cli-settings/codex/skills/tree").status_code == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/skills/tree/children",
            params={"path": "/a"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/skills/content",
            params={"path": "/a.md"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/workspaces/ws-1/cli-settings/codex/skills/content",
            params={"path": "/a.md"},
            json={"content": "hi", "revision": None},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/workspaces/ws-1/cli-settings/codex/skills",
            params={"path": "/a.md", "type": "file"},
        ).status_code
        == 201
    )
    assert (
        client.delete(
            "/workspaces/ws-1/cli-settings/codex/skills", params={"path": "/a.md"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/workspaces/ws-1/cli-settings/codex/skills/move",
            params={"sourcePath": "/a", "destPath": "/b"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/workspaces/ws-1/cli-settings/codex/skills/batch-delete",
            params=[("paths", "/a"), ("paths", "/b")],
        ).status_code
        == 200
    )


def test_skills_router_write_takes_content_in_body(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    response = client.put(
        "/workspaces/ws-1/cli-settings/codex/skills/content",
        params={"path": "skills/demo/SKILL.md"},
        json={"content": "# demo", "revision": None},
    )

    assert response.status_code == 200
    assert response.json()["data"]["path"] == "skills/demo/SKILL.md"
    assert service.write_calls == [("skills/demo/SKILL.md", "# demo", None, None)]


def test_skills_router_create_takes_content_in_body(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/skills",
        params={"path": "skills/demo/SKILL.md", "type": "file"},
        json={"content": "# demo", "revision": None},
    )

    assert response.status_code == 201
    assert service.create_calls == [("skills/demo/SKILL.md", "file", None, "# demo")]


def test_skills_router_preflights_upload_paste_and_extract(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)
    endpoint = "/workspaces/ws-1/cli-settings/codex/skills/conflicts/preflight"

    uploaded = client.post(
        endpoint,
        params={"scope": "project"},
        json={
            "operation": "upload",
            "targetPath": "demo",
            "sources": [{"sourcePath": "a.md", "entryType": "file"}],
            "archivePath": None,
        },
    )
    pasted = client.post(
        endpoint,
        params={"scope": "project"},
        json={
            "operation": "paste",
            "targetPath": "demo",
            "sources": [{"sourcePath": "a.md", "entryType": "file"}],
            "archivePath": None,
        },
    )
    extracted = client.post(
        endpoint,
        params={"scope": "project"},
        json={
            "operation": "extract",
            "targetPath": "demo",
            "sources": None,
            "archivePath": "demo.zip",
        },
    )

    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json() == {"conflicts": [], "total": 1}
    assert pasted.status_code == 200, pasted.text
    assert pasted.json()["conflicts"][0]["targetPath"] == "demo/copied.md"
    assert extracted.status_code == 200, extracted.text
    assert [kind for kind, _ in service.preflight_calls] == [
        "upload",
        "paste",
        "extract",
    ]
    assert service.preflight_calls[0][1] == {
        "target_path": "demo",
        "filenames": ["a.md"],
        "scope": "project",
    }
    assert service.preflight_calls[1][1] == {
        "source_paths": ["a.md"],
        "target_path": "demo",
        "source_scope": "project",
        "dest_scope": "project",
    }


def test_skills_router_preflight_rejects_readonly_scope_without_calling_service(
    monkeypatch,
) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/skills/conflicts/preflight",
        params={"scope": "plugin"},
        json={
            "operation": "upload",
            "targetPath": "demo",
            "sources": [{"sourcePath": "a.md", "entryType": "file"}],
            "archivePath": None,
        },
    )

    assert response.status_code == 403
    assert service.preflight_calls == []


def test_skills_router_extract_preflight_requires_archive_path(monkeypatch) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/skills/conflicts/preflight",
        json={
            "operation": "extract",
            "targetPath": "demo",
            "sources": None,
            "archivePath": None,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_ARCHIVE"
    assert service.preflight_calls == []


def test_skills_router_streams_uploads_and_extracts_stored_archives(
    monkeypatch,
) -> None:
    service = FakeSkillService()
    client = _client(service, monkeypatch)

    uploaded = client.post(
        "/workspaces/ws-1/cli-settings/codex/skills/upload",
        data={
            "targetPath": "demo",
            "scope": "project",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files={"files": ("asset.bin", b"\x00\xff", "application/octet-stream")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["items"][0]["finalPath"] == "demo/asset.bin"
    assert service.upload_calls[0][0] == "demo"
    assert service.upload_calls[0][1][0][2] == 2

    extracted = client.post(
        "/workspaces/ws-1/cli-settings/codex/skills/extract",
        json={
            "archivePath": "demo.zip",
            "targetPath": "demo",
            "scope": "project",
            "defaultStrategy": "keep-both",
            "resolutions": [],
        },
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["items"][0]["finalPath"] == "demo/demo/SKILL.md"
    assert service.extract_calls == [
        ("demo.zip", "demo", "keep-both", [], "project")
    ]


def test_skills_router_error_mapping(monkeypatch) -> None:
    service = FakeSkillService()
    service.fail_with = FileManagementException("BROKEN", "broken", status_code=409)
    client = _client(service, monkeypatch)

    response = client.get("/workspaces/ws-1/cli-settings/codex/skills/tree")
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "errorCode": "BROKEN",
        "message": "broken",
    }

    service.fail_with = RuntimeError("boom")
    response = client.get(
        "/workspaces/ws-1/cli-settings/codex/skills/content", params={"path": "/a.md"}
    )
    assert response.status_code == 500
    assert response.json()["detail"] == {
        "errorCode": "INTERNAL_ERROR",
        "message": "boom",
    }


def test_skills_router_plugin_endpoint_absent(monkeypatch) -> None:
    client = _client(FakeSkillService(), monkeypatch, tool=SkillTool.CODEX)
    response = client.get("/workspaces/ws-1/cli-settings/codex/skills/plugins")
    assert response.status_code == 404


class FakeClaudeSkillService(FakeSkillService):
    def __init__(self):
        super().__init__()
        self.plugin_skills = []
        self.plugin_error = None

    def get_plugin_skills(self):
        if self.plugin_error:
            raise self.plugin_error
        return self.plugin_skills


def test_skills_router_plugin_endpoint_present_for_claude(monkeypatch) -> None:
    service = FakeClaudeSkillService()
    client = _client(service, monkeypatch, tool=SkillTool.CLAUDE)

    response = client.get("/workspaces/ws-1/cli-settings/claude-code/skills/plugins")

    assert response.status_code == 200
    assert response.json() == {"workspaceId": "ws-1", "plugins": []}


def test_skills_router_plugin_endpoint_exception_returns_empty(monkeypatch) -> None:
    service = FakeClaudeSkillService()
    service.plugin_error = RuntimeError("boom")
    client = _client(service, monkeypatch, tool=SkillTool.CLAUDE)

    response = client.get("/workspaces/ws-1/cli-settings/claude-code/skills/plugins")

    assert response.status_code == 200
    assert response.json() == {"workspaceId": "ws-1", "plugins": []}


def test_skills_router_claude_happy_paths(monkeypatch) -> None:
    service = FakeClaudeSkillService()
    client = _client(service, monkeypatch, tool=SkillTool.CLAUDE)

    assert (
        client.get("/workspaces/ws-1/cli-settings/claude-code/skills/tree").status_code
        == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/claude-code/skills/content",
            params={"path": "/a.md"},
        ).status_code
        == 200
    )
