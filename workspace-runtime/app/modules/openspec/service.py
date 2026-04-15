"""OpenSpec runtime service."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.config.settings import get_workspace_path

from .models import (
    OpenSpecActionAvailability,
    OpenSpecActionContextSubview,
    OpenSpecActionInputKind,
    OpenSpecActionGroup,
    OpenSpecActionItem,
    OpenSpecActionProfile,
    OpenSpecChangeStatus,
    OpenSpecChangeSummary,
    OpenSpecNavigationChange,
    OpenSpecSpecDocument,
    OpenSpecWorkspaceProfile,
    OpenSpecWorkspaceResponse,
    OpenSpecWorkspaceState,
)

logger = logging.getLogger(__name__)


TranslateFn = Callable[[str], str]
TASK_CHECKBOX_RE = re.compile(r"^\s*-\s\[(x|X| )\]\s.+$")


@dataclass(frozen=True)
class OpenSpecActionDefinition:
    action_id: str
    title_key: str
    description_key: str
    group: OpenSpecActionGroup
    profile: OpenSpecActionProfile
    requires_change: bool
    supports_change_argument: bool
    input_kind: OpenSpecActionInputKind
    example_command: str | None
    draft_template: str


@dataclass(frozen=True)
class OpenSpecActionContext:
    subview: OpenSpecActionContextSubview | None = None
    focused_change_name: str | None = None


class OpenSpecService:
    """聚合 workspace OpenSpec 狀態與 actions。"""

    def __init__(self, workspace_path: str | Path | None = None) -> None:
        self._workspace_path = Path(workspace_path or get_workspace_path())

    def get_workspace_state(
        self,
        workspace_id: str,
        *,
        translate: TranslateFn | None = None,
        language: str | None = None,
        subview: OpenSpecActionContextSubview | None = None,
        focused_change_name: str | None = None,
    ) -> OpenSpecWorkspaceResponse:
        cli_version = self._get_cli_version()
        cli_installed = cli_version is not None
        initialized = self._is_initialized()
        active_changes = self._list_active_changes() if cli_installed and initialized else []
        navigation_changes = self._list_navigation_changes() if initialized else []
        profile = self._resolve_workspace_profile() if cli_installed else OpenSpecWorkspaceProfile.CORE
        project_synced, missing_project_actions = self._resolve_project_sync_state(profile, cli_installed, initialized)
        translator = self._get_translator(translate, language)
        action_context = OpenSpecActionContext(
            subview=subview,
            focused_change_name=focused_change_name,
        )

        state = OpenSpecWorkspaceState(
            cliInstalled=cli_installed,
            cliVersion=cli_version,
            initialized=initialized,
            profile=profile,
            projectSynced=project_synced,
            activeChanges=active_changes,
        )

        actions = self._build_actions(
            state,
            navigation_changes,
            action_context,
            translator,
            missing_project_actions=missing_project_actions,
        )
        return OpenSpecWorkspaceResponse(
            workspaceId=workspace_id,
            state=state,
            actions=actions,
            changes=navigation_changes,
        )

    def log_cli_probe(self) -> None:
        """在 runtime 啟動時記錄 OpenSpec CLI 狀態。"""
        version = self._get_cli_version()
        if version:
            logger.info("✅ OpenSpec CLI 已就緒: %s", version)
            return
        logger.warning("⚠️ OpenSpec CLI 未安裝或不可用")

    def _build_actions(
        self,
        state: OpenSpecWorkspaceState,
        navigation_changes: list[OpenSpecNavigationChange],
        action_context: OpenSpecActionContext,
        translate: TranslateFn,
        *,
        missing_project_actions: set[str],
    ) -> list[OpenSpecActionItem]:
        has_active_change = len(state.activeChanges) > 0
        current_change = state.activeChanges[0].name if has_active_change else None
        archive_target_change = self._resolve_archive_target_change(
            state,
            navigation_changes,
            action_context,
        )

        registry = [
            self._action(
                "propose",
                "openspec.actions.propose.title",
                "openspec.actions.propose.description",
                OpenSpecActionGroup.START,
                OpenSpecActionProfile.CORE,
                requires_change=False,
                supports_change_argument=False,
                input_kind=OpenSpecActionInputKind.STRUCTURED,
                example_command="/opsx:propose add-dark-mode",
                draft_template="/opsx:propose ",
            ),
            self._action(
                "explore",
                "openspec.actions.explore.title",
                "openspec.actions.explore.description",
                OpenSpecActionGroup.START,
                OpenSpecActionProfile.CORE,
                requires_change=False,
                supports_change_argument=False,
                input_kind=OpenSpecActionInputKind.NONE,
                example_command="/opsx:explore auth strategy",
                draft_template="/opsx:explore ",
            ),
            self._action(
                "apply",
                "openspec.actions.apply.title",
                "openspec.actions.apply.description",
                OpenSpecActionGroup.IMPLEMENT,
                OpenSpecActionProfile.CORE,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:apply add-dark-mode",
                draft_template=f"/opsx:apply {current_change}" if current_change else "/opsx:apply ",
            ),
            self._action(
                "archive",
                "openspec.actions.archive.title",
                "openspec.actions.archive.description",
                OpenSpecActionGroup.FINALIZE,
                OpenSpecActionProfile.CORE,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:archive add-dark-mode",
                draft_template=f"/opsx:archive {current_change}" if current_change else "/opsx:archive ",
            ),
            self._action(
                "new",
                "openspec.actions.new.title",
                "openspec.actions.new.description",
                OpenSpecActionGroup.PLAN,
                OpenSpecActionProfile.EXPANDED,
                requires_change=False,
                supports_change_argument=False,
                input_kind=OpenSpecActionInputKind.STRUCTURED,
                example_command="/opsx:new add-dark-mode --schema spec-driven",
                draft_template="/opsx:new ",
            ),
            self._action(
                "continue",
                "openspec.actions.continue.title",
                "openspec.actions.continue.description",
                OpenSpecActionGroup.PLAN,
                OpenSpecActionProfile.EXPANDED,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:continue add-dark-mode",
                draft_template=f"/opsx:continue {current_change}" if current_change else "/opsx:continue ",
            ),
            self._action(
                "ff",
                "openspec.actions.ff.title",
                "openspec.actions.ff.description",
                OpenSpecActionGroup.PLAN,
                OpenSpecActionProfile.EXPANDED,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:ff add-dark-mode",
                draft_template=f"/opsx:ff {current_change}" if current_change else "/opsx:ff ",
            ),
            self._action(
                "verify",
                "openspec.actions.verify.title",
                "openspec.actions.verify.description",
                OpenSpecActionGroup.FINALIZE,
                OpenSpecActionProfile.EXPANDED,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:verify add-dark-mode",
                draft_template=f"/opsx:verify {current_change}" if current_change else "/opsx:verify ",
            ),
            self._action(
                "sync",
                "openspec.actions.sync.title",
                "openspec.actions.sync.description",
                OpenSpecActionGroup.FINALIZE,
                OpenSpecActionProfile.EXPANDED,
                requires_change=True,
                supports_change_argument=True,
                input_kind=OpenSpecActionInputKind.CHANGE,
                example_command="/opsx:sync add-dark-mode",
                draft_template=f"/opsx:sync {current_change}" if current_change else "/opsx:sync ",
            ),
            self._action(
                "bulk-archive",
                "openspec.actions.bulk-archive.title",
                "openspec.actions.bulk-archive.description",
                OpenSpecActionGroup.FINALIZE,
                OpenSpecActionProfile.EXPANDED,
                requires_change=False,
                supports_change_argument=False,
                input_kind=OpenSpecActionInputKind.STRUCTURED,
                example_command="/opsx:bulk-archive add-dark-mode fix-login-redirect",
                draft_template="/opsx:bulk-archive",
            ),
            self._action(
                "onboard",
                "openspec.actions.onboard.title",
                "openspec.actions.onboard.description",
                OpenSpecActionGroup.LEARN,
                OpenSpecActionProfile.EXPANDED,
                requires_change=False,
                supports_change_argument=False,
                input_kind=OpenSpecActionInputKind.NONE,
                example_command="/opsx:onboard",
                draft_template="/opsx:onboard",
            ),
        ]

        actions: list[OpenSpecActionItem] = []
        for definition in registry:
            availability, reason = self._resolve_action_availability(
                definition,
                state,
                navigation_changes,
                action_context,
                archive_target_change,
                translate,
                missing_project_actions=missing_project_actions,
            )
            draft_template = self._resolve_draft_template(
                definition,
                current_change=current_change,
                archive_target_change=archive_target_change,
            )
            actions.append(
                OpenSpecActionItem(
                    id=definition.action_id,
                    title=translate(definition.title_key),
                    description=translate(definition.description_key),
                    group=definition.group,
                    profile=definition.profile,
                    availability=availability,
                    reason=reason,
                    recommended=self._is_recommended(
                        definition.action_id,
                        state,
                        navigation_changes,
                        action_context,
                        archive_target_change,
                    ),
                    recommendedReason=self._resolve_recommended_reason(
                        definition.action_id,
                        state,
                        navigation_changes,
                        action_context,
                        archive_target_change,
                        translate,
                    ),
                    requiresChange=definition.requires_change,
                    supportsChangeArgument=definition.supports_change_argument,
                    inputKind=definition.input_kind,
                    exampleCommand=definition.example_command,
                    draftTemplate=draft_template,
                )
            )

        return actions

    def _resolve_action_availability(
        self,
        action: OpenSpecActionDefinition,
        state: OpenSpecWorkspaceState,
        navigation_changes: list[OpenSpecNavigationChange],
        action_context: OpenSpecActionContext,
        archive_target_change: str | None,
        translate: TranslateFn,
        *,
        missing_project_actions: set[str],
    ) -> tuple[OpenSpecActionAvailability, str | None]:
        if not state.cliInstalled:
            return OpenSpecActionAvailability.SETUP_REQUIRED, translate("openspec.actions.reason.cli_missing")
        if not state.initialized and action.action_id not in {"explore", "onboard"}:
            return OpenSpecActionAvailability.SETUP_REQUIRED, translate("openspec.actions.reason.not_initialized")
        if action.profile == OpenSpecActionProfile.EXPANDED and state.profile == OpenSpecWorkspaceProfile.CORE:
            return OpenSpecActionAvailability.HIDDEN, translate("openspec.actions.reason.expanded_hidden")
        if action.action_id in missing_project_actions:
            return OpenSpecActionAvailability.SYNC_REQUIRED, translate("openspec.actions.reason.project_not_synced")
        if action.action_id == "archive":
            return self._resolve_archive_availability(
                action_context,
                navigation_changes,
                archive_target_change,
                translate,
            )
        if action.action_id == "bulk-archive":
            return self._resolve_bulk_archive_availability(
                action_context,
                navigation_changes,
                self._to_action_profile(state.profile),
                translate,
            )
        if action.requires_change and not state.activeChanges:
            return OpenSpecActionAvailability.BLOCKED, translate("openspec.actions.reason.no_active_change")
        return OpenSpecActionAvailability.ENABLED, None

    def _resolve_recommended_reason(
        self,
        action_id: str,
        state: OpenSpecWorkspaceState,
        navigation_changes: list[OpenSpecNavigationChange],
        action_context: OpenSpecActionContext,
        archive_target_change: str | None,
        translate: TranslateFn,
    ) -> str | None:
        if not self._is_recommended(action_id, state, navigation_changes, action_context, archive_target_change):
            return None
        if not state.cliInstalled:
            return translate("openspec.actions.recommended.missing_cli")
        if not state.initialized:
            if action_id == "onboard":
                return translate("openspec.actions.recommended.not_initialized_onboard")
            return translate("openspec.actions.recommended.not_initialized_explore")
        if action_context.subview == OpenSpecActionContextSubview.COMPLETE:
            if action_id == "bulk-archive":
                return translate("openspec.actions.recommended.complete_many")
            if action_id == "archive":
                return translate("openspec.actions.recommended.complete_one")
        if state.activeChanges:
            if action_id == "apply":
                return translate("openspec.actions.recommended.in_progress_apply")
            if action_id == "archive":
                return translate("openspec.actions.recommended.in_progress_archive")
        if action_id == "propose":
            return translate("openspec.actions.recommended.no_active_change_propose")
        if action_id == "explore":
            return translate("openspec.actions.recommended.no_active_change_explore")
        return None

    def _is_recommended(
        self,
        action_id: str,
        state: OpenSpecWorkspaceState,
        navigation_changes: list[OpenSpecNavigationChange],
        action_context: OpenSpecActionContext,
        archive_target_change: str | None,
    ) -> bool:
        if not state.cliInstalled:
            return action_id == "onboard"
        if not state.initialized:
            return action_id in {"explore", "onboard"}
        if action_context.subview == OpenSpecActionContextSubview.COMPLETE:
            completed_changes = [
                change for change in navigation_changes
                if change.status == OpenSpecChangeStatus.COMPLETE
            ]
            if len(completed_changes) > 1:
                return action_id == "bulk-archive"
            if archive_target_change:
                return action_id == "archive"
            return False
        if action_context.subview == OpenSpecActionContextSubview.ARCHIVED:
            return False
        if state.activeChanges:
            return action_id in {"apply", "archive"}
        return action_id in {"propose", "explore"}

    def _resolve_archive_availability(
        self,
        action_context: OpenSpecActionContext,
        navigation_changes: list[OpenSpecNavigationChange],
        archive_target_change: str | None,
        translate: TranslateFn,
    ) -> tuple[OpenSpecActionAvailability, str | None]:
        if action_context.subview == OpenSpecActionContextSubview.ARCHIVED:
            return (
                OpenSpecActionAvailability.DISABLED,
                translate("openspec.actions.reason.archived_read_only"),
            )
        if archive_target_change:
            return OpenSpecActionAvailability.ENABLED, None
        if action_context.subview == OpenSpecActionContextSubview.COMPLETE:
            completed_changes = [
                change for change in navigation_changes
                if change.status == OpenSpecChangeStatus.COMPLETE
            ]
            if completed_changes:
                return (
                    OpenSpecActionAvailability.BLOCKED,
                    translate("openspec.actions.reason.no_focused_completed_change"),
                )
            return (
                OpenSpecActionAvailability.BLOCKED,
                translate("openspec.actions.reason.no_completed_change"),
            )
        return OpenSpecActionAvailability.BLOCKED, translate("openspec.actions.reason.no_active_change")

    def _resolve_bulk_archive_availability(
        self,
        action_context: OpenSpecActionContext,
        navigation_changes: list[OpenSpecNavigationChange],
        profile: OpenSpecActionProfile,
        translate: TranslateFn,
    ) -> tuple[OpenSpecActionAvailability, str | None]:
        completed_changes = [
            change for change in navigation_changes
            if change.status == OpenSpecChangeStatus.COMPLETE
        ]
        if action_context.subview == OpenSpecActionContextSubview.COMPLETE and len(completed_changes) > 1:
            return OpenSpecActionAvailability.ENABLED, None
        if profile == OpenSpecActionProfile.EXPANDED:
            return OpenSpecActionAvailability.ENABLED, None
        return OpenSpecActionAvailability.HIDDEN, translate("openspec.actions.reason.expanded_hidden")

    def _resolve_workspace_profile(self) -> OpenSpecWorkspaceProfile:
        raw_profile = (self._run_openspec(["config", "get", "profile"]) or "").strip().lower()
        if raw_profile == OpenSpecWorkspaceProfile.CORE.value:
            return OpenSpecWorkspaceProfile.CORE
        if raw_profile == OpenSpecWorkspaceProfile.EXPANDED.value:
            return OpenSpecWorkspaceProfile.EXPANDED
        if raw_profile == OpenSpecWorkspaceProfile.CUSTOM.value:
            return OpenSpecWorkspaceProfile.CUSTOM
        workflows = self._get_config_workflows()
        core_workflows = {"propose", "explore", "apply", "archive"}
        if set(workflows) <= core_workflows:
            return OpenSpecWorkspaceProfile.CORE
        return OpenSpecWorkspaceProfile.CUSTOM

    def _resolve_project_sync_state(
        self,
        profile: OpenSpecWorkspaceProfile,
        cli_installed: bool,
        initialized: bool,
    ) -> tuple[bool | None, set[str]]:
        if not cli_installed or not initialized:
            return None, set()
        expected = self._expected_project_command_ids(profile)
        if not expected:
            return None, set()
        actual = self._list_project_command_ids()
        missing = expected.difference(actual)
        return len(missing) == 0, missing

    def _expected_project_command_ids(self, profile: OpenSpecWorkspaceProfile) -> set[str]:
        if profile == OpenSpecWorkspaceProfile.CORE:
            return {"propose", "explore", "apply", "archive"}

        workflows = set(self._get_config_workflows())
        valid_actions = {
            "propose",
            "explore",
            "apply",
            "archive",
            "new",
            "continue",
            "ff",
            "verify",
            "sync",
            "bulk-archive",
            "onboard",
        }
        return workflows.intersection(valid_actions)

    def _list_project_command_ids(self) -> set[str]:
        commands_dir = self._workspace_path / ".claude" / "commands" / "opsx"
        if not commands_dir.is_dir():
            return set()
        return {
            file_path.stem
            for file_path in commands_dir.glob("*.md")
            if file_path.is_file()
        }

    def _get_config_workflows(self) -> list[str]:
        payload = self._run_openspec(["config", "get", "workflows"])
        if not payload:
            return []
        try:
            workflows = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(workflows, list):
            return []
        return [str(item) for item in workflows]

    def _to_action_profile(self, profile: OpenSpecWorkspaceProfile) -> OpenSpecActionProfile:
        if profile == OpenSpecWorkspaceProfile.CORE:
            return OpenSpecActionProfile.CORE
        return OpenSpecActionProfile.EXPANDED

    def _resolve_archive_target_change(
        self,
        state: OpenSpecWorkspaceState,
        navigation_changes: list[OpenSpecNavigationChange],
        action_context: OpenSpecActionContext,
    ) -> str | None:
        focused_change_name = action_context.focused_change_name
        if focused_change_name:
            focused_change = next(
                (change for change in navigation_changes if change.name == focused_change_name),
                None,
            )
            if focused_change is not None:
                if action_context.subview == OpenSpecActionContextSubview.COMPLETE:
                    if focused_change.status == OpenSpecChangeStatus.COMPLETE:
                        return focused_change.name
                elif action_context.subview == OpenSpecActionContextSubview.ARCHIVED:
                    return None
                elif focused_change.status == OpenSpecChangeStatus.IN_PROGRESS:
                    return focused_change.name

        if action_context.subview == OpenSpecActionContextSubview.COMPLETE:
            completed_changes = [
                change for change in navigation_changes
                if change.status == OpenSpecChangeStatus.COMPLETE
            ]
            if len(completed_changes) == 1:
                return completed_changes[0].name
            return None

        if action_context.subview == OpenSpecActionContextSubview.ARCHIVED:
            return None

        if state.activeChanges:
            return state.activeChanges[0].name
        return None

    def _resolve_draft_template(
        self,
        action: OpenSpecActionDefinition,
        *,
        current_change: str | None,
        archive_target_change: str | None,
    ) -> str:
        if action.action_id == "archive":
            if archive_target_change:
                return f"/opsx:archive {archive_target_change}"
            return "/opsx:archive "
        if action.action_id in {"apply", "continue", "ff", "verify", "sync"}:
            command = action.draft_template.split(" ", 1)[0]
            if current_change:
                return f"{command} {current_change}"
            return f"{command} "
        return action.draft_template

    def _list_active_changes(self) -> list[OpenSpecChangeSummary]:
        result = self._run_openspec(["list", "--json"])
        if not result:
            return []

        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            logger.warning("Failed to parse openspec list JSON output")
            return []

        changes = payload.get("changes") if isinstance(payload, dict) else []
        if not isinstance(changes, list):
            return []

        summaries: list[OpenSpecChangeSummary] = []
        for item in changes:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status == "complete":
                continue
            summaries.append(
                OpenSpecChangeSummary(
                    name=str(item.get("name", "")),
                    status=status if isinstance(status, str) else None,
                    completedTasks=int(item.get("completedTasks", 0) or 0),
                    totalTasks=int(item.get("totalTasks", 0) or 0),
                    lastModified=item.get("lastModified") if isinstance(item.get("lastModified"), str) else None,
                )
            )
        return summaries

    def _is_initialized(self) -> bool:
        openspec_dir = self._workspace_path / "openspec"
        return openspec_dir.is_dir() or (openspec_dir / "config.yaml").is_file()

    def _get_cli_version(self) -> str | None:
        if shutil.which("openspec") is None:
            return None
        output = self._run_openspec(["--version"])
        if not output:
            return None
        return output.strip()

    def _run_openspec(self, args: list[str]) -> str | None:
        try:
            completed = subprocess.run(
                ["openspec", *args],
                cwd=self._workspace_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("OpenSpec command failed: %s", exc)
            return None
        return completed.stdout

    def _list_navigation_changes(self) -> list[OpenSpecNavigationChange]:
        changes_dir = self._workspace_path / "openspec" / "changes"
        archive_dir = changes_dir / "archive"
        discovered: list[OpenSpecNavigationChange] = []

        if changes_dir.is_dir():
            for change_dir in sorted(changes_dir.iterdir(), key=lambda item: item.name):
                if not change_dir.is_dir() or change_dir.name == "archive":
                    continue
                discovered.append(self._build_navigation_change(change_dir, archived=False))

        if archive_dir.is_dir():
            for change_dir in sorted(archive_dir.iterdir(), key=lambda item: item.name):
                if not change_dir.is_dir():
                    continue
                discovered.append(self._build_navigation_change(change_dir, archived=True))

        return discovered

    def _build_navigation_change(self, change_dir: Path, *, archived: bool) -> OpenSpecNavigationChange:
        proposal_path = change_dir / "proposal.md"
        design_path = change_dir / "design.md"
        tasks_path = change_dir / "tasks.md"
        specs_dir = change_dir / "specs"

        completed_tasks = 0
        total_tasks = 0
        if tasks_path.is_file():
            completed_tasks, total_tasks = self._parse_task_progress(tasks_path)

        if archived:
            status = OpenSpecChangeStatus.ARCHIVED
        elif total_tasks > 0 and completed_tasks == total_tasks:
            status = OpenSpecChangeStatus.COMPLETE
        else:
            status = OpenSpecChangeStatus.IN_PROGRESS

        spec_documents: list[OpenSpecSpecDocument] = []
        if specs_dir.is_dir():
            for spec_file in sorted(specs_dir.glob("**/spec.md")):
                try:
                    capability_name = spec_file.parent.name
                except IndexError:
                    continue
                spec_documents.append(
                    OpenSpecSpecDocument(
                        capabilityName=capability_name,
                        path=self._to_workspace_path(spec_file),
                    )
                )

        return OpenSpecNavigationChange(
            name=change_dir.name,
            status=status,
            archived=archived,
            proposalPath=self._to_workspace_path(proposal_path) if proposal_path.is_file() else None,
            designPath=self._to_workspace_path(design_path) if design_path.is_file() else None,
            tasksPath=self._to_workspace_path(tasks_path) if tasks_path.is_file() else None,
            specs=spec_documents,
            completedTasks=completed_tasks,
            totalTasks=total_tasks,
            lastModified=self._get_last_modified(change_dir),
        )

    def _parse_task_progress(self, tasks_path: Path) -> tuple[int, int]:
        try:
            lines = tasks_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.warning("Failed to read tasks file for OpenSpec navigation: %s", exc)
            return (0, 0)

        checklist_lines = [line for line in lines if TASK_CHECKBOX_RE.match(line)]
        completed = sum(1 for line in checklist_lines if "[x]" in line.lower())
        return (completed, len(checklist_lines))

    def _get_last_modified(self, change_dir: Path) -> str | None:
        timestamps: list[float] = []
        try:
            for path in change_dir.rglob("*"):
                if path.is_file():
                    timestamps.append(path.stat().st_mtime)
        except OSError as exc:
            logger.warning("Failed to inspect OpenSpec change timestamps: %s", exc)
            return None

        if not timestamps:
            return None

        return datetime.fromtimestamp(max(timestamps), tz=UTC).isoformat().replace("+00:00", "Z")

    def _to_workspace_path(self, path: Path) -> str:
        return f"/{path.relative_to(self._workspace_path).as_posix()}"

    def _action(
        self,
        action_id: str,
        title_key: str,
        description_key: str,
        group: OpenSpecActionGroup,
        profile: OpenSpecActionProfile,
        *,
        requires_change: bool,
        supports_change_argument: bool,
        input_kind: OpenSpecActionInputKind,
        example_command: str | None,
        draft_template: str,
    ) -> OpenSpecActionDefinition:
        return OpenSpecActionDefinition(
            action_id=action_id,
            title_key=title_key,
            description_key=description_key,
            group=group,
            profile=profile,
            requires_change=requires_change,
            supports_change_argument=supports_change_argument,
            input_kind=input_kind,
            example_command=example_command,
            draft_template=draft_template,
        )

    def _get_translator(
        self,
        translate: TranslateFn | None,
        language: str | None,
    ) -> TranslateFn:
        if translate is not None:
            return translate

        from app.services.i18n_service import get_i18n_service

        i18n = get_i18n_service()
        resolved_language = i18n.resolve_language(language)
        return lambda key: i18n.translate(key, language=resolved_language)
