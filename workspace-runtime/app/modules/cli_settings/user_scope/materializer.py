"""Transactional one-shot Marketplace user-copy materialization."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import shutil
import stat
from collections import defaultdict
from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from .adapter import (
    StructuredDocumentKind,
    StructuredEntryMode,
    UserCopyAdapterError,
    UserCopyTargetKind,
    canonical_value_digest,
    extract_json_pointer,
    normalize_package_locator,
    rewrite_known_placeholders,
)
from .codecs import (
    JsonDocumentCodec,
    TomlDocumentCodec,
    directory_tree_revision,
    file_bytes_revision,
    fsync_directory,
    read_bytes,
    remove_file_exact,
    write_bytes_atomic,
)
from .paths import UserScopePathResolver, get_user_scope_path_resolver
from .planner import (
    PlannedUserCopyResource,
    UserCopyAction,
    UserCopyBaselineRequirement,
    UserCopyMaterializationPlan,
    UserCopyOverwriteApproval,
    UserCopyPlanConflict,
    UserCopyPlanStatus,
    compute_materialization_digest,
    validate_overwrite_approvals,
)

_MAX_JOURNAL_BYTES = 8 * 1024 * 1024


class UserCopyJournalPhase(str, Enum):
    """Durable transaction phases used by restart recovery."""

    PREPARED = "prepared"
    BACKED_UP = "backed-up"
    APPLYING = "applying"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling-back"
    ROLLED_BACK = "rolled-back"
    ROLLBACK_FAILED = "rollback-failed"


class UserCopyCrashPoint(str, Enum):
    """Deterministic test and recovery boundaries."""

    AFTER_PREPARED = "after-prepared"
    AFTER_BACKUP = "after-backup"
    AFTER_TARGET_WRITE_BEFORE_JOURNAL = "after-target-write-before-journal"
    AFTER_TARGET_APPLY = "after-target-apply"
    BEFORE_VERIFY = "before-verify"
    AFTER_VERIFY = "after-verify"
    BEFORE_FINALIZE = "before-finalize"


class UserCopyMaterializationError(RuntimeError):
    """A one-shot transaction failed with a stable error code."""

    def __init__(
        self,
        code: str,
        *,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.resource_id = resource_id


class UserCopyInjectedCrash(BaseException):
    """Simulate process termination without in-process rollback."""


@dataclass(frozen=True)
class MaterializedUserCopyResource:
    """Transient verified result for one copied user resource."""

    resource_type: str
    resource_id: str
    target_locator: str
    action: UserCopyAction
    content_digest: str


@dataclass(frozen=True)
class UserCopyMaterializationResult:
    """Verified result with no persistent ownership projection."""

    operation_id: str
    materialization_digest: str
    resources: tuple[MaterializedUserCopyResource, ...]
    journal_phase: UserCopyJournalPhase

    @property
    def created_count(self) -> int:
        return self._count(UserCopyAction.CREATE)

    @property
    def merged_count(self) -> int:
        return self._count(UserCopyAction.MERGE)

    @property
    def unchanged_count(self) -> int:
        return self._count(UserCopyAction.UNCHANGED)

    @property
    def overwritten_count(self) -> int:
        return self._count(UserCopyAction.OVERWRITE)

    def _count(self, action: UserCopyAction) -> int:
        return sum(resource.action is action for resource in self.resources)


@dataclass(frozen=True)
class UserCopyRecoveryResult:
    """Restart recovery outcome for one incomplete transaction."""

    operation_id: str
    action: str
    phase: UserCopyJournalPhase
    result: UserCopyMaterializationResult | None = None
    published: bool = False


@dataclass
class _BackupRecord:
    group_locator: str
    existed: bool
    target_kind: str
    revision: str | None
    mode: int | None = None
    backup_name: str | None = None
    displaced_relative_path: str | None = None
    staged_relative_path: str | None = None
    owned_target_identity: str | None = None

    def canonical_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "groupLocator": self.group_locator,
            "existed": self.existed,
            "targetKind": self.target_kind,
        }
        if self.revision is not None:
            result["revision"] = self.revision
        if self.mode is not None:
            result["mode"] = self.mode
        if self.backup_name is not None:
            result["backupName"] = self.backup_name
        if self.displaced_relative_path is not None:
            result["displacedRelativePath"] = self.displaced_relative_path
        if self.staged_relative_path is not None:
            result["stagedRelativePath"] = self.staged_relative_path
        if self.owned_target_identity is not None:
            result["ownedTargetIdentity"] = self.owned_target_identity
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> _BackupRecord:
        allowed = {
            "groupLocator",
            "existed",
            "targetKind",
            "revision",
            "mode",
            "backupName",
            "displacedRelativePath",
            "stagedRelativePath",
            "ownedTargetIdentity",
        }
        if (
            set(value) - allowed
            or not isinstance(value.get("groupLocator"), str)
            or not value["groupLocator"]
            or type(value.get("existed")) is not bool
            or value.get("targetKind") not in {"file", "directory"}
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        revision = value.get("revision")
        mode = value.get("mode")
        backup_name = value.get("backupName")
        displaced = value.get("displacedRelativePath")
        staged = value.get("stagedRelativePath")
        owned_identity = value.get("ownedTargetIdentity")
        if (
            (revision is not None and not _is_digest(revision))
            or (
                mode is not None
                and (type(mode) is not int or mode < 0 or mode > 0o7777)
            )
            or (backup_name is not None and not _is_safe_state_name(backup_name))
            or (displaced is not None and not _is_safe_relative_path(displaced))
            or (staged is not None and not _is_safe_relative_path(staged))
            or (owned_identity is not None and not _is_target_identity(owned_identity))
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        existed = value["existed"]
        backup_complete = (
            revision is not None and mode is not None and backup_name is not None
        )
        backup_absent = revision is None and mode is None and backup_name is None
        if (existed and not backup_complete) or (not existed and not backup_absent):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        if displaced is not None and not existed:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        if (staged is None) != (owned_identity is None):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        return cls(
            group_locator=value["groupLocator"],
            existed=existed,
            target_kind=value["targetKind"],
            revision=revision,
            mode=mode,
            backup_name=backup_name,
            displaced_relative_path=displaced,
            staged_relative_path=staged,
            owned_target_identity=owned_identity,
        )


@dataclass
class _OperationJournal:
    operation_id: str
    workspace_id: str
    target_client: str
    profile_digest: str
    materialization_digest: str
    contextual_materialization_digest: str
    plan: dict[str, Any]
    phase: UserCopyJournalPhase
    backups: dict[str, _BackupRecord] = field(default_factory=dict)
    applied_groups: list[str] = field(default_factory=list)
    inflight_group: str | None = None
    post_revisions: dict[str, str] = field(default_factory=dict)
    created_parent_directories: dict[str, list[str]] = field(default_factory=dict)
    last_error_code: str | None = None
    published: bool = False

    def canonical_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "journalVersion": 3,
            "operationId": self.operation_id,
            "workspaceId": self.workspace_id,
            "targetClient": self.target_client,
            "profileDigest": self.profile_digest,
            "materializationDigest": self.materialization_digest,
            "contextualMaterializationDigest": (self.contextual_materialization_digest),
            "plan": self.plan,
            "phase": self.phase.value,
            "backups": {
                key: self.backups[key].canonical_dict() for key in sorted(self.backups)
            },
            "appliedGroups": list(self.applied_groups),
            "postRevisions": {
                key: self.post_revisions[key] for key in sorted(self.post_revisions)
            },
            "createdParentDirectories": {
                key: sorted(self.created_parent_directories[key])
                for key in sorted(self.created_parent_directories)
            },
            "published": self.published,
        }
        if self.inflight_group is not None:
            result["inflightGroup"] = self.inflight_group
        if self.last_error_code is not None:
            result["lastErrorCode"] = self.last_error_code
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> _OperationJournal:
        allowed = {
            "journalVersion",
            "operationId",
            "workspaceId",
            "targetClient",
            "profileDigest",
            "materializationDigest",
            "contextualMaterializationDigest",
            "plan",
            "phase",
            "backups",
            "appliedGroups",
            "inflightGroup",
            "postRevisions",
            "createdParentDirectories",
            "lastErrorCode",
            "published",
        }
        required = {
            "journalVersion",
            "operationId",
            "workspaceId",
            "targetClient",
            "profileDigest",
            "materializationDigest",
            "contextualMaterializationDigest",
            "plan",
            "phase",
            "backups",
            "appliedGroups",
            "postRevisions",
            "createdParentDirectories",
            "published",
        }
        if (
            set(value) - allowed
            or not required.issubset(value)
            or type(value.get("journalVersion")) is not int
            or value["journalVersion"] != 3
            or not _is_operation_id(value.get("operationId"))
            or not isinstance(value.get("workspaceId"), str)
            or not value["workspaceId"]
            or value.get("targetClient") not in {"claude-code", "codex"}
            or not _is_digest(value.get("profileDigest"))
            or not _is_digest(value.get("materializationDigest"))
            or not _is_digest(value.get("contextualMaterializationDigest"))
            or not isinstance(value.get("plan"), dict)
            or not isinstance(value.get("backups"), dict)
            or not isinstance(value.get("appliedGroups"), list)
            or not isinstance(value.get("postRevisions"), dict)
            or not isinstance(value.get("createdParentDirectories"), dict)
            or type(value.get("published")) is not bool
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        try:
            phase = UserCopyJournalPhase(value["phase"])
        except (TypeError, ValueError) as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            ) from exc
        backups: dict[str, _BackupRecord] = {}
        for key, item in value["backups"].items():
            if not isinstance(key, str) or not isinstance(item, Mapping):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            record = _BackupRecord.from_dict(item)
            if record.group_locator != key:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            backups[key] = record
        applied_groups = value["appliedGroups"]
        if any(not isinstance(item, str) or not item for item in applied_groups) or len(
            set(applied_groups)
        ) != len(applied_groups):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        inflight = value.get("inflightGroup")
        if inflight is not None and (
            not isinstance(inflight, str) or not inflight or inflight in applied_groups
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        post_revisions: dict[str, str] = {}
        for key, item in value["postRevisions"].items():
            if not isinstance(key, str) or not _is_digest(item):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            post_revisions[key] = item
        created_parents: dict[str, list[str]] = {}
        for key, items in value["createdParentDirectories"].items():
            if (
                not isinstance(key, str)
                or not isinstance(items, list)
                or any(not _is_safe_relative_path(item) for item in items)
                or len(set(items)) != len(items)
            ):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            created_parents[key] = list(items)
        expected_post_keys = set(applied_groups)
        if inflight is not None:
            expected_post_keys.add(inflight)
        if (
            set(post_revisions) != expected_post_keys
            or set(created_parents) != expected_post_keys
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        last_error = value.get("lastErrorCode")
        if (phase is UserCopyJournalPhase.ROLLBACK_FAILED) != (
            last_error == "marketplace.user_copy.rollback_failed"
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        if value["published"] and phase is not UserCopyJournalPhase.COMPLETED:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        return cls(
            operation_id=value["operationId"],
            workspace_id=value["workspaceId"],
            target_client=value["targetClient"],
            profile_digest=value["profileDigest"],
            materialization_digest=value["materializationDigest"],
            contextual_materialization_digest=value["contextualMaterializationDigest"],
            plan=dict(value["plan"]),
            phase=phase,
            backups=backups,
            applied_groups=list(applied_groups),
            inflight_group=inflight,
            post_revisions=post_revisions,
            created_parent_directories=created_parents,
            last_error_code=last_error,
            published=value["published"],
        )


@dataclass(frozen=True)
class _PreparedTargetMutation:
    """One target post-image prepared before the write-ahead intent."""

    content_digests: Mapping[str, str]
    changed: bool
    post_revision: str | None = None
    pre_revision: str | None = None
    content: bytes | None = None
    directory_source: Path | None = None
    target_mode: int | None = None


ReadbackResolver = Callable[[PlannedUserCopyResource], Optional[str]]
CrashHook = Callable[[UserCopyCrashPoint, Optional[str]], None]


class UserCopyMaterializer:
    """Apply one-shot plans with durable backup and reverse rollback."""

    def __init__(
        self,
        *,
        operation_state_root: Path,
        paths: UserScopePathResolver | None = None,
        crash_hook: CrashHook | None = None,
    ) -> None:
        self._operation_state_root = operation_state_root
        self._paths = paths or get_user_scope_path_resolver()
        self._crash_hook = crash_hook

    def apply(
        self,
        plan: UserCopyMaterializationPlan,
        package_root: Path,
        *,
        operation_id: str,
        workspace_id: str,
        overwrite_approvals: Iterable[UserCopyOverwriteApproval] = (),
        contextual_materialization_digest: str | None = None,
        readback: ReadbackResolver | None = None,
    ) -> UserCopyMaterializationResult:
        """Apply, read back, and verify one exact one-shot plan."""

        approvals = tuple(overwrite_approvals)
        self._validate_plan(plan, approvals)
        context_digest = (
            contextual_materialization_digest or plan.materialization_digest
        )
        if not _is_digest(context_digest):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.materialization_mismatch"
            )
        operation_dir = self._operation_directory(operation_id)
        if operation_dir.exists() or operation_dir.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.operation_conflict"
            )
        operation_dir.mkdir(parents=False, exist_ok=False, mode=0o700)
        os.chmod(operation_dir, 0o700)
        fsync_directory(operation_dir.parent)
        journal = _OperationJournal(
            operation_id=operation_id,
            workspace_id=workspace_id,
            target_client=plan.target_client,
            profile_digest=plan.profile_digest,
            materialization_digest=plan.materialization_digest,
            contextual_materialization_digest=context_digest,
            plan=plan.canonical_dict(),
            phase=UserCopyJournalPhase.PREPARED,
        )
        self._write_journal(operation_dir, journal)
        self._hit(UserCopyCrashPoint.AFTER_PREPARED)

        try:
            self._validate_sources(plan, package_root)
            self._validate_execute_baselines(plan)
            self._backup_targets(plan, operation_dir, journal)
            journal.phase = UserCopyJournalPhase.BACKED_UP
            self._write_journal(operation_dir, journal)
            self._hit(UserCopyCrashPoint.AFTER_BACKUP)

            journal.phase = UserCopyJournalPhase.APPLYING
            self._write_journal(operation_dir, journal)
            payload_root = self._dependency_payload_root(plan)
            for group_locator, resources in self._target_groups(plan):
                prepared = self._prepare_target_group(
                    resources,
                    payload_root=payload_root,
                )
                if not prepared.changed:
                    continue
                if prepared.post_revision is None:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.apply_failed",
                        resource_id=resources[0].resource_id,
                    )
                journal.inflight_group = group_locator
                journal.post_revisions[group_locator] = prepared.post_revision
                journal.created_parent_directories[group_locator] = (
                    self._missing_parent_directories(resources[0].runtime_path)
                )
                self._stage_target_group(
                    resources,
                    prepared,
                    operation_id=operation_id,
                    journal=journal,
                    group_locator=group_locator,
                )
                self._write_journal(operation_dir, journal)
                self._commit_target_group(
                    resources,
                    prepared,
                    journal=journal,
                    group_locator=group_locator,
                )
                self._hit(
                    UserCopyCrashPoint.AFTER_TARGET_WRITE_BEFORE_JOURNAL,
                    group_locator,
                )
                if self._target_revision(resources[0]) != prepared.post_revision:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.apply_failed",
                        resource_id=resources[0].resource_id,
                    )
                journal.applied_groups.append(group_locator)
                journal.inflight_group = None
                self._write_journal(operation_dir, journal)
                self._hit(UserCopyCrashPoint.AFTER_TARGET_APPLY, group_locator)

            self._hit(UserCopyCrashPoint.BEFORE_VERIFY)
            journal.phase = UserCopyJournalPhase.VERIFYING
            self._write_journal(operation_dir, journal)
            resources = self._verify(plan, readback=readback)
            journal.phase = UserCopyJournalPhase.VERIFIED
            self._write_journal(operation_dir, journal)
            self._hit(UserCopyCrashPoint.AFTER_VERIFY)
            self._hit(UserCopyCrashPoint.BEFORE_FINALIZE)
            self._remove_displaced_targets(journal)
            journal.phase = UserCopyJournalPhase.COMPLETED
            self._write_journal(operation_dir, journal)
            return UserCopyMaterializationResult(
                operation_id=operation_id,
                materialization_digest=plan.materialization_digest,
                resources=resources,
                journal_phase=journal.phase,
            )
        except UserCopyInjectedCrash:
            raise
        except BaseException as exc:
            try:
                self._rollback(plan, operation_dir, journal)
            except BaseException as rollback_exc:
                journal.phase = UserCopyJournalPhase.ROLLBACK_FAILED
                journal.last_error_code = "marketplace.user_copy.rollback_failed"
                self._write_journal(operation_dir, journal)
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                ) from rollback_exc
            if isinstance(exc, UserCopyMaterializationError):
                raise
            raise UserCopyMaterializationError(
                "marketplace.user_copy.apply_failed"
            ) from exc

    def recover(
        self,
        candidate_plan: UserCopyMaterializationPlan,
        *,
        operation_id: str,
        overwrite_approvals: Iterable[UserCopyOverwriteApproval] = (),
        expected_contextual_materialization_digest: str | None = None,
    ) -> UserCopyRecoveryResult:
        """Return a published result or roll every pre-release phase back."""

        operation_dir = self._operation_directory(operation_id)
        journal = self._read_journal(operation_dir)
        plan = self._recovery_plan(journal, candidate_plan)
        self._validate_plan(plan, tuple(overwrite_approvals))
        if (
            expected_contextual_materialization_digest is not None
            and journal.contextual_materialization_digest
            != expected_contextual_materialization_digest
        ):
            raise UserCopyMaterializationError("marketplace.user_copy.plan_stale")
        self._validate_journal(plan, journal, operation_id=operation_id)
        if journal.phase is UserCopyJournalPhase.COMPLETED and journal.published:
            result = UserCopyMaterializationResult(
                operation_id=operation_id,
                materialization_digest=plan.materialization_digest,
                resources=self._result_from_plan(plan),
                journal_phase=journal.phase,
            )
            return UserCopyRecoveryResult(
                operation_id=operation_id,
                action="completed",
                phase=journal.phase,
                result=result,
                published=journal.published,
            )
        if journal.phase is UserCopyJournalPhase.ROLLBACK_FAILED:
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        self._rollback(plan, operation_dir, journal)
        return UserCopyRecoveryResult(
            operation_id=operation_id,
            action="rolled-back",
            phase=journal.phase,
            published=journal.published,
        )

    def has_transaction(self, operation_id: str) -> bool:
        """Return whether a recoverable transaction directory exists."""

        operation_dir = self._operation_directory(operation_id)
        return operation_dir.exists()

    def mark_published(self, operation_id: str) -> None:
        """Persist that target_client generation advanced for this completed copy."""

        operation_dir = self._operation_directory(operation_id)
        journal = self._read_journal(operation_dir)
        if journal.phase is not UserCopyJournalPhase.COMPLETED:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        journal.published = True
        self._write_journal(operation_dir, journal)

    def transaction_published(
        self,
        operation_id: str,
        *,
        expected_contextual_materialization_digest: str,
    ) -> bool:
        """Validate and report the retained post-release journal proof."""

        operation_dir = self._operation_directory(operation_id)
        journal = self._read_journal(operation_dir)
        if (
            journal.contextual_materialization_digest
            != expected_contextual_materialization_digest
        ):
            raise UserCopyMaterializationError("marketplace.user_copy.plan_stale")
        return journal.phase is UserCopyJournalPhase.COMPLETED and journal.published

    def finalize(self, operation_id: str) -> None:
        """Delete transaction-only journal and backup artifacts."""

        operation_dir = self._operation_directory(operation_id)
        journal = self._read_journal(operation_dir)
        if journal.phase not in {
            UserCopyJournalPhase.COMPLETED,
            UserCopyJournalPhase.ROLLED_BACK,
        }:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        shutil.rmtree(operation_dir)
        fsync_directory(operation_dir.parent)

    def _validate_plan(
        self,
        plan: UserCopyMaterializationPlan,
        approvals: tuple[UserCopyOverwriteApproval, ...],
    ) -> None:
        if (
            plan.status is UserCopyPlanStatus.BLOCKED
            or not plan.resources
            or compute_materialization_digest(plan) != plan.materialization_digest
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.materialization_mismatch"
            )
        try:
            validate_overwrite_approvals(plan, approvals)
        except UserCopyAdapterError as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.overwrite_approval_invalid"
            ) from exc
        for resource in plan.resources:
            self._assert_runtime_target(resource.runtime_path)

    def _validate_sources(
        self,
        plan: UserCopyMaterializationPlan,
        package_root: Path,
    ) -> None:
        try:
            root = package_root.resolve(strict=True)
        except OSError as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.source_reference_invalid"
            ) from exc
        for resource in plan.resources:
            relative = normalize_package_locator(resource.source_locator)
            candidate = package_root.joinpath(*relative.parts)
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
                if resolved != resource.source_path.resolve(strict=True):
                    raise ValueError("plan source path changed")
            except (OSError, ValueError) as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.source_reference_invalid",
                    resource_id=resource.resource_id,
                ) from exc
            if self._source_digest(resource, candidate) != resource.source_digest:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.materialization_mismatch",
                    resource_id=resource.resource_id,
                )

    def _validate_execute_baselines(
        self,
        plan: UserCopyMaterializationPlan,
    ) -> None:
        for resource in plan.resources:
            current = self._current_resource_digest(resource)
            if resource.baseline_requirement is UserCopyBaselineRequirement.ABSENT:
                valid = current is None
            else:
                valid = current == resource.baseline_revision
            if not valid:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.plan_stale",
                    resource_id=resource.resource_id,
                )

    def _backup_targets(
        self,
        plan: UserCopyMaterializationPlan,
        operation_dir: Path,
        journal: _OperationJournal,
    ) -> None:
        backup_dir = operation_dir / "backup"
        if backup_dir.is_symlink() or (backup_dir.exists() and not backup_dir.is_dir()):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(backup_dir, 0o700)
        for index, (group_locator, resources) in enumerate(self._target_groups(plan)):
            if not any(resource.changed for resource in resources):
                continue
            first = resources[0]
            target = first.runtime_path
            existed = target.exists() or target.is_symlink()
            if target.is_symlink():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.target_unsafe",
                    resource_id=first.resource_id,
                )
            target_kind = (
                "directory"
                if first.target_kind is UserCopyTargetKind.DIRECTORY
                else "file"
            )
            revision = (
                directory_tree_revision(target)
                if target_kind == "directory" and existed
                else (file_bytes_revision(target) if existed else None)
            )
            mode = stat.S_IMODE(target.stat().st_mode) if existed else None
            backup_name: str | None = None
            if existed:
                if target_kind == "directory":
                    backup_name = f"target-{index:04d}"
                    self._copy_directory(
                        target,
                        backup_dir / backup_name,
                        normalize_modes=False,
                    )
                else:
                    backup_name = f"target-{index:04d}.bin"
                    backup_path = backup_dir / backup_name
                    write_bytes_atomic(backup_path, read_bytes(target))
                    os.chmod(backup_path, 0o600)
            journal.backups[group_locator] = _BackupRecord(
                group_locator=group_locator,
                existed=existed,
                target_kind=target_kind,
                revision=revision,
                mode=mode,
                backup_name=backup_name,
            )
        fsync_directory(backup_dir)
        self._write_journal(operation_dir, journal)

    def _prepare_target_group(
        self,
        resources: list[PlannedUserCopyResource],
        *,
        payload_root: Path | None,
    ) -> _PreparedTargetMutation:
        first = resources[0]
        self._validate_group_baselines(resources)
        if first.target_kind is UserCopyTargetKind.FILE:
            if len(resources) != 1:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.duplicate_target"
                )
            content = first.source_path.read_bytes()
            source_mode = stat.S_IMODE(first.source_path.stat().st_mode)
            return _PreparedTargetMutation(
                content_digests={first.stable_id: first.content_digest},
                changed=first.changed,
                post_revision=first.content_digest if first.changed else None,
                pre_revision=self._target_revision(first),
                content=content,
                target_mode=0o700 if source_mode & 0o111 else 0o600,
            )
        if first.target_kind is UserCopyTargetKind.DIRECTORY:
            if len(resources) != 1:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.duplicate_target"
                )
            return _PreparedTargetMutation(
                content_digests={first.stable_id: first.content_digest},
                changed=first.changed,
                post_revision=first.content_digest if first.changed else None,
                pre_revision=self._target_revision(first),
                directory_source=first.source_path,
            )
        return self._prepare_structured_group(
            resources,
            payload_root=payload_root,
        )

    def _prepare_structured_group(
        self,
        resources: list[PlannedUserCopyResource],
        *,
        payload_root: Path | None,
    ) -> _PreparedTargetMutation:
        first = resources[0]
        pre_revision = self._target_revision(first)
        document = self._read_structured_document(first)
        changed = False
        content_digests: dict[str, str] = {}
        tokens = self._placeholder_tokens(first.target_client)
        for resource in resources:
            source_document = json.loads(
                resource.source_path.read_text(encoding="utf-8")
            )
            source_value = extract_json_pointer(
                source_document,
                resource.source_json_pointer,
            )
            try:
                value, _used_payload = rewrite_known_placeholders(
                    source_value,
                    tokens=tokens,
                    payload_root=payload_root,
                    validate_payload_reference=True,
                )
            except UserCopyAdapterError as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.source_reference_invalid",
                    resource_id=resource.resource_id,
                ) from exc
            digest = canonical_value_digest(value)
            if digest != resource.content_digest:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.materialization_mismatch",
                    resource_id=resource.resource_id,
                )
            current = self._resolve_structured_parent(document, resource)
            if resource.structured_entry_mode is StructuredEntryMode.MAPPING_ENTRY:
                if not isinstance(current, dict):
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.target_unsafe",
                        resource_id=resource.resource_id,
                    )
                entry_id = resource.structured_entry_id or ""
                if resource.action is UserCopyAction.UNCHANGED:
                    if (
                        entry_id not in current
                        or canonical_value_digest(current[entry_id]) != digest
                    ):
                        raise UserCopyMaterializationError(
                            "marketplace.user_copy.plan_stale",
                            resource_id=resource.resource_id,
                        )
                else:
                    current[entry_id] = value
                    changed = True
            elif resource.structured_entry_mode is StructuredEntryMode.LIST_ENTRY:
                if not isinstance(current, list):
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.target_unsafe",
                        resource_id=resource.resource_id,
                    )
                matches = [
                    item for item in current if canonical_value_digest(item) == digest
                ]
                if len(matches) > 1:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.effective_identity_conflict",
                        resource_id=resource.resource_id,
                    )
                if resource.action is UserCopyAction.UNCHANGED:
                    if len(matches) != 1:
                        raise UserCopyMaterializationError(
                            "marketplace.user_copy.plan_stale",
                            resource_id=resource.resource_id,
                        )
                elif not matches:
                    current.append(value)
                    changed = True
            else:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.materialization_mismatch"
                )
            content_digests[resource.stable_id] = digest

        if not changed:
            return _PreparedTargetMutation(
                content_digests=content_digests,
                changed=False,
                pre_revision=pre_revision,
            )
        content = self._serialize_structured_document(first, document)
        return _PreparedTargetMutation(
            content_digests=content_digests,
            changed=True,
            post_revision=sha256(content).hexdigest(),
            pre_revision=pre_revision,
            content=content,
        )

    def _stage_target_group(
        self,
        resources: list[PlannedUserCopyResource],
        prepared: _PreparedTargetMutation,
        *,
        operation_id: str,
        journal: _OperationJournal,
        group_locator: str,
    ) -> None:
        first = resources[0]
        target = first.runtime_path
        backup = journal.backups[group_locator]
        self._assert_runtime_target(target)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._assert_runtime_target(target)
        staged = target.with_name(f".{target.name}.{operation_id}.pending")
        self._assert_runtime_target(staged)
        if staged.exists() or staged.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_unsafe",
                resource_id=first.resource_id,
            )
        try:
            if first.target_kind is UserCopyTargetKind.DIRECTORY:
                if prepared.directory_source is None:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.apply_failed",
                        resource_id=first.resource_id,
                    )
                self._copy_directory(
                    prepared.directory_source,
                    staged,
                    normalize_modes=True,
                )
            else:
                if prepared.content is None:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.apply_failed",
                        resource_id=first.resource_id,
                    )
                write_bytes_atomic(staged, prepared.content)
                target_mode = (
                    prepared.target_mode
                    if prepared.target_mode is not None
                    else (backup.mode if backup.mode is not None else 0o600)
                )
                os.chmod(staged, target_mode)
                fsync_directory(staged.parent)
            if self._revision_at(first, staged) != prepared.post_revision:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.apply_failed",
                    resource_id=first.resource_id,
                )
        except BaseException:
            if staged.exists() and not staged.is_symlink():
                self._remove_staged_target(staged, backup.target_kind)
            raise
        backup.staged_relative_path = (
            staged.absolute().relative_to(self._paths.user_home.absolute()).as_posix()
        )
        backup.owned_target_identity = _target_identity(staged)
        if backup.existed:
            displaced = target.with_name(f".{target.name}.{operation_id}.previous")
            self._assert_runtime_target(displaced)
            if displaced.exists() or displaced.is_symlink():
                self._remove_staged_target(staged, backup.target_kind)
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.target_unsafe",
                    resource_id=first.resource_id,
                )
            backup.displaced_relative_path = (
                displaced.absolute()
                .relative_to(self._paths.user_home.absolute())
                .as_posix()
            )

    def _commit_target_group(
        self,
        resources: list[PlannedUserCopyResource],
        prepared: _PreparedTargetMutation,
        *,
        journal: _OperationJournal,
        group_locator: str,
    ) -> None:
        first = resources[0]
        backup = journal.backups[group_locator]
        self._assert_runtime_target(first.runtime_path)
        self._validate_group_baselines(resources)
        staged = self._staged_path(backup)
        if (
            staged is None
            or backup.owned_target_identity is None
            or not staged.exists()
            or staged.is_symlink()
            or _target_identity(staged) != backup.owned_target_identity
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid",
                resource_id=first.resource_id,
            )
        displaced = self._displaced_path(backup)
        if backup.existed:
            if displaced is None:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    resource_id=first.resource_id,
                )
            try:
                _rename_noreplace(first.runtime_path, displaced)
            except (FileExistsError, FileNotFoundError) as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.plan_stale",
                    resource_id=first.resource_id,
                ) from exc
            fsync_directory(first.runtime_path.parent)
            if not self._path_matches_backup(displaced, backup):
                try:
                    _rename_noreplace(displaced, first.runtime_path)
                    fsync_directory(first.runtime_path.parent)
                except (FileExistsError, FileNotFoundError):
                    pass
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.plan_stale",
                    resource_id=first.resource_id,
                )
        try:
            _rename_noreplace(staged, first.runtime_path)
        except (FileExistsError, FileNotFoundError) as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.plan_stale",
                resource_id=first.resource_id,
            ) from exc
        fsync_directory(first.runtime_path.parent)
        if _target_identity(first.runtime_path) != backup.owned_target_identity:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.apply_failed",
                resource_id=first.resource_id,
            )

    def _verify(
        self,
        plan: UserCopyMaterializationPlan,
        *,
        readback: ReadbackResolver | None,
    ) -> tuple[MaterializedUserCopyResource, ...]:
        verified: list[MaterializedUserCopyResource] = []
        for resource in plan.resources:
            current_digest = (
                readback(resource)
                if readback is not None
                else self._current_resource_digest(resource)
            )
            if current_digest != resource.content_digest:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.verification_failed",
                    resource_id=resource.resource_id,
                )
            verified.append(
                MaterializedUserCopyResource(
                    resource_type=resource.resource_type,
                    resource_id=resource.resource_id,
                    target_locator=resource.target_locator,
                    action=resource.action,
                    content_digest=current_digest,
                )
            )
        return tuple(verified)

    def _rollback(
        self,
        plan: UserCopyMaterializationPlan,
        operation_dir: Path,
        journal: _OperationJournal,
    ) -> None:
        journal.phase = UserCopyJournalPhase.ROLLING_BACK
        self._write_journal(operation_dir, journal)
        groups = {key: items for key, items in self._target_groups(plan)}
        rollback_groups = list(journal.applied_groups)
        if (
            journal.inflight_group is not None
            and journal.inflight_group not in rollback_groups
        ):
            rollback_groups.append(journal.inflight_group)
        for group_locator in reversed(rollback_groups):
            resources = groups.get(group_locator)
            backup = journal.backups.get(group_locator)
            if resources is None or backup is None:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
            self._restore_target(
                resources[0],
                backup,
                operation_id=journal.operation_id,
                operation_dir=operation_dir,
                expected_post_revision=journal.post_revisions.get(group_locator),
            )
        self._remove_created_parent_directories(journal)
        journal.phase = UserCopyJournalPhase.ROLLED_BACK
        journal.applied_groups.clear()
        journal.inflight_group = None
        journal.post_revisions.clear()
        journal.created_parent_directories.clear()
        journal.last_error_code = None
        for backup in journal.backups.values():
            backup.displaced_relative_path = None
            backup.staged_relative_path = None
            backup.owned_target_identity = None
        self._write_journal(operation_dir, journal)

    def _restore_target(
        self,
        resource: PlannedUserCopyResource,
        backup: _BackupRecord,
        *,
        operation_id: str,
        operation_dir: Path,
        expected_post_revision: str | None,
    ) -> None:
        target = resource.runtime_path
        self._assert_runtime_target(target)
        if target.is_symlink() or (
            target.exists()
            and (
                (
                    resource.target_kind is UserCopyTargetKind.DIRECTORY
                    and not target.is_dir()
                )
                or (
                    resource.target_kind is not UserCopyTargetKind.DIRECTORY
                    and not target.is_file()
                )
            )
        ):
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        displaced = self._displaced_path(backup)
        staged = self._staged_path(backup)
        rollback_capture = target.with_name(f".{target.name}.{operation_id}.rollback")
        self._assert_runtime_target(rollback_capture)

        if self._target_matches_backup(resource, backup):
            self._remove_staged_if_owned(staged, backup)
            self._remove_displaced_if_backup(displaced, backup)
            self._remove_rollback_capture(
                rollback_capture,
                resource,
                backup,
                expected_post_revision=expected_post_revision,
            )
            return

        if rollback_capture.exists() or rollback_capture.is_symlink():
            if not self._rollback_capture_matches(
                rollback_capture,
                resource,
                backup,
                expected_post_revision=expected_post_revision,
            ):
                self._restore_external_capture(
                    rollback_capture,
                    target,
                )
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
        elif target.exists():
            try:
                _rename_noreplace(target, rollback_capture)
            except (FileExistsError, FileNotFoundError) as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                ) from exc
            fsync_directory(target.parent)
            if not self._rollback_capture_matches(
                rollback_capture,
                resource,
                backup,
                expected_post_revision=expected_post_revision,
            ):
                restored = self._restore_external_capture(
                    rollback_capture,
                    target,
                )
                if (
                    restored
                    and staged is not None
                    and staged.exists()
                    and (displaced is None or not displaced.exists())
                ):
                    self._remove_staged_if_owned(staged, backup)
                    return
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )

        if backup.existed:
            if target.exists() or target.is_symlink():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
            if displaced is not None and displaced.exists():
                if not self._path_matches_backup(displaced, backup):
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.rollback_failed"
                    )
                try:
                    _rename_noreplace(displaced, target)
                except (FileExistsError, FileNotFoundError) as exc:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.rollback_failed"
                    ) from exc
                fsync_directory(target.parent)
            else:
                self._restore_backup_noreplace(
                    resource,
                    backup,
                    operation_id=operation_id,
                    operation_dir=operation_dir,
                )
        self._remove_rollback_capture(
            rollback_capture,
            resource,
            backup,
            expected_post_revision=expected_post_revision,
        )
        self._remove_staged_if_owned(staged, backup)

    def _validate_group_baselines(
        self,
        resources: list[PlannedUserCopyResource],
    ) -> None:
        for resource in resources:
            current = self._current_resource_digest(resource)
            if resource.baseline_requirement is UserCopyBaselineRequirement.ABSENT:
                valid = current is None
            else:
                valid = current == resource.baseline_revision
            if not valid:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.plan_stale",
                    resource_id=resource.resource_id,
                )

    def _current_resource_digest(
        self,
        resource: PlannedUserCopyResource,
    ) -> str | None:
        path = resource.runtime_path
        self._assert_runtime_target(path)
        missing = not path.exists() and not path.is_symlink()
        if missing:
            return None
        if resource.target_kind is UserCopyTargetKind.FILE:
            if path.is_file() and not path.is_symlink():
                return (
                    _dependency_file_digest(path)
                    if resource.resource_type == "dependency-payload"
                    else file_bytes_revision(path)
                )
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_unsafe",
                resource_id=resource.resource_id,
            )
        if resource.target_kind is UserCopyTargetKind.DIRECTORY:
            if path.is_dir() and not path.is_symlink():
                try:
                    if any(
                        child.is_symlink() or not (child.is_file() or child.is_dir())
                        for child in path.rglob("*")
                    ):
                        raise ValueError("unsafe directory entry")
                    return directory_tree_revision(path)
                except (OSError, ValueError) as exc:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.target_unsafe",
                        resource_id=resource.resource_id,
                    ) from exc
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_unsafe",
                resource_id=resource.resource_id,
            )
        if not path.is_file() or path.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_unsafe",
                resource_id=resource.resource_id,
            )
        document = self._read_structured_document(resource)
        current: Any = document
        for part in resource.structured_parent:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        if resource.structured_entry_mode is StructuredEntryMode.MAPPING_ENTRY:
            if not isinstance(current, dict):
                return None
            entry_id = resource.structured_entry_id or ""
            if entry_id not in current:
                return None
            return canonical_value_digest(current[entry_id])
        if resource.structured_entry_mode is StructuredEntryMode.LIST_ENTRY:
            if not isinstance(current, list):
                return None
            expected = resource.content_digest
            matches = [
                item for item in current if canonical_value_digest(item) == expected
            ]
            return expected if len(matches) == 1 else None
        return None

    def _source_digest(
        self,
        resource: PlannedUserCopyResource,
        source_path: Path,
    ) -> str:
        if resource.target_kind is UserCopyTargetKind.DIRECTORY:
            return _materialized_directory_digest(source_path)
        if resource.target_kind is UserCopyTargetKind.FILE:
            return (
                _dependency_file_digest(source_path)
                if resource.resource_type == "dependency-payload"
                else file_bytes_revision(source_path)
            )
        try:
            document = json.loads(source_path.read_text(encoding="utf-8"))
            value = extract_json_pointer(
                document,
                resource.source_json_pointer,
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            UserCopyAdapterError,
        ) as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.source_reference_invalid",
                resource_id=resource.resource_id,
            ) from exc
        return canonical_value_digest(value)

    def _read_structured_document(
        self,
        resource: PlannedUserCopyResource,
    ) -> dict[str, Any]:
        try:
            if resource.structured_document is StructuredDocumentKind.JSON:
                return JsonDocumentCodec(invalid_as_empty=False).read(
                    resource.runtime_path
                )
            if resource.structured_document is StructuredDocumentKind.TOML:
                return TomlDocumentCodec(invalid_as_empty=False).read(
                    resource.runtime_path
                )
        except Exception as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_document_invalid",
                resource_id=resource.resource_id,
            ) from exc
        raise UserCopyMaterializationError(
            "marketplace.user_copy.materialization_mismatch",
            resource_id=resource.resource_id,
        )

    @staticmethod
    def _resolve_structured_parent(
        document: dict[str, Any],
        resource: PlannedUserCopyResource,
    ) -> Any:
        current: Any = document
        for index, part in enumerate(resource.structured_parent):
            if not isinstance(current, dict):
                return current
            child = current.get(part)
            if child is None:
                child = (
                    []
                    if index == len(resource.structured_parent) - 1
                    and resource.structured_entry_mode is StructuredEntryMode.LIST_ENTRY
                    else {}
                )
                current[part] = child
            current = child
        return current

    @staticmethod
    def _serialize_structured_document(
        resource: PlannedUserCopyResource,
        document: Mapping[str, Any],
    ) -> bytes:
        if resource.structured_document is StructuredDocumentKind.JSON:
            return (
                JsonDocumentCodec(invalid_as_empty=False)
                .serialize(document)
                .encode("utf-8")
            )
        if resource.structured_document is StructuredDocumentKind.TOML:
            return (
                TomlDocumentCodec(invalid_as_empty=False)
                .serialize(document)
                .encode("utf-8")
            )
        raise UserCopyMaterializationError(
            "marketplace.user_copy.materialization_mismatch",
            resource_id=resource.resource_id,
        )

    def _copy_directory(
        self,
        source: Path,
        target: Path,
        *,
        normalize_modes: bool,
    ) -> None:
        if target.exists() or target.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        target.mkdir(parents=False, mode=0o700)
        os.chmod(
            target,
            (0o700 if normalize_modes else stat.S_IMODE(source.stat().st_mode)),
        )
        self._copy_tree_contents(
            source,
            target,
            normalize_modes=normalize_modes,
        )
        fsync_directory(target.parent)

    @staticmethod
    def _copy_tree_contents(
        source: Path,
        target: Path,
        *,
        normalize_modes: bool,
    ) -> None:
        for entry in sorted(
            source.rglob("*"),
            key=lambda path: path.relative_to(source).as_posix(),
        ):
            relative = entry.relative_to(source)
            destination = target / relative
            if entry.is_symlink():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.source_reference_invalid"
                )
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                mode = 0o700 if normalize_modes else stat.S_IMODE(entry.stat().st_mode)
                os.chmod(destination, mode)
                continue
            if not entry.is_file():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.source_reference_invalid"
                )
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(entry.read_bytes())
            source_mode = stat.S_IMODE(entry.stat().st_mode)
            mode = (
                (0o700 if source_mode & 0o111 else 0o600)
                if normalize_modes
                else source_mode
            )
            os.chmod(destination, mode)
            descriptor = os.open(destination, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        for directory in sorted(
            (path for path in target.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            fsync_directory(directory)

    def _remove_directory_exact(self, target: Path) -> None:
        self._assert_runtime_target(target)
        if target.is_symlink() or not target.is_dir():
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        shutil.rmtree(target)
        fsync_directory(target.parent)

    def _missing_parent_directories(self, target: Path) -> list[str]:
        self._assert_runtime_target(target)
        user_home = self._paths.user_home.absolute()
        missing: list[str] = []
        current = target.absolute().parent
        while current != user_home:
            if current.exists() or current.is_symlink():
                break
            missing.append(current.relative_to(user_home).as_posix())
            current = current.parent
        return missing

    def _remove_created_parent_directories(
        self,
        journal: _OperationJournal,
    ) -> None:
        user_home = self._paths.user_home.absolute()
        relative_paths = {
            relative
            for paths in journal.created_parent_directories.values()
            for relative in paths
        }
        for relative in sorted(
            relative_paths,
            key=lambda value: len(Path(value).parts),
            reverse=True,
        ):
            path = user_home.joinpath(*Path(relative).parts)
            self._assert_runtime_target(path)
            if path.is_symlink() or not path.is_dir():
                continue
            try:
                path.rmdir()
            except OSError:
                continue
            fsync_directory(path.parent)

    def _remove_displaced_targets(self, journal: _OperationJournal) -> None:
        for backup in journal.backups.values():
            displaced = self._displaced_path(backup)
            if displaced is not None and displaced.exists():
                self._remove_displaced_if_backup(displaced, backup)

    def _displaced_path(self, backup: _BackupRecord) -> Path | None:
        relative = backup.displaced_relative_path
        if relative is None:
            return None
        path = self._paths.user_home.joinpath(*Path(relative).parts)
        self._assert_runtime_target(path)
        return path

    def _staged_path(self, backup: _BackupRecord) -> Path | None:
        relative = backup.staged_relative_path
        if relative is None:
            return None
        path = self._paths.user_home.joinpath(*Path(relative).parts)
        self._assert_runtime_target(path)
        return path

    @staticmethod
    def _path_matches_backup(path: Path, backup: _BackupRecord) -> bool:
        if (
            not backup.existed
            or backup.revision is None
            or backup.mode is None
            or path.is_symlink()
        ):
            return False
        if backup.target_kind == "directory":
            return (
                path.is_dir()
                and directory_tree_revision(path) == backup.revision
                and stat.S_IMODE(path.stat().st_mode) == backup.mode
            )
        return (
            path.is_file()
            and file_bytes_revision(path) == backup.revision
            and stat.S_IMODE(path.stat().st_mode) == backup.mode
        )

    def _remove_displaced_if_backup(
        self,
        displaced: Path | None,
        backup: _BackupRecord,
    ) -> None:
        if displaced is None:
            return
        self._discard_after_atomic_capture(
            displaced,
            target_kind=backup.target_kind,
            validator=lambda path: self._path_matches_backup(path, backup),
        )

    def _remove_staged_if_owned(
        self,
        staged: Path | None,
        backup: _BackupRecord,
    ) -> None:
        if staged is None:
            return
        expected_identity = backup.owned_target_identity
        if expected_identity is None:
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        self._discard_after_atomic_capture(
            staged,
            target_kind=backup.target_kind,
            validator=lambda path: (
                not path.is_symlink() and _target_identity(path) == expected_identity
            ),
        )

    def _remove_rollback_capture(
        self,
        capture: Path,
        resource: PlannedUserCopyResource,
        backup: _BackupRecord,
        *,
        expected_post_revision: str | None,
    ) -> None:
        if not capture.exists() and not capture.is_symlink():
            return
        self._discard_after_atomic_capture(
            capture,
            target_kind=backup.target_kind,
            validator=lambda path: self._rollback_capture_matches(
                path,
                resource,
                backup,
                expected_post_revision=expected_post_revision,
            ),
        )

    def _discard_after_atomic_capture(
        self,
        path: Path,
        *,
        target_kind: str,
        validator: Callable[[Path], bool],
    ) -> None:
        discard = path.with_name(f"{path.name}.discard")
        self._assert_runtime_target(path)
        self._assert_runtime_target(discard)
        if discard.exists() or discard.is_symlink():
            if path.exists() or path.is_symlink() or not validator(discard):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
        elif path.exists() or path.is_symlink():
            try:
                _rename_noreplace(path, discard)
            except (FileExistsError, FileNotFoundError) as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                ) from exc
            fsync_directory(path.parent)
            if not validator(discard):
                self._restore_external_capture(discard, path)
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
        else:
            return
        self._remove_staged_target(discard, target_kind)

    def _rollback_capture_matches(
        self,
        capture: Path,
        resource: PlannedUserCopyResource,
        backup: _BackupRecord,
        *,
        expected_post_revision: str | None,
    ) -> bool:
        return (
            expected_post_revision is not None
            and backup.owned_target_identity is not None
            and capture.exists()
            and not capture.is_symlink()
            and _target_identity(capture) == backup.owned_target_identity
            and self._revision_at(resource, capture) == expected_post_revision
        )

    @staticmethod
    def _restore_external_capture(
        capture: Path,
        target: Path,
    ) -> bool:
        if target.exists() or target.is_symlink():
            return False
        try:
            _rename_noreplace(capture, target)
        except (FileExistsError, FileNotFoundError):
            return False
        fsync_directory(target.parent)
        return True

    def _restore_backup_noreplace(
        self,
        resource: PlannedUserCopyResource,
        backup: _BackupRecord,
        *,
        operation_id: str,
        operation_dir: Path,
    ) -> None:
        if backup.backup_name is None or backup.mode is None or backup.revision is None:
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        backup_root = operation_dir / "backup"
        backup_path = backup_root / backup.backup_name
        _assert_safe_state_path(
            backup_path,
            backup_root,
            expect_directory=(backup.target_kind == "directory"),
        )
        target = resource.runtime_path
        restore = target.with_name(f".{target.name}.{operation_id}.restore")
        self._assert_runtime_target(restore)
        if restore.exists() or restore.is_symlink():
            if not self._path_matches_backup(restore, backup):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.rollback_failed"
                )
        elif backup.target_kind == "directory":
            self._copy_directory(
                backup_path,
                restore,
                normalize_modes=False,
            )
        else:
            write_bytes_atomic(restore, backup_path.read_bytes())
            os.chmod(restore, backup.mode)
            fsync_directory(restore.parent)
        if not self._path_matches_backup(restore, backup):
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        try:
            _rename_noreplace(restore, target)
        except (FileExistsError, FileNotFoundError) as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.rollback_failed"
            ) from exc
        fsync_directory(target.parent)
        if not self._path_matches_backup(target, backup):
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")

    def _remove_staged_target(
        self,
        target: Path,
        target_kind: str,
    ) -> None:
        if target_kind == "directory":
            self._remove_directory_exact(target)
            return
        if target.is_symlink() or not target.is_file():
            raise UserCopyMaterializationError("marketplace.user_copy.rollback_failed")
        remove_file_exact(target)

    @staticmethod
    def _revision_at(
        resource: PlannedUserCopyResource,
        path: Path,
    ) -> str | None:
        if resource.target_kind is UserCopyTargetKind.DIRECTORY:
            if path.is_dir() and not path.is_symlink():
                return directory_tree_revision(path)
            return None
        if path.is_file() and not path.is_symlink():
            return (
                _dependency_file_digest(path)
                if resource.resource_type == "dependency-payload"
                else file_bytes_revision(path)
            )
        return None

    @staticmethod
    def _target_revision(resource: PlannedUserCopyResource) -> str | None:
        path = resource.runtime_path
        if resource.target_kind is UserCopyTargetKind.DIRECTORY:
            if path.is_dir() and not path.is_symlink():
                return directory_tree_revision(path)
            return None
        if path.is_file() and not path.is_symlink():
            return (
                _dependency_file_digest(path)
                if resource.resource_type == "dependency-payload"
                else file_bytes_revision(path)
            )
        return None

    @staticmethod
    def _target_matches_backup(
        resource: PlannedUserCopyResource,
        backup: _BackupRecord,
    ) -> bool:
        path = resource.runtime_path
        if not backup.existed:
            return not path.exists() and not path.is_symlink()
        if backup.target_kind == "directory":
            return (
                path.is_dir()
                and not path.is_symlink()
                and directory_tree_revision(path) == backup.revision
                and stat.S_IMODE(path.stat().st_mode) == backup.mode
            )
        return (
            path.is_file()
            and not path.is_symlink()
            and file_bytes_revision(path) == backup.revision
            and stat.S_IMODE(path.stat().st_mode) == backup.mode
        )

    def _target_groups(
        self,
        plan: UserCopyMaterializationPlan,
    ) -> list[tuple[str, list[PlannedUserCopyResource]]]:
        return self._target_groups_static(plan)

    def _dependency_payload_root(
        self,
        plan: UserCopyMaterializationPlan,
    ) -> Path | None:
        roots: set[Path] = set()
        for resource in plan.resources:
            if resource.resource_type != "dependency-payload":
                continue
            try:
                relative = normalize_package_locator(resource.source_locator)
            except UserCopyAdapterError as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.materialization_mismatch",
                    resource_id=resource.resource_id,
                ) from exc
            root = resource.runtime_path
            for _part in relative.parts:
                root = root.parent
            roots.add(root)
        if len(roots) > 1:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.materialization_mismatch"
            )
        if not roots:
            return None
        root = roots.pop()
        self._assert_runtime_target(root)
        return root

    def _operation_directory(self, operation_id: str) -> Path:
        if not _is_operation_id(operation_id):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.operation_id_invalid"
            )
        if self._operation_state_root.is_symlink() or (
            self._operation_state_root.exists()
            and not self._operation_state_root.is_dir()
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        try:
            self._operation_state_root.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o700,
            )
            os.chmod(self._operation_state_root, 0o700)
        except OSError as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            ) from exc
        operation_dir = self._operation_state_root / operation_id
        if operation_dir.is_symlink() or (
            operation_dir.exists() and not operation_dir.is_dir()
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        return operation_dir

    @staticmethod
    def _write_journal(
        operation_dir: Path,
        journal: _OperationJournal,
    ) -> None:
        if operation_dir.is_symlink() or not operation_dir.is_dir():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        target = operation_dir / "journal.json"
        temporary = operation_dir / ".journal.tmp"
        if target.is_symlink() or temporary.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        encoded = json.dumps(
            journal.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > _MAX_JOURNAL_BYTES:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            fsync_directory(operation_dir)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_journal(operation_dir: Path) -> _OperationJournal:
        if operation_dir.is_symlink() or not operation_dir.is_dir():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        target = operation_dir / "journal.json"
        temporary = operation_dir / ".journal.tmp"
        if temporary.is_symlink() or (temporary.exists() and not temporary.is_file()):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        if temporary.exists():
            temporary.unlink()
            fsync_directory(operation_dir)
        if target.is_symlink() or not target.is_file():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        try:
            if target.stat().st_size > _MAX_JOURNAL_BYTES:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            encoded = target.read_bytes()
            if len(encoded) > _MAX_JOURNAL_BYTES:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            value = json.loads(encoded)
        except UserCopyMaterializationError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            ) from exc
        if not isinstance(value, Mapping):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        journal = _OperationJournal.from_dict(value)
        expected_entries = {"journal.json"}
        expected_backups = {
            backup.backup_name
            for backup in journal.backups.values()
            if backup.backup_name is not None
        }
        backup_root = operation_dir / "backup"
        if expected_backups:
            expected_entries.add("backup")
            if backup_root.is_symlink() or not backup_root.is_dir():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            actual_backups = {item.name for item in backup_root.iterdir()}
            if actual_backups != expected_backups:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            for backup in journal.backups.values():
                if backup.backup_name is None:
                    continue
                _assert_safe_state_path(
                    backup_root / backup.backup_name,
                    backup_root,
                    expect_directory=(backup.target_kind == "directory"),
                )
        elif backup_root.exists() or backup_root.is_symlink():
            if (
                backup_root.is_symlink()
                or not backup_root.is_dir()
                or any(backup_root.iterdir())
            ):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            expected_entries.add("backup")
        if {item.name for item in operation_dir.iterdir()} != expected_entries:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        return journal

    @staticmethod
    def _validate_journal(
        plan: UserCopyMaterializationPlan,
        journal: _OperationJournal,
        *,
        operation_id: str,
    ) -> None:
        groups = {
            group_locator: resources
            for group_locator, resources in UserCopyMaterializer._target_groups_static(
                plan
            )
        }
        changed_groups = {
            group_locator
            for group_locator, resources in groups.items()
            if any(resource.changed for resource in resources)
        }
        backup_keys = set(journal.backups)
        applied = set(journal.applied_groups)
        inflight = (
            {journal.inflight_group} if journal.inflight_group is not None else set()
        )
        terminal_apply_phases = {
            UserCopyJournalPhase.VERIFYING,
            UserCopyJournalPhase.VERIFIED,
            UserCopyJournalPhase.COMPLETED,
        }
        staged_groups = {
            key
            for key, backup in journal.backups.items()
            if backup.staged_relative_path is not None
        }
        displaced_groups = {
            key
            for key, backup in journal.backups.items()
            if backup.displaced_relative_path is not None
        }
        expected_staged_groups = applied | inflight
        if journal.phase in {
            UserCopyJournalPhase.ROLLED_BACK,
            UserCopyJournalPhase.ROLLING_BACK,
        }:
            expected_staged_groups = {
                key
                for key in applied | inflight
                if journal.backups[key].staged_relative_path is not None
            }
        if (
            journal.operation_id != operation_id
            or journal.target_client != plan.target_client
            or journal.profile_digest != plan.profile_digest
            or journal.materialization_digest != plan.materialization_digest
            or not backup_keys.issubset(changed_groups)
            or not applied.issubset(changed_groups)
            or not inflight.issubset(changed_groups)
            or set(journal.post_revisions) != applied | inflight
            or set(journal.created_parent_directories) != applied | inflight
            or staged_groups != expected_staged_groups
            or not displaced_groups.issubset(staged_groups)
            or any(not journal.backups[key].existed for key in displaced_groups)
            or (
                journal.phase not in {UserCopyJournalPhase.PREPARED}
                and backup_keys != changed_groups
            )
            or (
                journal.phase
                in {
                    UserCopyJournalPhase.PREPARED,
                    UserCopyJournalPhase.BACKED_UP,
                }
                and (applied or inflight)
            )
            or (
                journal.phase in terminal_apply_phases
                and (applied != changed_groups or inflight)
            )
            or (
                journal.phase is UserCopyJournalPhase.COMPLETED
                and journal.last_error_code is not None
            )
            or (
                journal.phase is UserCopyJournalPhase.ROLLBACK_FAILED
                and journal.last_error_code != "marketplace.user_copy.rollback_failed"
            )
            or (
                journal.phase is not UserCopyJournalPhase.ROLLBACK_FAILED
                and journal.last_error_code is not None
            )
            or (
                journal.published
                and journal.phase is not UserCopyJournalPhase.COMPLETED
            )
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )

    @staticmethod
    def _recovery_plan(
        journal: _OperationJournal,
        candidate_plan: UserCopyMaterializationPlan,
    ) -> UserCopyMaterializationPlan:
        """Restore mutation baselines from a strict canonical plan proof."""

        proof = journal.plan
        if (
            set(proof)
            != {
                "status",
                "packageFormat",
                "targetClient",
                "profileVersion",
                "profileDigest",
                "resources",
                "conflicts",
                "blockingIssues",
                "skippedResources",
                "projectionDigest",
                "materializationDigest",
            }
            or proof.get("packageFormat") != candidate_plan.package_format
            or proof.get("targetClient") != candidate_plan.target_client
            or proof.get("profileVersion") != candidate_plan.profile_version
            or proof.get("profileDigest") != candidate_plan.profile_digest
            or proof.get("materializationDigest") != journal.materialization_digest
            or proof.get("projectionDigest") != candidate_plan.projection_digest
            or proof.get("status")
            not in {
                UserCopyPlanStatus.READY.value,
                UserCopyPlanStatus.CONFIRMATION_REQUIRED.value,
            }
            or not isinstance(proof.get("resources"), list)
            or not isinstance(proof.get("conflicts"), list)
            or proof.get("blockingIssues") != []
            or proof.get("skippedResources")
            != [
                item.canonical_dict() for item in candidate_plan.skipped_resources
            ]
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )

        candidates = {
            resource.stable_id: resource for resource in candidate_plan.resources
        }
        if len(candidates) != len(candidate_plan.resources):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        resources: list[PlannedUserCopyResource] = []
        seen: set[str] = set()
        resource_allowed = {
            "targetClient",
            "resourceType",
            "resourceId",
            "sourceKind",
            "sourceLocator",
            "sourceDigest",
            "contentDigest",
            "targetKind",
            "targetScope",
            "targetLocator",
            "targetIdentity",
            "action",
            "baselineRequirement",
            "baselineRevision",
            "sourceJsonPointer",
            "structuredDocument",
            "structuredEntryMode",
            "structuredParent",
            "structuredEntryId",
        }
        mutation_keys = {
            "action",
            "baselineRequirement",
            "baselineRevision",
        }
        for raw_resource in proof["resources"]:
            if not isinstance(raw_resource, Mapping):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            resource_type = raw_resource.get("resourceType")
            resource_id = raw_resource.get("resourceId")
            if (
                set(raw_resource) - resource_allowed
                or not isinstance(resource_type, str)
                or not isinstance(resource_id, str)
            ):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            stable_id = f"{resource_type}:{resource_id}"
            candidate = candidates.get(stable_id)
            if candidate is None or stable_id in seen:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            seen.add(stable_id)
            candidate_proof = candidate.canonical_dict()
            if {
                key: value
                for key, value in raw_resource.items()
                if key not in mutation_keys
            } != {
                key: value
                for key, value in candidate_proof.items()
                if key not in mutation_keys
            }:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            try:
                action = UserCopyAction(raw_resource.get("action"))
                baseline_requirement = UserCopyBaselineRequirement(
                    raw_resource.get("baselineRequirement")
                )
            except (TypeError, ValueError) as exc:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                ) from exc
            baseline_revision = raw_resource.get("baselineRevision")
            if baseline_requirement is UserCopyBaselineRequirement.ABSENT:
                if baseline_revision is not None or action not in {
                    UserCopyAction.CREATE,
                    UserCopyAction.MERGE,
                }:
                    raise UserCopyMaterializationError(
                        "marketplace.user_copy.runtime_state_invalid"
                    )
            elif not _is_digest(baseline_revision) or action not in {
                UserCopyAction.UNCHANGED,
                UserCopyAction.OVERWRITE,
            }:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            resources.append(
                replace(
                    candidate,
                    action=action,
                    baseline_requirement=baseline_requirement,
                    baseline_revision=baseline_revision,
                )
            )
        if seen != set(candidates):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )

        resource_by_target = {
            resource.target_identity: resource
            for resource in resources
            if resource.action is UserCopyAction.OVERWRITE
        }
        conflicts: list[UserCopyPlanConflict] = []
        for raw_conflict in proof["conflicts"]:
            if (
                not isinstance(raw_conflict, Mapping)
                or set(raw_conflict)
                != {
                    "code",
                    "resourceType",
                    "resourceId",
                    "sourceLocator",
                    "targetLocator",
                    "targetIdentity",
                    "baselineRevision",
                    "incomingDigest",
                    "overwritable",
                }
                or raw_conflict.get("code") != "marketplace.user_copy.target_conflict"
                or raw_conflict.get("overwritable") is not True
            ):
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            target_identity = raw_conflict.get("targetIdentity")
            resource = (
                resource_by_target.get(target_identity)
                if isinstance(target_identity, str)
                else None
            )
            if resource is None:
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            expected = UserCopyPlanConflict(
                code="marketplace.user_copy.target_conflict",
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                source_locator=resource.source_locator,
                target_locator=resource.target_locator,
                target_identity=resource.target_identity,
                baseline_revision=resource.baseline_revision or "",
                incoming_digest=resource.content_digest,
            )
            if dict(raw_conflict) != expected.canonical_dict():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.runtime_state_invalid"
                )
            conflicts.append(expected)
        if len(conflicts) != len(resource_by_target) or {
            conflict.target_identity for conflict in conflicts
        } != set(resource_by_target):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )

        status = UserCopyPlanStatus(proof["status"])
        expected_status = (
            UserCopyPlanStatus.CONFIRMATION_REQUIRED
            if conflicts or candidate_plan.skipped_resources
            else UserCopyPlanStatus.READY
        )
        if status is not expected_status:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        plan = UserCopyMaterializationPlan(
            package_format=candidate_plan.package_format,
            target_client=candidate_plan.target_client,
            profile_version=candidate_plan.profile_version,
            profile_digest=candidate_plan.profile_digest,
            status=status,
            resources=tuple(resources),
            conflicts=tuple(conflicts),
            blocking_issues=tuple(),
            skipped_resources=candidate_plan.skipped_resources,
            projection_digest=candidate_plan.projection_digest,
            materialization_digest=journal.materialization_digest,
        )
        if (
            plan.canonical_dict() != proof
            or compute_materialization_digest(plan) != journal.materialization_digest
        ):
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
        return plan

    @staticmethod
    def _result_from_plan(
        plan: UserCopyMaterializationPlan,
    ) -> tuple[MaterializedUserCopyResource, ...]:
        return tuple(
            MaterializedUserCopyResource(
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                target_locator=resource.target_locator,
                action=resource.action,
                content_digest=resource.content_digest,
            )
            for resource in plan.resources
        )

    @staticmethod
    def _target_groups_static(
        plan: UserCopyMaterializationPlan,
    ) -> list[tuple[str, list[PlannedUserCopyResource]]]:
        groups: defaultdict[Path, list[PlannedUserCopyResource]] = defaultdict(list)
        for resource in plan.resources:
            groups[resource.runtime_path].append(resource)
        return [
            (
                _target_file_locator(resources[0]),
                sorted(resources, key=lambda item: item.stable_id),
            )
            for _path, resources in sorted(
                groups.items(),
                key=lambda item: (
                    0 if item[1][0].resource_type == "dependency-payload" else 1,
                    _target_file_locator(item[1][0]),
                ),
            )
        ]

    def _assert_runtime_target(self, target: Path) -> None:
        self._assert_below(target, self._paths.user_home)
        current = self._paths.user_home.absolute()
        relative = target.absolute().relative_to(current)
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise UserCopyMaterializationError(
                    "marketplace.user_copy.target_unsafe"
                )

    @staticmethod
    def _assert_below(target: Path, allowed_root: Path) -> None:
        try:
            relative = target.absolute().relative_to(allowed_root.absolute())
        except ValueError as exc:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_not_writable"
            ) from exc
        if not relative.parts:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.target_not_writable"
            )

    def _hit(
        self,
        point: UserCopyCrashPoint,
        target_locator: str | None = None,
    ) -> None:
        if self._crash_hook is not None:
            self._crash_hook(point, target_locator)

    @staticmethod
    def _placeholder_tokens(target_client: str) -> tuple[str, ...]:
        if target_client == "claude-code":
            return ("${CLAUDE_PLUGIN_ROOT}",)
        if target_client == "codex":
            return ("PLUGIN_ROOT", "${PLUGIN_ROOT}", "${CODEX_PLUGIN_ROOT}")
        raise UserCopyMaterializationError(
            "marketplace.user_copy.materialization_mismatch"
        )


def _target_file_locator(resource: PlannedUserCopyResource) -> str:
    return resource.target_locator.split("#", 1)[0]


def _materialized_directory_digest(source: Path) -> str:
    digest = sha256()
    for path in sorted(
        source.rglob("*"),
        key=lambda item: item.relative_to(source).as_posix(),
    ):
        relative = path.relative_to(source).as_posix().encode("utf-8")
        if path.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.source_reference_invalid"
            )
        if path.is_dir():
            entry_type = b"directory"
            mode = 0o700
            content = b""
        elif path.is_file():
            entry_type = b"file"
            source_mode = stat.S_IMODE(path.stat().st_mode)
            mode = 0o700 if source_mode & 0o111 else 0o600
            content = path.read_bytes()
        else:
            raise UserCopyMaterializationError(
                "marketplace.user_copy.source_reference_invalid"
            )
        for component in (
            entry_type,
            f"{mode:o}".encode("ascii"),
            relative,
            content,
        ):
            digest.update(len(component).to_bytes(8, "big"))
            digest.update(component)
    return digest.hexdigest()


def _dependency_file_digest(path: Path) -> str:
    source_mode = stat.S_IMODE(path.stat().st_mode)
    normalized_mode = 0o700 if source_mode & 0o111 else 0o600
    digest = sha256()
    for component in (
        b"file",
        f"{normalized_mode:o}".encode("ascii"),
        path.read_bytes(),
    ):
        digest.update(len(component).to_bytes(8, "big"))
        digest.update(component)
    return digest.hexdigest()


def _target_identity(path: Path) -> str:
    metadata = path.stat(follow_symlinks=False)
    return f"{metadata.st_dev}:{metadata.st_ino}"


def _is_target_identity(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 128:
        return False
    parts = value.split(":")
    return len(parts) == 2 and all(part.isascii() and part.isdigit() for part in parts)


def _rename_noreplace(source: Path, target: Path) -> None:
    """Atomically publish one staged path without replacing another writer."""

    error_number = _renameat2_noreplace(source, target)
    if error_number is None:
        return
    if error_number in {
        errno.EINVAL,
        errno.ENOSYS,
        errno.ENOTSUP,
        errno.EOPNOTSUPP,
    }:
        _portable_rename_noreplace(source, target)
        return
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(error_number, os.strerror(error_number), target)
    if error_number == errno.ENOENT:
        raise FileNotFoundError(error_number, os.strerror(error_number), source)
    raise OSError(error_number, os.strerror(error_number), source, target)


def _renameat2_noreplace(source: Path, target: Path) -> int | None:
    """Return the errno when Linux cannot complete a no-replace rename."""

    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        return errno.ENOSYS
    result = renameat2(
        ctypes.c_int(-100),
        ctypes.c_char_p(os.fsencode(source)),
        ctypes.c_int(-100),
        ctypes.c_char_p(os.fsencode(target)),
        ctypes.c_uint(1),
    )
    if result == 0:
        return None
    return ctypes.get_errno()


def _portable_rename_noreplace(source: Path, target: Path) -> None:
    """Publish on filesystems that reject Linux renameat2 flags."""

    try:
        os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), target)

    metadata = os.lstat(source)
    if stat.S_ISREG(metadata.st_mode):
        os.link(source, target, follow_symlinks=False)
        try:
            source.unlink()
        except BaseException:
            try:
                if _target_identity(source) == _target_identity(target):
                    target.unlink()
            except (FileNotFoundError, OSError):
                pass
            raise
        return
    if stat.S_ISDIR(metadata.st_mode):
        os.rename(source, target)
        return
    raise UserCopyMaterializationError("marketplace.user_copy.runtime_state_invalid")


def _is_operation_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_safe_state_name(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


def _is_safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    path = Path(value)
    return not path.is_absolute() and all(
        part not in {"", ".", ".."} for part in path.parts
    )


def _assert_safe_state_path(
    path: Path,
    root: Path,
    *,
    expect_directory: bool,
) -> None:
    if root.is_symlink() or not root.is_dir():
        raise UserCopyMaterializationError(
            "marketplace.user_copy.runtime_state_invalid"
        )
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise UserCopyMaterializationError(
            "marketplace.user_copy.runtime_state_invalid"
        ) from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise UserCopyMaterializationError(
                "marketplace.user_copy.runtime_state_invalid"
            )
    if (expect_directory and not path.is_dir()) or (
        not expect_directory and not path.is_file()
    ):
        raise UserCopyMaterializationError(
            "marketplace.user_copy.runtime_state_invalid"
        )
