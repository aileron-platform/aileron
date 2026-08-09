"""Create and refresh local authorization snapshots from OIDC claims."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.identity.advisory_lock import acquire_identity_lock
from app.modules.identity.user_authorization_policy import canonical_role_issues


class UserSnapshotSyncService:
    """Provision a local member snapshot without managing the external account."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_from_claims(
        self, claims: dict[str, object], *, issuer: str | None = None
    ) -> db_models.User:
        """Synchronize a successful OIDC login into the local authorization store."""

        subject = self._required_text_claim(claims.get("sub"), "sub")
        trusted_issuer = issuer or self._required_text_claim(claims.get("iss"), "iss")
        acquire_identity_lock(self.db, f"{trusted_issuer}:{subject}")
        username = self._display_identifier(claims, subject)
        now = datetime.now(timezone.utc)

        user = self.db.scalar(
            select(db_models.User).where(
                db_models.User.oidc_issuer == trusted_issuer,
                db_models.User.oidc_subject == subject,
            )
        )
        if user is None:
            user = db_models.User(
                id=str(uuid4()),
                oidc_issuer=trusted_issuer,
                oidc_subject=subject,
                username=username,
                is_active=True,
                identity_enabled=True,
                sync_status="local_shadow_imported",
                platform_role="member",
                role_status="valid",
                role_issues=canonical_role_issues("valid"),
            )
            self.db.add(user)
        else:
            user.oidc_issuer = trusted_issuer
            user.oidc_subject = subject
            user.identity_enabled = True
            user.sync_status = (
                "local_shadow_imported"
                if user.platform_role is None
                else "synced"
            )
            if user.platform_role is None:
                user.platform_role = "member"
                user.role_status = "valid"
                user.role_issues = canonical_role_issues("valid")

        user.username = username
        self._update_optional_profile(user, "email", claims, "email")
        self._update_optional_profile(user, "first_name", claims, "given_name")
        self._update_optional_profile(user, "last_name", claims, "family_name")
        self._update_optional_profile(user, "display_name", claims, "name")
        self._update_optional_profile(user, "avatar_url", claims, "picture")
        user.last_synced_at = now

        self.db.commit()
        self.db.refresh(user)
        return user

    @staticmethod
    def _required_text_claim(value: object, claim_name: str) -> str:
        max_length = 2048 if claim_name == "iss" else 255
        if not isinstance(value, str) or not value.strip() or len(value) > max_length:
            raise ValueError(f"OIDC {claim_name} claim is invalid")
        return value.strip()

    @classmethod
    def _display_identifier(cls, claims: dict[str, object], subject: str) -> str:
        for claim_name in ("preferred_username", "name", "username"):
            value = claims.get(claim_name)
            if isinstance(value, str) and value.strip() and len(value.strip()) <= 255:
                return value.strip()
        return subject[:255]

    @staticmethod
    def _update_optional_profile(
        user: db_models.User,
        attribute: str,
        claims: dict[str, object],
        claim_name: str,
    ) -> None:
        if claim_name not in claims:
            return
        value = claims[claim_name]
        max_length = 2048 if attribute == "avatar_url" else 255
        if value is None:
            setattr(user, attribute, None)
        elif (
            isinstance(value, str)
            and value.strip()
            and len(value.strip()) <= max_length
        ):
            setattr(user, attribute, value.strip())


__all__ = ["UserSnapshotSyncService"]
