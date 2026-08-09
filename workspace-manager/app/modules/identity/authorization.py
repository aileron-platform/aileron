"""Snapshot-backed platform authorization."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy


class PlatformAuthorizationService:
    """Authorize platform actions from the local user snapshot."""

    def __init__(
        self,
        db: Session,
        *,
        authorization_policy: UserAuthorizationPolicy | None = None,
    ) -> None:
        self.db = db
        self.authorization_policy = authorization_policy or UserAuthorizationPolicy()

    def get_valid_user(self, user_id: str | None) -> db_models.User | None:
        """Return the valid local authorization snapshot, or fail closed with None."""

        user = self.db.get(db_models.User, user_id) if user_id else None
        return user if self._is_valid_snapshot(user) else None

    def _is_valid_snapshot(self, user: db_models.User | None) -> bool:
        return self.authorization_policy.is_authorized(user)
