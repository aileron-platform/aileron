"""Persistent audit event service."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db import models as db_models

AUDIT_METADATA_KEYS = frozenset(
    {
        "changed_fields",
        "before",
        "after",
        "group_id",
        "kb_id",
        "workspace_id",
        "job_id",
        "runtime_instance_id",
        "previous_runtime_instance_id",
        "new_runtime_instance_id",
        "previous_owner_id",
        "new_owner_id",
        "owner_reassignment_reason",
        "target_revision",
        "desired_mount_revision",
        "observed_mount_revision",
        "runtime_access_revision",
        "browser_credential_revision",
        "retry_attempt",
        "attempt",
        "reason",
        "intent",
        "phase",
    }
)

_IDENTIFIER_METADATA_KEYS = frozenset(
    {
        "group_id",
        "kb_id",
        "workspace_id",
        "job_id",
        "runtime_instance_id",
        "previous_runtime_instance_id",
        "new_runtime_instance_id",
        "previous_owner_id",
        "new_owner_id",
    }
)
_REVISION_METADATA_KEYS = frozenset(
    {
        "target_revision",
        "desired_mount_revision",
        "observed_mount_revision",
        "runtime_access_revision",
        "browser_credential_revision",
        "retry_attempt",
        "attempt",
    }
)
_ENUM_VALUE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class AuditEventService:
    """Add and query structured audit events within caller-owned transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str,
        actor_user_id: str | None,
        target_type: str,
        target_id: str,
        action: str,
        result: str,
        error_code: str | None,
        correlation_id: str,
        root_correlation_id: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> db_models.AuditEvent:
        """Add an audit event and flush it without owning the transaction."""

        self._validate_actor(
            actor_type=actor_type,
            actor_id=actor_id,
            actor_user_id=actor_user_id,
        )
        self._validate_result(result=result, error_code=error_code)
        event_metadata = self._validate_metadata(metadata)

        event = db_models.AuditEvent(
            id=str(uuid4()),
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            error_code=error_code,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            event_metadata=event_metadata,
        )
        self.db.add(event)
        self.db.flush()
        return event

    @staticmethod
    def _validate_actor(
        *, actor_type: str, actor_id: str, actor_user_id: str | None
    ) -> None:
        if actor_type not in {"user", "service"}:
            raise ValueError("actor_type must be user or service")
        if not actor_id:
            raise ValueError("actor_id must not be empty")
        if actor_type == "user" and not actor_user_id:
            raise ValueError("user audit actors require actor_user_id")
        if actor_type == "service" and actor_user_id is not None:
            raise ValueError("service audit actors cannot have actor_user_id")

    @staticmethod
    def _validate_result(*, result: str, error_code: str | None) -> None:
        if result not in {"success", "failure", "compensation_required"}:
            raise ValueError("invalid audit result")
        if result == "success" and error_code is not None:
            raise ValueError("successful audit events cannot have an error_code")
        if result != "success" and not error_code:
            raise ValueError("failed audit events require an error_code")

    @staticmethod
    def _validate_metadata(
        metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = dict(metadata or {})
        unsupported = sorted(set(normalized) - AUDIT_METADATA_KEYS)
        if unsupported:
            raise ValueError(
                f"unsupported audit metadata keys: {', '.join(unsupported)}"
            )

        for key, value in normalized.items():
            if key == "changed_fields":
                if not isinstance(value, list) or not all(
                    isinstance(field, str) and _FIELD_NAME_PATTERN.fullmatch(field)
                    for field in value
                ):
                    raise ValueError("changed_fields must contain field names")
            elif key in {"before", "after"}:
                if value is not None and not (
                    isinstance(value, bool)
                    or (isinstance(value, str) and _ENUM_VALUE_PATTERN.fullmatch(value))
                ):
                    raise ValueError(f"{key} must be a non-sensitive enum value")
            elif key in _IDENTIFIER_METADATA_KEYS:
                if not isinstance(value, str) or not value or len(value) > 128:
                    raise ValueError(f"{key} must be a non-empty identifier")
            elif key in _REVISION_METADATA_KEYS:
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"{key} must be a non-negative integer")
            elif key in {"reason", "intent", "phase"}:
                if not isinstance(value, str) or not _ENUM_VALUE_PATTERN.fullmatch(
                    value
                ):
                    raise ValueError("reason must be a stable enum value")
            elif key == "owner_reassignment_reason":
                if (
                    not isinstance(value, str)
                    or value != value.strip()
                    or not 3 <= len(value) <= 500
                    or any(ord(character) < 32 for character in value)
                ):
                    raise ValueError("owner reassignment reason is invalid")

        return normalized
