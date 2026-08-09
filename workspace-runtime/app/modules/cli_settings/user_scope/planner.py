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
from typing import Any, Iterable, Mapping

from aileron_marketplace_core import (
    USER_COPY_PAYLOAD_ROOT_SENTINEL,
    build_user_copy_profile_preview,
)

from .adapter import (
    CoreProfileResource,
    ProviderUserCopyAdapter,
    ResolvedUserCopyTarget,
    StructuredDocumentKind,
    StructuredEntryMode,
    UserCopyAdapterError,
    UserCopyOperation,
    UserCopyTargetKind,
    canonical_value_digest,
    enum_value,
    extract_json_pointer,
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

    provider: str
    resource_type: str
    resource_id: str
    scope: str

    @property
    def normalized_identity(self) -> str:
        return f"{self.provider}:{self.resource_type}:{self.resource_id}".casefold()


@dataclass(frozen=True)
class UserCopyInventory:
    """Provider-wide semantic identities used by preflight."""

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

    provider: str
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
            "provider": self.provider,
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

    provider: str
    profile_version: int
    profile_digest: str
    status: UserCopyPlanStatus
    resources: tuple[PlannedUserCopyResource, ...]
    conflicts: tuple[UserCopyPlanConflict, ...]
    blocking_issues: tuple[UserCopyBlockingIssue, ...]
    materialization_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status.value,
            "provider": self.provider,
            "profileVersion": self.profile_version,
            "profileDigest": self.profile_digest,
            "resources": [resource.canonical_dict() for resource in self.resources],
            "conflicts": [conflict.canonical_dict() for conflict in self.conflicts],
            "blockingIssues": [
                issue.canonical_dict() for issue in self.blocking_issues
            ],
        }
        if include_digest:
            result["materializationDigest"] = self.materialization_digest
        return result


def compute_materialization_digest(plan: UserCopyMaterializationPlan) -> str:
    """Recompute a plan proof without trusting its supplied digest."""

    encoded = json.dumps(
        plan.canonical_dict(include_digest=False),
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
    provider: str
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
        paths: UserScopePathResolver | None = None,
    ) -> None:
        if not isinstance(package_id, str) or _PACKAGE_ID.fullmatch(package_id) is None:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "package-id-invalid",
            )
        self._package_id = package_id
        self._paths = paths or get_user_scope_path_resolver()

    def plan(
        self,
        profile: object,
        package_root: Path,
        *,
        inventory: UserCopyInventory,
    ) -> UserCopyMaterializationPlan:
        preview = build_user_copy_profile_preview(package_root, profile)  # type: ignore[arg-type]
        dependency_required = {
            f"{item['resourceType']}:{item['resourceId']}": bool(
                item["dependencyPayloadRequired"]
            )
            for item in preview["resources"]
        }
        dependency_projectable = {
            f"{item['resourceType']}:{item['resourceId']}": bool(
                item["dependencyPayloadProjectable"]
            )
            for item in preview["resources"]
        }
        return self._build_plan(
            _adapt_core_profile(profile),
            inventory=inventory,
            package_root=package_root,
            dependency_payloads=_adapt_dependency_payloads(
                preview["dependencyPayloads"]
            ),
            dependency_payload_required=dependency_required,
            dependency_payload_projectable=dependency_projectable,
            structured_value_templates={
                f"{item['resourceType']}:{item['resourceId']}": item[
                    "structuredValueTemplate"
                ]
                for item in preview["resources"]
                if "structuredValueTemplate" in item
            },
        )

    def plan_preview(
        self,
        profile: object,
        *,
        source_digests: Mapping[str, str],
        dependency_payload_required: Mapping[str, bool],
        dependency_payload_projectable: Mapping[str, bool],
        dependency_payloads: Iterable[Mapping[str, Any]],
        structured_value_types: Mapping[str, str],
        structured_value_templates: Mapping[str, Any],
        inventory: UserCopyInventory,
    ) -> UserCopyMaterializationPlan:
        """Plan from Manager source proofs without reading a snapshot."""

        adapted = _adapt_core_profile(profile)
        expected_ids = {
            f"{resource.resource_type}:{resource.resource_id}"
            for resource in adapted.resources
        }
        expected_structured_ids = {
            f"{resource.resource_type}:{resource.resource_id}"
            for resource in adapted.resources
            if resource.copy_semantics == "merge-config-entry"
        }
        if (
            set(source_digests) != expected_ids
            or set(dependency_payload_required) != expected_ids
            or set(dependency_payload_projectable) != expected_ids
            or set(structured_value_types) != expected_structured_ids
            or set(structured_value_templates)
            != {
                stable_id
                for stable_id in expected_structured_ids
                if dependency_payload_required.get(stable_id) is True
                and dependency_payload_projectable.get(stable_id) is True
            }
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "preview-resource-proof-mismatch",
            )
        validated_digests = {
            stable_id: validate_sha256_digest(digest)
            for stable_id, digest in source_digests.items()
        }
        if any(
            type(required) is not bool
            for required in dependency_payload_required.values()
        ) or any(
            type(projectable) is not bool
            for projectable in dependency_payload_projectable.values()
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "preview-dependency-proof-invalid",
            )
        adapted_payloads = _adapt_dependency_payloads(dependency_payloads)
        template_payload_locators: set[str] = set()
        for template in structured_value_templates.values():
            template_payload_locators.update(
                _structured_template_payload_locators(template)
            )
        if not _dependency_payload_coverage_valid(
            template_payload_locators,
            adapted_payloads,
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "preview-dependency-proof-mismatch",
            )
        return self._build_plan(
            adapted,
            inventory=inventory,
            source_digests=validated_digests,
            dependency_payload_required=dependency_payload_required,
            dependency_payload_projectable=dependency_payload_projectable,
            dependency_payloads=adapted_payloads,
            structured_value_types=structured_value_types,
            structured_value_templates=structured_value_templates,
        )

    def _build_plan(
        self,
        adapted: _AdaptedProfile,
        *,
        inventory: UserCopyInventory,
        package_root: Path | None = None,
        source_digests: Mapping[str, str] | None = None,
        dependency_payload_required: Mapping[str, bool] | None = None,
        dependency_payload_projectable: Mapping[str, bool] | None = None,
        dependency_payloads: tuple[_DependencyPayload, ...] = (),
        structured_value_types: Mapping[str, str] | None = None,
        structured_value_templates: Mapping[str, Any] | None = None,
    ) -> UserCopyMaterializationPlan:
        adapter = self._adapter(adapted.provider)
        conflicts: list[UserCopyPlanConflict] = []
        blocking = list(adapted.blocked_resources)
        resources: list[PlannedUserCopyResource] = []

        if not inventory.complete:
            blocking.append(
                UserCopyBlockingIssue(
                    code="marketplace.user_copy.inventory_unavailable"
                )
            )

        seen_resource_ids: set[str] = set()
        for resource in adapted.resources:
            stable_identity = (
                f"{adapted.provider}:{resource.resource_type}:{resource.resource_id}"
            ).casefold()
            if stable_identity in seen_resource_ids:
                blocking.append(
                    _blocking_for_resource(
                        "marketplace.user_copy.duplicate_target",
                        resource,
                    )
                )
                continue
            seen_resource_ids.add(stable_identity)
            try:
                if package_root is not None:
                    if (
                        dependency_payload_required is None
                        or dependency_payload_projectable is None
                    ):
                        raise UserCopyAdapterError(
                            "profile-contract-invalid",
                            "dependency-proof-missing",
                        )
                    resource_stable_id = (
                        f"{resource.resource_type}:{resource.resource_id}"
                    )
                    planned, resource_conflict, resource_issues = self._plan_resource(
                        adapted.provider,
                        adapter,
                        resource,
                        package_root,
                        dependency_payload_required=(
                            dependency_payload_required[resource_stable_id]
                        ),
                        dependency_payload_projectable=(
                            dependency_payload_projectable[resource_stable_id]
                        ),
                    )
                else:
                    if (
                        source_digests is None
                        or dependency_payload_required is None
                        or dependency_payload_projectable is None
                        or structured_value_types is None
                        or structured_value_templates is None
                    ):
                        raise UserCopyAdapterError(
                            "profile-contract-invalid",
                            "preview-resource-proof-missing",
                        )
                    resource_stable_id = (
                        f"{resource.resource_type}:{resource.resource_id}"
                    )
                    planned, resource_conflict, resource_issues = (
                        self._plan_preview_resource(
                            adapted.provider,
                            adapter,
                            resource,
                            source_digest=source_digests[resource_stable_id],
                            dependency_payload_required=(
                                dependency_payload_required[resource_stable_id]
                            ),
                            dependency_payload_projectable=(
                                dependency_payload_projectable[resource_stable_id]
                            ),
                            structured_value_type=structured_value_types.get(
                                resource_stable_id
                            ),
                            structured_value_template=(
                                structured_value_templates.get(resource_stable_id)
                            ),
                        )
                    )
            except UserCopyAdapterError as exc:
                blocking.append(
                    _blocking_for_resource(
                        _adapter_error_code(exc.code),
                        resource,
                    )
                )
                continue
            resources.append(planned)
            if resource_conflict is not None:
                conflicts.append(resource_conflict)
            blocking.extend(resource_issues)
            blocking.extend(
                self._effective_identity_issues(
                    adapted.provider,
                    resource,
                    inventory=inventory,
                    target_locator=planned.target_locator,
                )
            )

        for payload in dependency_payloads:
            try:
                planned, payload_conflict, payload_issues = self._plan_payload(
                    adapted.provider,
                    payload,
                    package_root=package_root,
                )
            except UserCopyAdapterError as exc:
                blocking.append(
                    UserCopyBlockingIssue(
                        code=_adapter_error_code(exc.code),
                        resource_type="dependency-payload",
                        resource_id=payload.source_locator,
                        source_locator=payload.source_locator,
                    )
                )
                continue
            resources.append(planned)
            if payload_conflict is not None:
                conflicts.append(payload_conflict)
            blocking.extend(payload_issues)

        self._detect_duplicate_targets(resources, blocking)
        if not resources:
            blocking.append(
                UserCopyBlockingIssue(code="marketplace.user_copy.profile_empty")
            )

        resources_tuple = tuple(sorted(resources, key=_planned_resource_sort_key))
        conflicts_tuple = tuple(
            sorted(
                set(conflicts),
                key=lambda item: (
                    item.target_identity,
                    item.resource_type,
                    item.resource_id,
                ),
            )
        )
        blocking_tuple = tuple(
            sorted(
                set(blocking),
                key=lambda item: (
                    item.code,
                    item.resource_type or "",
                    item.resource_id or "",
                    item.target_locator or "",
                ),
            )
        )
        status = (
            UserCopyPlanStatus.BLOCKED
            if blocking_tuple
            else (
                UserCopyPlanStatus.CONFIRMATION_REQUIRED
                if conflicts_tuple
                else UserCopyPlanStatus.READY
            )
        )
        plan = UserCopyMaterializationPlan(
            provider=adapted.provider,
            profile_version=adapted.profile_version,
            profile_digest=adapted.profile_digest,
            status=status,
            resources=resources_tuple,
            conflicts=conflicts_tuple,
            blocking_issues=blocking_tuple,
            materialization_digest="",
        )
        return UserCopyMaterializationPlan(
            provider=plan.provider,
            profile_version=plan.profile_version,
            profile_digest=plan.profile_digest,
            status=plan.status,
            resources=plan.resources,
            conflicts=plan.conflicts,
            blocking_issues=plan.blocking_issues,
            materialization_digest=compute_materialization_digest(plan),
        )

    def _adapter(self, provider: str) -> ProviderUserCopyAdapter:
        if provider == "codex":
            from .codex import get_codex_user_copy_adapter

            return get_codex_user_copy_adapter(self._paths)
        if provider == "claude-code":
            from .claude import get_claude_user_copy_adapter

            return get_claude_user_copy_adapter(self._paths)
        raise UserCopyAdapterError("provider-not-supported", provider)

    def _dependency_payload_root(self, provider: str) -> Path:
        return (
            self._paths.user_home
            / ".aileron"
            / "user-copy"
            / provider
            / self._package_id
        )

    def _plan_payload(
        self,
        provider: str,
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
            f"~/.aileron/user-copy/{provider}/{self._package_id}/"
            f"{relative.as_posix()}"
        )
        target = ResolvedUserCopyTarget(
            agent=self._adapter(provider).agent,
            target_kind=target_kind,
            operation=UserCopyOperation.CREATE,
            runtime_path=self._dependency_payload_root(provider).joinpath(
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
            provider,
            resource,
            target,
            source_digest=payload.content_digest,
            content_digest=payload.content_digest,
            source_path=source_path,
        )

    def _plan_resource(
        self,
        provider: str,
        adapter: ProviderUserCopyAdapter,
        resource: CoreProfileResource,
        package_root: Path,
        *,
        dependency_payload_required: bool,
        dependency_payload_projectable: bool,
    ) -> tuple[
        PlannedUserCopyResource,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        source_path = _resolve_source_path(package_root, resource.source_locator)
        source_value = (
            _structured_source_value(source_path, resource.json_pointer)
            if resource.copy_semantics == "merge-config-entry"
            else None
        )
        target_source_value = source_value
        structured_content_digest: str | None = None
        if resource.copy_semantics == "merge-config-entry":
            structured_content_digest = canonical_value_digest(source_value)
            if dependency_payload_required and dependency_payload_projectable:
                target_source_value, used_payload = rewrite_known_placeholders(
                    source_value,
                    tokens=adapter.placeholder_tokens,
                    payload_root=self._dependency_payload_root(provider),
                    validate_payload_reference=False,
                )
                if not used_payload:
                    raise UserCopyAdapterError(
                        "profile-contract-invalid",
                        "dependency-template-mismatch",
                    )
                structured_content_digest = canonical_value_digest(target_source_value)
        target = adapter.resolve_target(
            resource,
            source_value=target_source_value,
            source_digest=(
                structured_content_digest if resource.resource_type == "hook" else None
            ),
        )
        _validate_source_shape(resource, source_path, target.target_kind)
        source_digest = _source_digest(
            source_path,
            target.target_kind,
            source_value,
        )
        content_digest = source_digest
        if target.target_kind is UserCopyTargetKind.CONFIG_ENTRY:
            content_digest = structured_content_digest or source_digest
        planned, conflict, issues = self._planned_target(
            provider,
            resource,
            target,
            source_digest=source_digest,
            content_digest=content_digest,
            source_path=source_path,
        )
        if dependency_payload_required and not dependency_payload_projectable:
            issues.append(
                _blocking_for_resource(
                    "marketplace.user_copy.dependency_payload_unprojectable",
                    resource,
                    target_locator=target.logical_locator,
                )
            )
        return planned, conflict, issues

    def _plan_preview_resource(
        self,
        provider: str,
        adapter: ProviderUserCopyAdapter,
        resource: CoreProfileResource,
        *,
        source_digest: str,
        dependency_payload_required: bool,
        dependency_payload_projectable: bool,
        structured_value_type: str | None,
        structured_value_template: Any | None,
    ) -> tuple[
        PlannedUserCopyResource,
        UserCopyPlanConflict | None,
        list[UserCopyBlockingIssue],
    ]:
        source_locator = normalize_package_locator(resource.source_locator)
        source_value = (
            (
                _materialize_structured_template(
                    structured_value_template,
                    payload_root=self._dependency_payload_root(provider),
                )
                if dependency_payload_required and dependency_payload_projectable
                else _structured_value_placeholder(structured_value_type)
            )
            if resource.copy_semantics == "merge-config-entry"
            else None
        )
        target = adapter.resolve_target(
            resource,
            source_value=source_value,
            source_digest=(
                (
                    canonical_value_digest(source_value)
                    if dependency_payload_required and dependency_payload_projectable
                    else source_digest
                )
                if resource.resource_type == "hook"
                else None
            ),
        )
        planned, conflict, issues = self._planned_target(
            provider,
            resource,
            target,
            source_digest=source_digest,
            content_digest=(
                canonical_value_digest(source_value)
                if resource.copy_semantics == "merge-config-entry"
                and dependency_payload_required
                and dependency_payload_projectable
                else source_digest
            ),
            source_path=Path(*source_locator.parts),
        )
        if dependency_payload_required and not dependency_payload_projectable:
            issues.append(
                _blocking_for_resource(
                    "marketplace.user_copy.dependency_payload_unprojectable",
                    resource,
                    target_locator=target.logical_locator,
                )
            )
        return planned, conflict, issues

    def _planned_target(
        self,
        provider: str,
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
                provider=provider,
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
        provider: str,
        resource: CoreProfileResource,
        *,
        inventory: UserCopyInventory,
        target_locator: str,
    ) -> list[UserCopyBlockingIssue]:
        expected = (
            f"{provider}:{resource.resource_type}:{resource.resource_id}"
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


def _adapt_core_profile(profile: object) -> _AdaptedProfile:
    try:
        provider = enum_value(getattr(profile, "provider"))
        profile_version = getattr(profile, "profile_version")
        profile_digest = getattr(profile, "profile_digest")
        raw_resources = tuple(getattr(profile, "resources"))
        raw_blocked = tuple(getattr(profile, "blocked_resources", ()))
    except (AttributeError, TypeError, ValueError) as exc:
        raise UserCopyAdapterError(
            "profile-contract-invalid",
            type(profile).__name__,
        ) from exc
    if provider not in {"claude-code", "codex"}:
        raise UserCopyAdapterError("provider-not-supported", provider)
    if (
        type(profile_version) is not int
        or profile_version != 1
        or not isinstance(profile_digest, str)
        or len(profile_digest) != 64
        or any(character not in "0123456789abcdef" for character in profile_digest)
    ):
        raise UserCopyAdapterError("profile-contract-invalid", profile_digest)

    resources: list[CoreProfileResource] = []
    for raw in raw_resources:
        try:
            resource_id = getattr(raw, "resource_id")
            source_locator = getattr(raw, "source_locator")
            relative_target = getattr(raw, "relative_target", None)
            json_pointer = getattr(raw, "json_pointer", None)
            if (
                not isinstance(resource_id, str)
                or not resource_id
                or len(resource_id) > _MAX_USER_COPY_FIELD_LENGTH
                or not isinstance(source_locator, str)
                or not source_locator
                or len(source_locator) > _MAX_USER_COPY_FIELD_LENGTH
                or (
                    relative_target is not None
                    and (
                        not isinstance(relative_target, str)
                        or len(relative_target) > _MAX_USER_COPY_FIELD_LENGTH
                    )
                )
                or (
                    json_pointer is not None
                    and (
                        not isinstance(json_pointer, str)
                        or len(json_pointer) > _MAX_USER_COPY_FIELD_LENGTH
                    )
                )
            ):
                raise TypeError("invalid user-copy profile resource")
            resources.append(
                CoreProfileResource(
                    resource_type=enum_value(getattr(raw, "resource_type")),
                    resource_id=resource_id,
                    source_kind=enum_value(getattr(raw, "source_kind")),
                    source_locator=source_locator,
                    target_resource=enum_value(getattr(raw, "target_resource")),
                    copy_semantics=enum_value(getattr(raw, "copy_semantics")),
                    relative_target=relative_target,
                    json_pointer=json_pointer,
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                type(raw).__name__,
            ) from exc

    blocked_items: list[UserCopyBlockingIssue] = []
    for raw in raw_blocked:
        raw_resource_type = getattr(raw, "resource_type", None)
        resource_type = (
            raw_resource_type
            if isinstance(raw_resource_type, str)
            and raw_resource_type in _PUBLIC_USER_COPY_RESOURCE_TYPES
            else None
        )
        raw_locator = getattr(raw, "source_locator", None)
        source_locator = _safe_blocking_locator(raw_locator)
        blocked_items.append(
            UserCopyBlockingIssue(
                code="marketplace.user_copy.unsupported_resource",
                resource_type=resource_type,
                source_locator=source_locator,
            )
        )
    blocked = tuple(blocked_items)
    return _AdaptedProfile(
        provider=provider,
        profile_version=profile_version,
        profile_digest=profile_digest,
        resources=tuple(resources),
        blocked_resources=blocked,
    )


def _adapt_dependency_payloads(
    raw_payloads: Iterable[Mapping[str, Any]],
) -> tuple[_DependencyPayload, ...]:
    payloads: list[_DependencyPayload] = []
    seen: set[str] = set()
    previous_sort_key: tuple[str, str] | None = None
    for raw in raw_payloads:
        if not isinstance(raw, Mapping) or set(raw) != {
            "sourceLocator",
            "sourceKind",
            "contentDigest",
        }:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-invalid",
            )
        locator = raw.get("sourceLocator")
        source_kind = raw.get("sourceKind")
        digest = raw.get("contentDigest")
        if (
            not isinstance(locator, str)
            or len(locator) > _MAX_USER_COPY_FIELD_LENGTH
            or not isinstance(source_kind, str)
            or source_kind not in {"file", "directory"}
            or not isinstance(digest, str)
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-invalid",
            )
        try:
            normalized = normalize_package_locator(locator).as_posix()
            validated_digest = validate_sha256_digest(digest)
        except UserCopyAdapterError as exc:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-invalid",
            ) from exc
        if normalized != locator:
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-invalid",
            )
        folded = locator.casefold()
        sort_key = (locator, source_kind)
        if folded in seen or (
            previous_sort_key is not None and sort_key <= previous_sort_key
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-order-invalid",
            )
        seen.add(folded)
        previous_sort_key = sort_key
        payloads.append(
            _DependencyPayload(
                source_locator=locator,
                source_kind=source_kind,
                content_digest=validated_digest,
            )
        )

    for index, payload in enumerate(payloads):
        prefix = f"{payload.source_locator}/".casefold()
        if any(
            other.source_locator.casefold().startswith(prefix)
            for other in payloads[index + 1 :]
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-payload-overlap-invalid",
            )
    return tuple(payloads)


def _materialize_structured_template(
    template: Any,
    *,
    payload_root: Path,
) -> Any:
    found_sentinel = False

    def visit(value: Any) -> Any:
        nonlocal found_sentinel
        if isinstance(value, dict):
            return {str(key): visit(child) for key, child in value.items()}
        if isinstance(value, list):
            return [visit(child) for child in value]
        if isinstance(value, str):
            prefix = f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/"
            if value.startswith(prefix):
                found_sentinel = True
                suffix = value.removeprefix(prefix)
                relative = normalize_package_locator(suffix)
                if relative.as_posix() != suffix:
                    raise UserCopyAdapterError(
                        "profile-contract-invalid",
                        "dependency-template-invalid",
                    )
                return payload_root.joinpath(*relative.parts).as_posix()
            if USER_COPY_PAYLOAD_ROOT_SENTINEL in value:
                raise UserCopyAdapterError(
                    "profile-contract-invalid",
                    "dependency-template-invalid",
                )
        return value

    materialized = visit(template)
    if not found_sentinel:
        raise UserCopyAdapterError(
            "profile-contract-invalid",
            "dependency-template-invalid",
        )
    return materialized


def _structured_template_payload_locators(template: Any) -> set[str]:
    locators: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if any(USER_COPY_PAYLOAD_ROOT_SENTINEL in str(key) for key in value):
                raise UserCopyAdapterError(
                    "profile-contract-invalid",
                    "dependency-template-invalid",
                )
            for child in value.values():
                visit(child)
            return
        if isinstance(value, list):
            for child in value:
                visit(child)
            return
        if not isinstance(value, str) or USER_COPY_PAYLOAD_ROOT_SENTINEL not in value:
            return
        prefix = f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/"
        if not value.startswith(prefix):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-template-invalid",
            )
        suffix = value.removeprefix(prefix)
        relative = normalize_package_locator(suffix)
        locator = relative.as_posix()
        if (
            locator != suffix
            or len(locator) > _MAX_USER_COPY_FIELD_LENGTH
            or USER_COPY_PAYLOAD_ROOT_SENTINEL in suffix
        ):
            raise UserCopyAdapterError(
                "profile-contract-invalid",
                "dependency-template-invalid",
            )
        locators.add(locator)

    visit(template)
    return locators


def _dependency_payload_coverage_valid(
    referenced_locators: set[str],
    dependency_payloads: tuple[_DependencyPayload, ...],
) -> bool:
    if bool(referenced_locators) != bool(dependency_payloads):
        return False

    def payload_covers(
        payload: _DependencyPayload,
        referenced: str,
    ) -> bool:
        return referenced == payload.source_locator or (
            payload.source_kind == "directory"
            and referenced.startswith(f"{payload.source_locator}/")
        )

    return all(
        any(payload_covers(payload, referenced) for payload in dependency_payloads)
        for referenced in referenced_locators
    ) and all(
        any(payload_covers(payload, referenced) for referenced in referenced_locators)
        for payload in dependency_payloads
    )


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


def _resolve_source_path(package_root: Path, locator: str) -> Path:
    relative = normalize_package_locator(locator)
    try:
        root = package_root.resolve(strict=True)
        candidate = package_root.joinpath(*relative.parts)
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise UserCopyAdapterError("source-reference-invalid", locator) from exc
    return candidate


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


def _structured_source_value(source_path: Path, pointer: str | None) -> Any:
    if not source_path.is_file():
        raise UserCopyAdapterError("source-not-allowed", source_path.name)
    try:
        document = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserCopyAdapterError(
            "source-document-invalid",
            source_path.name,
        ) from exc
    return extract_json_pointer(document, pointer)


def _validate_source_shape(
    resource: CoreProfileResource,
    source_path: Path,
    target_kind: UserCopyTargetKind,
) -> None:
    if target_kind is UserCopyTargetKind.DIRECTORY:
        if not source_path.is_dir() or source_path.is_symlink():
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        return
    if not source_path.is_file() or source_path.is_symlink():
        raise UserCopyAdapterError(
            "source-not-allowed",
            resource.source_locator,
        )


def _source_digest(
    source_path: Path,
    target_kind: UserCopyTargetKind,
    source_value: Any | None,
) -> str:
    if target_kind is UserCopyTargetKind.DIRECTORY:
        return _directory_source_digest(source_path)
    if target_kind is UserCopyTargetKind.CONFIG_ENTRY:
        return canonical_value_digest(source_value)
    return file_bytes_revision(source_path)


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
            entry_type = b"directory"
            mode = 0o700
            content = b""
        elif path.is_file():
            entry_type = b"file"
            source_mode = stat.S_IMODE(path.stat().st_mode)
            mode = 0o700 if source_mode & 0o111 else 0o600
            content = path.read_bytes()
        else:
            raise UserCopyAdapterError(
                "source-reference-invalid",
                relative.decode("utf-8", errors="replace"),
            )
        for field in (
            entry_type,
            f"{mode:o}".encode("ascii"),
            relative,
            content,
        ):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
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


def _structured_value_placeholder(value_type: str | None) -> Any:
    placeholders: dict[str, Any] = {
        "object": {},
        "array": [],
        "string": "",
        "number": 0,
        "boolean": False,
        "null": None,
    }
    if value_type not in placeholders:
        raise UserCopyAdapterError(
            "profile-contract-invalid",
            str(value_type),
        )
    return placeholders[value_type]


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
