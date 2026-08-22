"""Deterministic one-shot Marketplace user-copy planner."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from aileron_marketplace_core import (
    PluginPackageFormat,
    TargetClient,
    UserCopySourceProfile,
)

from .adapter import (
    CoreProfileResource,
    TargetClientUserScopeAdapter,
    ResolvedUserCopyTarget,
    StructuredDocumentKind,
    StructuredEntryMode,
    UserCopyAdapterError,
    UserCopyOperation,
    UserCopyTargetKind,
    canonical_value_digest,
    normalized_file_identity,
    normalize_package_locator,
    rewrite_known_placeholders,
    validate_sha256_digest,
)
from .codecs import (
    JsonDocumentCodec,
    TomlDocumentCodec,
    directory_tree_revision,
    file_bytes_revision,
)
from .paths import UserScopePathResolver, get_user_scope_path_resolver
from .projection import UserCopyProjectionRegistry

_PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_USER_COPY_FIELD_LENGTH = 1024
_PUBLIC_USER_COPY_RESOURCE_TYPES = frozenset(
    {
        "instructions",
        "skill",
        "subagent",
        "command",
        "output-style",
        "prompt",
        "rule",
        "mcp",
        "hook",
        "dependency-payload",
    }
)


class UserCopyPlanStatus(str, Enum):
    """One-shot preflight outcome."""

    READY = "ready"
    CONFIRMATION_REQUIRED = "confirmation-required"
    BLOCKED = "blocked"


class UserCopyBaselineRequirement(str, Enum):
    """Execute-time target requirements."""

    ABSENT = "absent"
    EXACT_REVISION = "exact-revision"


class UserCopyAction(str, Enum):
    """Mutation classification exposed by the one-shot plan."""

    CREATE = "create"
    MERGE = "merge"
    UNCHANGED = "unchanged"
    OVERWRITE = "overwrite"


@dataclass(frozen=True)
class EffectiveUserCopyIdentity:
    """One effective resource outside the planned user target."""

    target_client: str
    resource_type: str
    resource_id: str
    scope: str

    @property
    def normalized_identity(self) -> str:
        return f"{self.target_client}:{self.resource_type}:{self.resource_id}".casefold()


@dataclass(frozen=True)
class UserCopyInventory:
    """Target client-wide semantic identities used by preflight."""

    complete: bool
    effective_identities: tuple[EffectiveUserCopyIdentity, ...] = ()


@dataclass(frozen=True)
class UserCopyOverwriteApproval:
    """Exact caller approval for one observed conflicting target."""

    target_identity: str
    expected_revision: str

    def canonical_dict(self) -> dict[str, str]:
        return {
            "targetIdentity": self.target_identity,
            "expectedRevision": self.expected_revision,
        }


@dataclass(frozen=True)
class UserCopyPlanConflict:
    """A content conflict that can be explicitly overwritten."""

    code: str
    resource_type: str
    resource_id: str
    source_locator: str
    target_locator: str
    target_identity: str
    baseline_revision: str
    incoming_digest: str
    overwritable: bool = True

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "sourceLocator": self.source_locator,
            "targetLocator": self.target_locator,
            "targetIdentity": self.target_identity,
            "baselineRevision": self.baseline_revision,
            "incomingDigest": self.incoming_digest,
            "overwritable": self.overwritable,
        }


@dataclass(frozen=True)
class UserCopyBlockingIssue:
    """A planner issue that cannot be bypassed by overwrite approval."""

    code: str
    resource_type: str | None = None
    resource_id: str | None = None
    source_locator: str | None = None
    target_locator: str | None = None

    def canonical_dict(self) -> dict[str, str]:
        result = {"code": self.code}
        if self.resource_type is not None:
            result["resourceType"] = self.resource_type
        if self.resource_id is not None:
            result["resourceId"] = self.resource_id
        if self.source_locator is not None:
            result["sourceLocator"] = self.source_locator
        if self.target_locator is not None:
            result["targetLocator"] = self.target_locator
        return result


@dataclass(frozen=True)
class PlannedUserCopyResource:
    """One source-to-user-scope target in a deterministic plan."""

    target_client: str
    resource_type: str
    resource_id: str
    source_kind: str
    source_locator: str
    source_digest: str
    content_digest: str
    target_kind: UserCopyTargetKind
    target_scope: str
    target_locator: str
    target_identity: str
    action: UserCopyAction
    baseline_requirement: UserCopyBaselineRequirement
    baseline_revision: str | None
    runtime_path: Path
    source_path: Path
    source_json_pointer: str | None = None
    structured_document: StructuredDocumentKind | None = None
    structured_entry_mode: StructuredEntryMode | None = None
    structured_parent: tuple[str, ...] = ()
    structured_entry_id: str | None = None

    @property
    def stable_id(self) -> str:
        return f"{self.resource_type}:{self.resource_id}"

    @property
    def changed(self) -> bool:
        return self.action is not UserCopyAction.UNCHANGED

    def canonical_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "targetClient": self.target_client,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "sourceKind": self.source_kind,
            "sourceLocator": self.source_locator,
            "sourceDigest": self.source_digest,
            "contentDigest": self.content_digest,
            "targetKind": self.target_kind.value,
            "targetScope": self.target_scope,
            "targetLocator": self.target_locator,
            "targetIdentity": self.target_identity,
            "action": self.action.value,
            "baselineRequirement": self.baseline_requirement.value,
        }
        if self.baseline_revision is not None:
            result["baselineRevision"] = self.baseline_revision
        if self.source_json_pointer is not None:
            result["sourceJsonPointer"] = self.source_json_pointer
        if self.structured_document is not None:
            result["structuredDocument"] = self.structured_document.value
        if self.structured_entry_mode is not None:
            result["structuredEntryMode"] = self.structured_entry_mode.value
        if self.structured_parent:
            result["structuredParent"] = list(self.structured_parent)
        if self.structured_entry_id is not None:
            result["structuredEntryId"] = self.structured_entry_id
        return result


@dataclass(frozen=True)
class UserCopyMaterializationPlan:
    """Sanitized one-shot plan plus Runtime-only resolved paths."""

    package_format: str
    target_client: str
    profile_version: int
    profile_digest: str
    status: UserCopyPlanStatus
    resources: tuple[PlannedUserCopyResource, ...]
    conflicts: tuple[UserCopyPlanConflict, ...]
    blocking_issues: tuple[UserCopyBlockingIssue, ...]
    projection_digest: str
    materialization_digest: str
    skipped_resources: tuple[SkippedUserCopyPlanResource, ...] = ()

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status.value,
            "packageFormat": self.package_format,
            "targetClient": self.target_client,
            "profileVersion": self.profile_version,
            "profileDigest": self.profile_digest,
            "resources": [resource.canonical_dict() for resource in self.resources],
            "conflicts": [conflict.canonical_dict() for conflict in self.conflicts],
            "blockingIssues": [
                issue.canonical_dict() for issue in self.blocking_issues
            ],
            "projectionDigest": self.projection_digest,
            "skippedResources": [
                item.canonical_dict() for item in self.skipped_resources
            ],
        }
        if include_digest:
            result["materializationDigest"] = self.materialization_digest
        return result


@dataclass(frozen=True)
class SkippedUserCopyPlanResource:
    """A source resource intentionally omitted by an exact projection."""

    code: str
    resource_type: str
    resource_id: str
    source_locator: str

    def canonical_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "sourceLocator": self.source_locator,
        }


def compute_projection_digest(plan: UserCopyMaterializationPlan) -> str:
    payload = plan.canonical_dict(include_digest=False)
    payload.pop("projectionDigest", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def compute_materialization_digest(plan: UserCopyMaterializationPlan) -> str:
    """Recompute a plan proof without trusting its supplied digest."""

    payload = plan.canonical_dict(include_digest=False)
    payload["projectionDigest"] = compute_projection_digest(plan)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def validate_overwrite_approvals(
    plan: UserCopyMaterializationPlan,
    approvals: Iterable[UserCopyOverwriteApproval],
) -> None:
    """Require approvals to exactly match every conflict in one plan."""

    expected = {
        (conflict.target_identity, conflict.baseline_revision)
        for conflict in plan.conflicts
    }
    supplied_list = [
        (approval.target_identity, approval.expected_revision) for approval in approvals
    ]
    supplied = set(supplied_list)
    if (
        len(supplied) != len(supplied_list)
        or supplied != expected
        or plan.blocking_issues
    ):
        raise UserCopyAdapterError(
            "overwrite-approval-invalid",
            "approval-set-mismatch",
        )


@dataclass(frozen=True)
class _AdaptedProfile:
    target_client: str
    profile_version: int
    profile_digest: str
    resources: tuple[CoreProfileResource, ...]
    blocked_resources: tuple[UserCopyBlockingIssue, ...]


@dataclass(frozen=True)
class _DependencyPayload:
    source_locator: str
    source_kind: str
    content_digest: str


class UserCopyPlanner:
    """Plan safe one-shot mutations without changing Runtime state."""

    def __init__(
        self,
        *,
        package_id: str,
        release_revision: str = "0" * 64,
        paths: UserScopePathResolver | None = None,
    ) -> None:
        if not isinstance(package_id, str) or _PACKAGE_ID.fullmatch(package_id) is None:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "package-id-invalid",
            )
        self._package_id = package_id
        self._release_revision = validate_sha256_digest(release_revision)
        self._paths = paths or get_user_scope_path_resolver()

    def plan_source_profile(
        self,
        profile: UserCopySourceProfile,
        *,
        target_client: TargetClient | str,
        package_root: Path | None,
        inventory: UserCopyInventory,
    ) -> UserCopyMaterializationPlan:
        """Project a package-format profile into one target client's user scope."""

        client = TargetClient(target_client)
        try:
            projection = UserCopyProjectionRegistry().resolve(
                profile.package_format,
                client,
            )
        except ValueError:
            return self._finish_source_plan(
                profile,
                client,
                resources=[],
                conflicts=[],
                blocking=[UserCopyBlockingIssue(
                    code="marketplace.user_copy.projection_not_supported"
                )],
                skipped=[],
            )

        adapter = self._adapter(client.value)
        resources: list[PlannedUserCopyResource] = []
        conflicts: list[UserCopyPlanConflict] = []
        blocking: list[UserCopyBlockingIssue] = []
        skipped: list[SkippedUserCopyPlanResource] = []
        payloads: dict[str, _DependencyPayload] = {}

        if not inventory.complete:
            blocking.append(UserCopyBlockingIssue(
                code="marketplace.user_copy.inventory_unavailable"
            ))
        for diagnostic in profile.diagnostics:
            is_portability_diagnostic = (
                diagnostic.resource_type is not None
                and (
                    profile.package_format is PluginPackageFormat.AGENT_PLUGIN_V1
                    or diagnostic.code in {
                        "format-unsupported",
                        "source-not-allowed",
                        "unsupported-resource",
                    }
                )
            )
            if is_portability_diagnostic:
                skipped.append(SkippedUserCopyPlanResource(
                    code=diagnostic.code,
                    resource_type=diagnostic.resource_type,
                    resource_id=(diagnostic.resource_id or Path(
                        diagnostic.source_locator
                    ).stem or diagnostic.resource_type),
                    source_locator=diagnostic.source_locator,
                ))
            else:
                blocking.append(UserCopyBlockingIssue(
                    code=f"marketplace.user_copy.{diagnostic.code.replace('-', '_')}",
                    resource_type=diagnostic.resource_type,
                    resource_id=diagnostic.resource_id,
                    source_locator=diagnostic.source_locator,
                ))

        seen_resource_ids: set[str] = set()
        for source in profile.resources:
            projected_result = projection.project(source)
            if projected_result.skipped is not None:
                skipped.append(SkippedUserCopyPlanResource(
                    code=projected_result.skipped.code,
                    resource_type=source.resource_type.value,
                    resource_id=source.resource_id,
                    source_locator=source.source_locator,
                ))
                continue
            projected = projected_result.projected
            if projected is None:
                continue
            resource = CoreProfileResource(
                resource_type=source.resource_type.value,
                resource_id=source.resource_id,
                source_kind=source.source_kind.value,
                source_locator=source.source_locator,
                target_resource=projected.target_resource,
                copy_semantics=projected.copy_semantics,
                relative_target=projected.relative_target,
                json_pointer=source.source_json_pointer,
            )
            stable_identity = (
                f"{client.value}:{resource.resource_type}:{resource.resource_id}"
            ).casefold()
            if stable_identity in seen_resource_ids:
                blocking.append(_blocking_for_resource(
                    "marketplace.user_copy.duplicate_target", resource
                ))
                continue
            seen_resource_ids.add(stable_identity)
            try:
                planned, conflict, issues = self._plan_source_resource(
                    client.value,
                    adapter,
                    resource,
                    source_digest=source.source_digest,
                    structured_value=projected.structured_value,
                    package_root=package_root,
                    has_dependencies=bool(source.dependency_references),
                )
            except UserCopyAdapterError as exc:
                blocking.append(_blocking_for_resource(
                    _adapter_error_code(exc.code), resource
                ))
                continue
            resources.append(planned)
            if conflict is not None:
                conflicts.append(conflict)
            blocking.extend(issues)
            blocking.extend(self._effective_identity_issues(
                client.value,
                resource,
                inventory=inventory,
                target_locator=planned.target_locator,
            ))
            for reference in source.dependency_references:
                payloads.setdefault(reference.source_locator, _DependencyPayload(
                    source_locator=reference.source_locator,
                    source_kind=reference.source_kind,
                    content_digest=reference.source_digest,
                ))

        for payload in payloads.values():
            try:
                planned, conflict, issues = self._plan_payload(
                    client.value, payload, package_root=package_root
                )
            except UserCopyAdapterError as exc:
                blocking.append(UserCopyBlockingIssue(
                    code=_adapter_error_code(exc.code),
                    resource_type="dependency-payload",
                    resource_id=payload.source_locator,
                    source_locator=payload.source_locator,
                ))
                continue
            resources.append(planned)
            if conflict is not None:
                conflicts.append(conflict)
            blocking.extend(issues)

        self._detect_duplicate_targets(resources, blocking)
        if not profile.resources and not skipped:
            blocking.append(UserCopyBlockingIssue(
                code="marketplace.user_copy.profile_empty"
            ))
        return self._finish_source_plan(
            profile,
            client,
            resources=resources,
            conflicts=conflicts,
            blocking=blocking,
            skipped=skipped,
        )

    def _plan_source_resource(
        self,
        target_client: str,
        adapter: TargetClientUserScopeAdapter,
        resource: CoreProfileResource,
        *,
        source_digest: str,
        structured_value: Any | None,
        package_root: Path | None,
        has_dependencies: bool,
    ) -> tuple[
        PlannedUserCopyResource,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        source_digest = validate_sha256_digest(source_digest)
        source_relative = normalize_package_locator(resource.source_locator)
        source_path = (
            package_root.joinpath(*source_relative.parts)
            if package_root is not None
            else Path(*source_relative.parts)
        )
        value = structured_value
        if resource.copy_semantics == "merge-config-entry" and has_dependencies:
            value, used_payload = rewrite_known_placeholders(
                value,
                tokens=adapter.placeholder_tokens,
                payload_root=self._dependency_payload_root(target_client),
                validate_payload_reference=False,
            )
            if not used_payload:
                raise UserCopyAdapterError(
                    "profile-contract-invalid",
                    "dependency-template-mismatch",
                )
        target = adapter.resolve_target(
            resource,
            source_value=value,
            source_digest=(
                canonical_value_digest(value)
                if resource.resource_type == "hook" and value is not None
                else None
            ),
        )
        content_digest = (
            canonical_value_digest(value)
            if resource.copy_semantics == "merge-config-entry"
            else source_digest
        )
        return self._planned_target(
            target_client,
            resource,
            target,
            source_digest=source_digest,
            content_digest=content_digest,
            source_path=source_path,
        )

    def _finish_source_plan(
        self,
        profile: UserCopySourceProfile,
        target_client: TargetClient,
        *,
        resources: list[PlannedUserCopyResource],
        conflicts: list[UserCopyPlanConflict],
        blocking: list[UserCopyBlockingIssue],
        skipped: list[SkippedUserCopyPlanResource],
    ) -> UserCopyMaterializationPlan:
        resources_tuple = tuple(sorted(resources, key=_planned_resource_sort_key))
        conflicts_tuple = tuple(sorted(set(conflicts), key=lambda item: (
            item.target_identity, item.resource_type, item.resource_id
        )))
        blocking_tuple = tuple(sorted(set(blocking), key=lambda item: (
            item.code, item.resource_type or "", item.resource_id or "",
            item.target_locator or "",
        )))
        skipped_tuple = tuple(sorted(set(skipped), key=lambda item: (
            item.code, item.resource_type, item.resource_id, item.source_locator
        )))
        status = (
            UserCopyPlanStatus.BLOCKED if blocking_tuple else
            UserCopyPlanStatus.CONFIRMATION_REQUIRED
            if conflicts_tuple or skipped_tuple else
            UserCopyPlanStatus.READY
        )
        initial = UserCopyMaterializationPlan(
            package_format=profile.package_format.value,
            target_client=target_client.value,
            profile_version=profile.profile_version,
            profile_digest=profile.profile_digest,
            status=status,
            resources=resources_tuple,
            conflicts=conflicts_tuple,
            blocking_issues=blocking_tuple,
            projection_digest="",
            materialization_digest="",
            skipped_resources=skipped_tuple,
        )
        projection_digest = compute_projection_digest(initial)
        with_projection = UserCopyMaterializationPlan(
            package_format=initial.package_format,
            target_client=initial.target_client,
            profile_version=initial.profile_version,
            profile_digest=initial.profile_digest,
            status=initial.status,
            resources=initial.resources,
            conflicts=initial.conflicts,
            blocking_issues=initial.blocking_issues,
            projection_digest=projection_digest,
            materialization_digest="",
            skipped_resources=initial.skipped_resources,
        )
        return UserCopyMaterializationPlan(
            package_format=with_projection.package_format,
            target_client=with_projection.target_client,
            profile_version=with_projection.profile_version,
            profile_digest=with_projection.profile_digest,
            status=with_projection.status,
            resources=with_projection.resources,
            conflicts=with_projection.conflicts,
            blocking_issues=with_projection.blocking_issues,
            projection_digest=with_projection.projection_digest,
            materialization_digest=compute_materialization_digest(with_projection),
            skipped_resources=with_projection.skipped_resources,
        )

    def _adapter(self, target_client: str) -> TargetClientUserScopeAdapter:
        if target_client == "codex":
            from .codex import get_codex_user_copy_adapter

            return get_codex_user_copy_adapter(self._paths)
        if target_client == "claude-code":
            from .claude import get_claude_user_copy_adapter

            return get_claude_user_copy_adapter(self._paths)
        raise UserCopyAdapterError("target_client-not-supported", target_client)

    def _dependency_payload_root(self, target_client: str) -> Path:
        return (
            self._paths.user_home
            / ".aileron"
            / "user-copy-payloads"
            / target_client
            / self._package_id
            / self._release_revision
        )

    def _plan_payload(
        self,
        target_client: str,
        payload: _DependencyPayload,
        *,
        package_root: Path | None,
    ) -> tuple[
        PlannedUserCopyResource,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        relative = normalize_package_locator(payload.source_locator)
        target_kind = UserCopyTargetKind(payload.source_kind)
        source_path = (
            package_root.joinpath(*relative.parts)
            if package_root is not None
            else Path(*relative.parts)
        )
        if package_root is not None:
            _validate_payload_source(
                source_path,
                target_kind=target_kind,
                expected_digest=payload.content_digest,
            )
        logical_locator = (
            f"~/.aileron/user-copy-payloads/{target_client}/{self._package_id}/"
            f"{self._release_revision}/"
            f"{relative.as_posix()}"
        )
        target = ResolvedUserCopyTarget(
            agent=self._adapter(target_client).agent,
            target_kind=target_kind,
            operation=UserCopyOperation.CREATE,
            runtime_path=self._dependency_payload_root(target_client).joinpath(
                *relative.parts
            ),
            logical_locator=logical_locator,
            normalized_identity=normalized_file_identity(logical_locator),
        )
        resource = CoreProfileResource(
            resource_type="dependency-payload",
            resource_id=payload.source_locator,
            source_kind="dependency-payload",
            source_locator=payload.source_locator,
            target_resource="dependency-payload",
            copy_semantics=(
                "create-directory"
                if target_kind is UserCopyTargetKind.DIRECTORY
                else "create-file"
            ),
            relative_target=payload.source_locator,
            json_pointer=None,
        )
        return self._planned_target(
            target_client,
            resource,
            target,
            source_digest=payload.content_digest,
            content_digest=payload.content_digest,
            source_path=source_path,
        )


    def _planned_target(
        self,
        target_client: str,
        resource: CoreProfileResource,
        target: ResolvedUserCopyTarget,
        *,
        source_digest: str,
        content_digest: str,
        source_path: Path,
    ) -> tuple[
        PlannedUserCopyResource,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        if any(
            len(value) > _MAX_USER_COPY_FIELD_LENGTH
            for value in (
                resource.resource_id,
                resource.source_locator,
                target.logical_locator,
                target.normalized_identity,
            )
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "resource-field-too-long",
            )
        action, baseline, conflict, issues = self._target_state(
            resource,
            target,
            incoming_digest=content_digest,
        )
        return (
            PlannedUserCopyResource(
                target_client=target_client,
                resource_type=resource.resource_type,
                resource_id=resource.resource_id,
                source_kind=resource.source_kind,
                source_locator=resource.source_locator,
                source_digest=source_digest,
                content_digest=content_digest,
                target_kind=target.target_kind,
                target_scope="user",
                target_locator=target.logical_locator,
                target_identity=target.normalized_identity,
                action=action,
                baseline_requirement=(
                    UserCopyBaselineRequirement.EXACT_REVISION
                    if baseline is not None
                    else UserCopyBaselineRequirement.ABSENT
                ),
                baseline_revision=baseline,
                runtime_path=target.runtime_path,
                source_path=source_path,
                source_json_pointer=resource.json_pointer,
                structured_document=target.structured_document,
                structured_entry_mode=target.structured_entry_mode,
                structured_parent=target.structured_parent,
                structured_entry_id=target.structured_entry_id,
            ),
            conflict,
            issues,
        )

    def _target_state(
        self,
        resource: CoreProfileResource,
        target: ResolvedUserCopyTarget,
        *,
        incoming_digest: str,
    ) -> tuple[
        UserCopyAction,
        str | None,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        path_error = self._validate_runtime_target(target.runtime_path)
        if path_error is not None:
            return (
                _initial_action(target.target_kind),
                None,
                None,
                [
                    _blocking_for_resource(
                        path_error,
                        resource,
                        target_locator=target.logical_locator,
                    )
                ],
            )

        if target.target_kind is UserCopyTargetKind.FILE:
            if target.runtime_path.is_symlink() or (
                target.runtime_path.exists() and not target.runtime_path.is_file()
            ):
                return self._unsafe_target(resource, target)
            if not target.runtime_path.exists():
                return UserCopyAction.CREATE, None, None, []
            try:
                revision = (
                    _dependency_file_digest(target.runtime_path)
                    if resource.resource_type == "dependency-payload"
                    else file_bytes_revision(target.runtime_path)
                )
            except OSError:
                return self._unsafe_target(resource, target)
            return self._content_state(
                resource,
                target,
                incoming_digest=incoming_digest,
                baseline_revision=revision,
            )

        if target.target_kind is UserCopyTargetKind.DIRECTORY:
            if target.runtime_path.is_symlink() or (
                target.runtime_path.exists() and not target.runtime_path.is_dir()
            ):
                return self._unsafe_target(resource, target)
            if not target.runtime_path.exists():
                return UserCopyAction.CREATE, None, None, []
            try:
                unsafe_entry = any(
                    path.is_symlink() or not (path.is_file() or path.is_dir())
                    for path in target.runtime_path.rglob("*")
                )
                if unsafe_entry:
                    return self._unsafe_target(resource, target)
                revision = directory_tree_revision(target.runtime_path)
            except (OSError, ValueError):
                return self._unsafe_target(resource, target)
            return self._content_state(
                resource,
                target,
                incoming_digest=incoming_digest,
                baseline_revision=revision,
            )

        document, document_error = _read_target_document(target)
        if document_error is not None:
            return (
                UserCopyAction.MERGE,
                None,
                None,
                [
                    _blocking_for_resource(
                        document_error,
                        resource,
                        target_locator=target.logical_locator,
                    )
                ],
            )
        entry_exists, entry_digest, identifiable = _structured_entry_state(
            document,
            target,
        )
        if not identifiable:
            return (
                UserCopyAction.MERGE,
                None,
                None,
                [
                    _blocking_for_resource(
                        "marketplace.user_copy.effective_identity_conflict",
                        resource,
                        target_locator=target.logical_locator,
                    )
                ],
            )
        if not entry_exists:
            return UserCopyAction.MERGE, None, None, []
        if entry_digest == incoming_digest:
            return UserCopyAction.UNCHANGED, entry_digest, None, []
        assert entry_digest is not None
        return (
            UserCopyAction.OVERWRITE,
            entry_digest,
            _conflict_for_resource(
                resource,
                target,
                baseline_revision=entry_digest,
                incoming_digest=incoming_digest,
            ),
            [],
        )

    @staticmethod
    def _content_state(
        resource: CoreProfileResource,
        target: ResolvedUserCopyTarget,
        *,
        incoming_digest: str,
        baseline_revision: str,
    ) -> tuple[
        UserCopyAction,
        str,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        if baseline_revision == incoming_digest:
            return UserCopyAction.UNCHANGED, baseline_revision, None, []
        return (
            UserCopyAction.OVERWRITE,
            baseline_revision,
            _conflict_for_resource(
                resource,
                target,
                baseline_revision=baseline_revision,
                incoming_digest=incoming_digest,
            ),
            [],
        )

    @staticmethod
    def _unsafe_target(
        resource: CoreProfileResource,
        target: ResolvedUserCopyTarget,
    ) -> tuple[
        UserCopyAction,
        None,
        None,
        list[UserCopyBlockingIssue],
    ]:
        return (
            _initial_action(target.target_kind),
            None,
            None,
            [
                _blocking_for_resource(
                    "marketplace.user_copy.target_unsafe",
                    resource,
                    target_locator=target.logical_locator,
                )
            ],
        )

    def _validate_runtime_target(self, target: Path) -> str | None:
        user_home = self._paths.user_home.absolute()
        absolute_target = target.absolute()
        try:
            relative = absolute_target.relative_to(user_home)
        except ValueError:
            return "marketplace.user_copy.target_not_writable"

        current = user_home
        if current.is_symlink():
            return "marketplace.user_copy.target_unsafe"
        for part in relative.parts:
            if current.exists() and current.is_dir():
                for child in current.iterdir():
                    if child.name.casefold() == part.casefold() and child.name != part:
                        return "marketplace.user_copy.duplicate_target"
            current = current / part
            if current.is_symlink():
                return "marketplace.user_copy.target_unsafe"

        writable_parent = absolute_target.parent
        while (
            not writable_parent.exists() and writable_parent != writable_parent.parent
        ):
            writable_parent = writable_parent.parent
        if not writable_parent.is_dir() or not os.access(
            writable_parent, os.W_OK | os.X_OK
        ):
            return "marketplace.user_copy.target_not_writable"
        return None

    @staticmethod
    def _effective_identity_issues(
        target_client: str,
        resource: CoreProfileResource,
        *,
        inventory: UserCopyInventory,
        target_locator: str,
    ) -> list[UserCopyBlockingIssue]:
        expected = (
            f"{target_client}:{resource.resource_type}:{resource.resource_id}"
        ).casefold()
        return [
            _blocking_for_resource(
                "marketplace.user_copy.effective_identity_conflict",
                resource,
                target_locator=target_locator,
            )
            for identity in inventory.effective_identities
            if identity.normalized_identity == expected
        ]

    @staticmethod
    def _detect_duplicate_targets(
        resources: Iterable[PlannedUserCopyResource],
        blocking: list[UserCopyBlockingIssue],
    ) -> None:
        identities: dict[str, PlannedUserCopyResource] = {}
        for resource in resources:
            folded = resource.target_identity.casefold()
            previous = identities.get(folded)
            if previous is not None:
                blocking.append(
                    UserCopyBlockingIssue(
                        code="marketplace.user_copy.duplicate_target",
                        resource_type=resource.resource_type,
                        resource_id=resource.resource_id,
                        source_locator=resource.source_locator,
                        target_locator=resource.target_locator,
                    )
                )
            else:
                identities[folded] = resource



def _directory_source_digest(root: Path) -> str:
    digest = sha256()
    for path in sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_symlink():
            raise UserCopyAdapterError(
                "source-reference-invalid",
                relative.decode("utf-8", errors="replace"),
            )
        if path.is_dir():
            entry_type, mode, content = b"directory", 0o700, b""
        elif path.is_file():
            entry_type = b"file"
            mode = 0o700 if stat.S_IMODE(path.stat().st_mode) & 0o111 else 0o600
            content = path.read_bytes()
        else:
            raise UserCopyAdapterError(
                "source-reference-invalid",
                relative.decode("utf-8", errors="replace"),
            )
        for field in (entry_type, f"{mode:o}".encode("ascii"), relative, content):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def _dependency_file_digest(path: Path) -> str:
    normalized_mode = (
        0o700 if stat.S_IMODE(path.stat().st_mode) & 0o111 else 0o600
    )
    digest = sha256()
    for component in (
        b"file",
        f"{normalized_mode:o}".encode("ascii"),
        path.read_bytes(),
    ):
        digest.update(len(component).to_bytes(8, "big"))
        digest.update(component)
    return digest.hexdigest()


def _validate_payload_source(
    source_path: Path,
    *,
    target_kind: UserCopyTargetKind,
    expected_digest: str,
) -> None:
    if source_path.is_symlink():
        raise UserCopyAdapterError(
            "source-reference-invalid",
            source_path.name,
        )
    try:
        if target_kind is UserCopyTargetKind.FILE:
            if not source_path.is_file():
                raise UserCopyAdapterError(
                    "source-not-allowed",
                    source_path.name,
                )
            actual_digest = _dependency_file_digest(source_path)
        elif target_kind is UserCopyTargetKind.DIRECTORY:
            if not source_path.is_dir():
                raise UserCopyAdapterError(
                    "source-not-allowed",
                    source_path.name,
                )
            actual_digest = _directory_source_digest(source_path)
        else:
            raise UserCopyAdapterError(
                "source-not-allowed",
                source_path.name,
            )
    except OSError as exc:
        raise UserCopyAdapterError(
            "source-reference-invalid",
            source_path.name,
        ) from exc
    if actual_digest != expected_digest:
        raise UserCopyAdapterError(
            "source-reference-invalid",
            source_path.name,
        )



def _safe_blocking_locator(value: Any) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_USER_COPY_FIELD_LENGTH
    ):
        return None
    try:
        normalized = normalize_package_locator(value).as_posix()
    except UserCopyAdapterError:
        return None
    return value if normalized == value else None



def _read_target_document(
    target: ResolvedUserCopyTarget,
) -> tuple[dict[str, Any], str | None]:
    if target.runtime_path.is_symlink() or (
        target.runtime_path.exists() and not target.runtime_path.is_file()
    ):
        return {}, "marketplace.user_copy.target_unsafe"
    try:
        if target.structured_document is StructuredDocumentKind.JSON:
            return (
                JsonDocumentCodec(invalid_as_empty=False).read(target.runtime_path),
                None,
            )
        if target.structured_document is StructuredDocumentKind.TOML:
            return (
                TomlDocumentCodec(invalid_as_empty=False).read(target.runtime_path),
                None,
            )
    except Exception:
        return {}, "marketplace.user_copy.target_document_invalid"
    return {}, "marketplace.user_copy.profile_invalid"


def _structured_entry_state(
    document: dict[str, Any],
    target: ResolvedUserCopyTarget,
) -> tuple[bool, str | None, bool]:
    current: Any = document
    for part in target.structured_parent:
        if not isinstance(current, dict):
            return False, None, False
        if part not in current:
            return False, None, True
        current = current[part]

    if target.structured_entry_mode is StructuredEntryMode.MAPPING_ENTRY:
        if not isinstance(current, dict):
            return False, None, False
        entry_id = target.structured_entry_id or ""
        if entry_id not in current:
            return False, None, True
        return True, canonical_value_digest(current[entry_id]), True

    if target.structured_entry_mode is StructuredEntryMode.LIST_ENTRY:
        if not isinstance(current, list):
            return False, None, False
        expected_digest = target.structured_entry_id
        matches = [
            item for item in current if canonical_value_digest(item) == expected_digest
        ]
        if not matches:
            return False, None, True
        return True, expected_digest, len(matches) == 1
    return False, None, False


def _conflict_for_resource(
    resource: CoreProfileResource,
    target: ResolvedUserCopyTarget,
    *,
    baseline_revision: str,
    incoming_digest: str,
) -> UserCopyPlanConflict:
    return UserCopyPlanConflict(
        code="marketplace.user_copy.target_conflict",
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        source_locator=resource.source_locator,
        target_locator=target.logical_locator,
        target_identity=target.normalized_identity,
        baseline_revision=baseline_revision,
        incoming_digest=incoming_digest,
    )


def _blocking_for_resource(
    code: str,
    resource: CoreProfileResource,
    *,
    target_locator: str | None = None,
) -> UserCopyBlockingIssue:
    return UserCopyBlockingIssue(
        code=code,
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        source_locator=resource.source_locator,
        target_locator=target_locator,
    )


def _initial_action(target_kind: UserCopyTargetKind) -> UserCopyAction:
    return (
        UserCopyAction.MERGE
        if target_kind is UserCopyTargetKind.CONFIG_ENTRY
        else UserCopyAction.CREATE
    )



def _planned_resource_sort_key(
    resource: PlannedUserCopyResource,
) -> tuple[str, str, str, str]:
    return (
        resource.target_locator,
        resource.resource_type,
        resource.resource_id,
        resource.source_locator,
    )


def _adapter_error_code(code: str) -> str:
    return {
        "source-reference-invalid": "marketplace.user_copy.source_reference_invalid",
        "source-not-allowed": "marketplace.user_copy.source_not_allowed",
        "source-document-invalid": "marketplace.user_copy.source_reference_invalid",
        "placeholder-reference-invalid": (
            "marketplace.user_copy.source_reference_invalid"
        ),
        "dependency-payload-required": (
            "marketplace.user_copy.dependency_payload_unprojectable"
        ),
        "dependency-payload-reference-invalid": (
            "marketplace.user_copy.source_reference_invalid"
        ),
        "target-root-escape": "marketplace.user_copy.target_not_writable",
        "unsupported-resource": "marketplace.user_copy.unsupported_resource",
        "overwrite-approval-invalid": (
            "marketplace.user_copy.overwrite_approval_invalid"
        ),
    }.get(code, "marketplace.user_copy.profile_invalid")
