"""Create the retained local bootstrap administrator snapshot."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

from app.db import models as db_models
from app.db.database import SessionLocal, create_tables
from app.modules.identity.user_authorization_policy import canonical_role_issues


def bootstrap_admin_user(
    *, issuer: str, subject: str, username: str, email: str | None = None
) -> str:
    """Create or verify the one retained bootstrap principal."""
    if not issuer.strip() or not subject.strip() or not username.strip():
        raise ValueError("issuer, subject, and username are required")
    create_tables()
    with SessionLocal() as db:
        user = db.query(db_models.User).filter(
            db_models.User.oidc_issuer == issuer,
            db_models.User.oidc_subject == subject,
        ).one_or_none()
        now = datetime.now(timezone.utc)
        if user is None:
            user = db_models.User(
                id=str(uuid4()),
                oidc_issuer=issuer.strip(),
                oidc_subject=subject.strip(),
                username=username.strip(),
                email=email.strip() if email else None,
                is_active=True,
                identity_enabled=True,
                sync_status="local_shadow_imported",
                platform_role="admin",
                role_status="valid",
                role_issues=canonical_role_issues("valid"),
                last_synced_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
        else:
            user.username = username.strip()
            user.email = email.strip() if email else user.email
            user.is_active = True
            user.identity_enabled = True
            user.platform_role = "admin"
            user.role_status = "valid"
            user.role_issues = canonical_role_issues("valid")
            user.sync_status = "synced"
            user.last_synced_at = now
        db.commit()
        return user.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer", default=os.getenv("OIDC_ISSUER_URL"))
    parser.add_argument("--subject", default=os.getenv("BOOTSTRAP_ADMIN_SUBJECT"))
    parser.add_argument(
        "--username",
        default=os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin"),
    )
    parser.add_argument("--email", default=os.getenv("BOOTSTRAP_ADMIN_EMAIL"))
    args = parser.parse_args()
    if not args.issuer or not args.subject:
        parser.error("--issuer and --subject are required")
    try:
        print(
            bootstrap_admin_user(
                issuer=args.issuer,
                subject=args.subject,
                username=args.username,
                email=args.email,
            )
        )
    except Exception as exc:
        print(f"Bootstrap administrator creation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
