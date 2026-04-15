from __future__ import annotations

import json
from pathlib import Path

from app.modules.openspec.models import (
    OpenSpecActionAvailability,
    OpenSpecActionContextSubview,
    OpenSpecChangeStatus,
    OpenSpecWorkspaceProfile,
)
from app.modules.openspec.service import OpenSpecService


def test_workspace_state_when_cli_missing(tmp_path: Path, monkeypatch) -> None:
    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: None)

    result = service.get_workspace_state("ws-1")

    assert result.workspaceId == "ws-1"
    assert result.state.cliInstalled is False
    assert result.state.initialized is False
    assert result.actions[0].availability == OpenSpecActionAvailability.SETUP_REQUIRED
    assert result.actions[0].reason == "OpenSpec CLI 尚未安裝於 workspace runtime"
    assert result.changes == []


def test_workspace_state_with_initialized_project_and_active_changes(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec").mkdir()
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    change_dir = tmp_path / "openspec" / "changes" / "add-auth"
    (change_dir / "specs" / "auth").mkdir(parents=True)
    (change_dir / "proposal.md").write_text("proposal", encoding="utf-8")
    (change_dir / "design.md").write_text("design", encoding="utf-8")
    (change_dir / "tasks.md").write_text("- [x] Step 1\n- [ ] Step 2\n", encoding="utf-8")
    (change_dir / "specs" / "auth" / "spec.md").write_text("spec", encoding="utf-8")
    for command_name in ("explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")
    service = OpenSpecService(workspace_path=tmp_path)

    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")

    def fake_run(args: list[str]) -> str | None:
        if args == ["--version"]:
            return "1.3.0"
        if args == ["list", "--json"]:
            return json.dumps(
                {
                    "changes": [
                        {
                            "name": "add-auth",
                            "status": "in-progress",
                            "completedTasks": 1,
                            "totalTasks": 3,
                            "lastModified": "2026-04-12T03:00:00.000Z",
                        },
                        {
                            "name": "done-change",
                            "status": "complete",
                            "completedTasks": 2,
                            "totalTasks": 2,
                        },
                    ]
                }
            )
        if args == ["config", "get", "profile"]:
            return "custom"
        if args == ["config", "get", "workflows"]:
            return json.dumps(["explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"])
        return None

    monkeypatch.setattr(service, "_run_openspec", fake_run)

    result = service.get_workspace_state("ws-1", language="en-US")

    assert result.state.cliInstalled is True
    assert result.state.cliVersion == "1.3.0"
    assert result.state.initialized is True
    assert result.state.profile == OpenSpecWorkspaceProfile.CUSTOM
    assert result.state.projectSynced is True
    assert [change.name for change in result.state.activeChanges] == ["add-auth"]

    action_map = {action.id: action for action in result.actions}
    assert action_map["apply"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["apply"].recommended is True
    assert action_map["apply"].draftTemplate == "/opsx:apply add-auth"
    assert action_map["apply"].title == "Apply"
    assert action_map["apply"].description == "Implement the current change by following its tasks"
    assert action_map["new"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["apply"].recommendedReason == "There is an active change with work ready to implement"
    assert len(result.changes) == 1
    navigation_change = result.changes[0]
    assert navigation_change.name == "add-auth"
    assert navigation_change.status == OpenSpecChangeStatus.IN_PROGRESS
    assert navigation_change.tasksPath == "/openspec/changes/add-auth/tasks.md"
    assert navigation_change.completedTasks == 1
    assert navigation_change.totalTasks == 2
    assert navigation_change.specs[0].capabilityName == "auth"


def test_workspace_state_blocks_change_actions_without_active_changes(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec").mkdir()
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    for command_name in ("propose", "explore", "apply", "archive"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")
    service = OpenSpecService(workspace_path=tmp_path)

    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "core" if args == ["config", "get", "profile"]
            else json.dumps(["propose", "explore", "apply", "archive"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state("ws-1", language="zh-TW")

    action_map = {action.id: action for action in result.actions}
    assert action_map["propose"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["propose"].recommended is True
    assert action_map["propose"].title == "提案"
    assert action_map["apply"].availability == OpenSpecActionAvailability.BLOCKED
    assert action_map["apply"].reason == "目前沒有可用的 OpenSpec change"


def test_workspace_state_falls_back_to_default_language_for_unsupported_locale(tmp_path: Path, monkeypatch) -> None:
    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: None)

    result = service.get_workspace_state("ws-1", language="fr-FR")

    assert result.actions[0].title == "提案"
    assert result.actions[0].description == "建立 change 並產生規劃 artifacts"
    assert result.actions[0].reason == "OpenSpec CLI 尚未安裝於 workspace runtime"


def test_workspace_state_includes_complete_and_archived_navigation_changes(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec" / "changes" / "done-change" / "specs" / "docs").mkdir(parents=True)
    (tmp_path / "openspec" / "changes" / "archive" / "old-change").mkdir(parents=True)
    (tmp_path / "openspec" / "changes" / "done-change" / "tasks.md").write_text(
        "- [x] Done 1\n- [x] Done 2\n",
        encoding="utf-8",
    )
    (tmp_path / "openspec" / "changes" / "done-change" / "proposal.md").write_text("proposal", encoding="utf-8")
    (tmp_path / "openspec" / "changes" / "done-change" / "specs" / "docs" / "spec.md").write_text("spec", encoding="utf-8")
    (tmp_path / "openspec" / "changes" / "archive" / "old-change" / "tasks.md").write_text(
        "- [ ] remains archived\n",
        encoding="utf-8",
    )

    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "core" if args == ["config", "get", "profile"]
            else json.dumps(["propose", "explore", "apply", "archive"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state("ws-1")

    change_map = {change.name: change for change in result.changes}
    assert change_map["done-change"].status == OpenSpecChangeStatus.COMPLETE
    assert change_map["done-change"].completedTasks == 2
    assert change_map["done-change"].totalTasks == 2
    assert change_map["old-change"].status == OpenSpecChangeStatus.ARCHIVED
    assert change_map["old-change"].archived is True


def test_complete_subview_archives_focused_completed_change(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec" / "changes" / "done-change").mkdir(parents=True)
    (tmp_path / "openspec" / "changes" / "active-change").mkdir(parents=True)
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    for command_name in ("propose", "explore", "apply", "archive"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")
    (tmp_path / "openspec" / "changes" / "done-change" / "tasks.md").write_text(
        "- [x] Done 1\n- [x] Done 2\n",
        encoding="utf-8",
    )
    (tmp_path / "openspec" / "changes" / "active-change" / "tasks.md").write_text(
        "- [x] Done 1\n- [ ] Pending 2\n",
        encoding="utf-8",
    )
    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "core" if args == ["config", "get", "profile"]
            else json.dumps(["propose", "explore", "apply", "archive"]) if args == ["config", "get", "workflows"]
            else json.dumps(
                {
                    "changes": [
                        {"name": "active-change", "status": "in-progress", "completedTasks": 1, "totalTasks": 2},
                    ]
                }
            )
        ),
    )

    result = service.get_workspace_state(
        "ws-1",
        language="en-US",
        subview=OpenSpecActionContextSubview.COMPLETE,
        focused_change_name="done-change",
    )

    action_map = {action.id: action for action in result.actions}
    assert action_map["archive"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["archive"].draftTemplate == "/opsx:archive done-change"
    assert action_map["archive"].recommended is True


def test_complete_subview_exposes_bulk_archive_for_multiple_completed_changes(tmp_path: Path, monkeypatch) -> None:
    for change_name in ("done-a", "done-b"):
        change_dir = tmp_path / "openspec" / "changes" / change_name
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [x] Done 1\n", encoding="utf-8")
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    for command_name in ("explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")

    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "custom" if args == ["config", "get", "profile"]
            else json.dumps(["explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state(
        "ws-1",
        language="en-US",
        subview=OpenSpecActionContextSubview.COMPLETE,
    )

    action_map = {action.id: action for action in result.actions}
    assert action_map["archive"].availability == OpenSpecActionAvailability.BLOCKED
    assert action_map["archive"].reason == "Select a completed OpenSpec change to archive it individually"
    assert action_map["bulk-archive"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["bulk-archive"].recommended is True
    assert action_map["bulk-archive"].draftTemplate == "/opsx:bulk-archive"
    assert action_map["bulk-archive"].recommendedReason == "Multiple completed changes are ready to archive together"


def test_archived_subview_disables_archive_action(tmp_path: Path, monkeypatch) -> None:
    archived_dir = tmp_path / "openspec" / "changes" / "archive" / "old-change"
    archived_dir.mkdir(parents=True)
    (archived_dir / "tasks.md").write_text("- [x] Archived\n", encoding="utf-8")
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    for command_name in ("propose", "explore", "apply", "archive"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")

    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "core" if args == ["config", "get", "profile"]
            else json.dumps(["propose", "explore", "apply", "archive"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state(
        "ws-1",
        language="en-US",
        subview=OpenSpecActionContextSubview.ARCHIVED,
        focused_change_name="old-change",
    )

    action_map = {action.id: action for action in result.actions}
    assert action_map["archive"].availability == OpenSpecActionAvailability.DISABLED
    assert action_map["archive"].reason == "Archived OpenSpec changes are read-only"


def test_workspace_state_marks_missing_project_command_files_as_sync_required(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec").mkdir()
    (tmp_path / ".claude" / "commands" / "opsx").mkdir(parents=True)
    for command_name in ("explore", "apply", "archive"):
        (tmp_path / ".claude" / "commands" / "opsx" / f"{command_name}.md").write_text(command_name, encoding="utf-8")

    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "core" if args == ["config", "get", "profile"]
            else json.dumps(["propose", "explore", "apply", "archive"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state("ws-1", language="en-US")

    action_map = {action.id: action for action in result.actions}
    assert result.state.projectSynced is False
    assert action_map["propose"].availability == OpenSpecActionAvailability.SYNC_REQUIRED
    assert action_map["propose"].reason == "Project OpenSpec command files are out of sync with the active workflow profile"


def test_workspace_state_treats_generated_openspec_skills_as_project_synced(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "openspec").mkdir()
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    for skill_name in (
        "openspec-explore",
        "openspec-new-change",
        "openspec-continue-change",
        "openspec-apply-change",
        "openspec-ff-change",
        "openspec-sync-specs",
        "openspec-archive-change",
        "openspec-bulk-archive-change",
        "openspec-verify-change",
        "openspec-onboard",
    ):
        (skills_dir / skill_name).mkdir()

    service = OpenSpecService(workspace_path=tmp_path)
    monkeypatch.setattr("app.modules.openspec.service.shutil.which", lambda _: "/usr/bin/openspec")
    monkeypatch.setattr(
        service,
        "_run_openspec",
        lambda args: (
            "1.3.0" if args == ["--version"]
            else "custom" if args == ["config", "get", "profile"]
            else json.dumps(["explore", "new", "continue", "apply", "ff", "sync", "archive", "bulk-archive", "verify", "onboard"]) if args == ["config", "get", "workflows"]
            else json.dumps({"changes": []})
        ),
    )

    result = service.get_workspace_state("ws-1", language="en-US")

    action_map = {action.id: action for action in result.actions}
    assert result.state.projectSynced is True
    assert action_map["new"].availability == OpenSpecActionAvailability.ENABLED
    assert action_map["verify"].availability == OpenSpecActionAvailability.BLOCKED
    assert action_map["verify"].reason != "Project OpenSpec command files are out of sync with the active workflow profile"
