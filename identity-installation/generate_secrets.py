"""Create or validate the private artifacts required by the Identity Plane."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

SECRET_LAYOUT = {
    "identity-postgres": ("username", "password"),
    "aileron-oidc-client": ("client-secret",),
    "keycloak-bootstrap-admin": ("username", "password"),
    "keycloak-platform-admin": (
        "subject",
        "username",
        "email",
        "password",
        "import.json",
    ),
    "keycloak-break-glass": ("username", "email", "password"),
    "keycloak-realm-import": ("realm.json",),
}
SUBJECT_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("Identity Secret path must not contain a symbolic link")


def validate_private_root(private_root: Path, output_dir: Path) -> None:
    if not private_root.is_absolute() or not output_dir.is_absolute():
        raise ValueError("Identity Secret paths must be absolute")
    reject_symlink_components(private_root)
    reject_symlink_components(output_dir)
    private_root_metadata = os.lstat(private_root)
    if (
        not stat.S_ISDIR(private_root_metadata.st_mode)
        or stat.S_IMODE(private_root_metadata.st_mode) != 0o700
        or private_root_metadata.st_uid != os.geteuid()
    ):
        raise ValueError(
            "Identity Secret private root must be an owner-controlled mode 0700 directory"
        )
    try:
        output_dir.resolve(strict=False).relative_to(private_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Identity Secret output must be within the private root"
        ) from exc


def prepare_private_output_directory(private_root: Path, output_dir: Path) -> None:
    relative = output_dir.resolve(strict=False).relative_to(
        private_root.resolve(strict=True)
    )
    current = private_root
    for component in relative.parts:
        current /= component
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        metadata = os.lstat(current)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()
        ):
            raise ValueError(
                "Identity Secret output parents must be owner-controlled "
                "mode 0700 directories"
            )


def read_private(path: Path) -> str:
    reject_symlink_components(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError("Identity Secret artifact is unreadable") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise ValueError("Identity Secret artifact must be a mode 0600 file")
        value = os.read(descriptor, metadata.st_size + 1).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Identity Secret artifact is not UTF-8") from exc
    finally:
        os.close(descriptor)
    return value


def private_write(path: Path, value: str) -> None:
    reject_symlink_components(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(value)
        temporary_path = Path(handle.name)
    temporary_path.chmod(0o600)
    temporary_path.replace(path)


def secret_value(path: Path, factory: Callable[[], str]) -> str:
    if path.exists():
        value = read_private(path)
        if not value or value != value.strip():
            raise ValueError(
                f"invalid Secret artifact: {path.relative_to(path.parents[1])}"
            )
        path.chmod(0o600)
        return value
    value = factory()
    private_write(path, value)
    return value


def _secret_layout(postgres_enabled: bool) -> dict[str, tuple[str, ...]]:
    return {
        name: keys
        for name, keys in SECRET_LAYOUT.items()
        if postgres_enabled or name != "identity-postgres"
    }


def generate(
    output_dir: Path,
    *,
    private_root: Path,
    realm: str,
    platform_origin: str,
    client_id: str,
    platform_admin_subject: str,
    homelab_insecure_defaults: bool = False,
    postgres_enabled: bool = True,
) -> None:
    if SUBJECT_PATTERN.fullmatch(platform_admin_subject) is None:
        raise ValueError("platform administrator subject must be a canonical UUID")
    validate_private_root(private_root, output_dir)
    prepare_private_output_directory(private_root, output_dir)
    if not postgres_enabled and (output_dir / "identity-postgres").exists():
        raise ValueError(
            "external Identity database mode forbids bundled PostgreSQL artifacts"
        )

    if postgres_enabled:
        secret_value(output_dir / "identity-postgres/username", lambda: "keycloak")
        secret_value(
            output_dir / "identity-postgres/password",
            lambda: secrets.token_urlsafe(48),
        )
    client_secret = secret_value(
        output_dir / "aileron-oidc-client/client-secret",
        lambda: secrets.token_urlsafe(48),
    )
    secret_value(
        output_dir / "keycloak-bootstrap-admin/username", lambda: "keycloak-admin"
    )
    secret_value(
        output_dir / "keycloak-bootstrap-admin/password",
        lambda: secrets.token_urlsafe(48),
    )
    stored_platform_admin_subject = secret_value(
        output_dir / "keycloak-platform-admin/subject",
        lambda: platform_admin_subject,
    )
    if stored_platform_admin_subject != platform_admin_subject:
        raise ValueError(
            "existing platform administrator subject does not match the requested subject"
        )
    platform_admin_username = secret_value(
        output_dir / "keycloak-platform-admin/username",
        lambda: "admin",
    )
    platform_admin_email = secret_value(
        output_dir / "keycloak-platform-admin/email",
        lambda: "admin@aileron.com",
    )
    secret_value(
        output_dir / "keycloak-platform-admin/password",
        lambda: "admin123" if homelab_insecure_defaults else secrets.token_urlsafe(48),
    )
    secret_value(
        output_dir / "keycloak-break-glass/username", lambda: "local-emergency-admin"
    )
    secret_value(
        output_dir / "keycloak-break-glass/email", lambda: "emergency@aileron.local"
    )
    secret_value(
        output_dir / "keycloak-break-glass/password", lambda: secrets.token_urlsafe(48)
    )

    platform_admin_import = {
        "ifResourceExists": "SKIP",
        "users": [
            {
                "id": stored_platform_admin_subject,
                "username": platform_admin_username,
                "email": platform_admin_email,
                "firstName": "Platform",
                "lastName": "Administrator",
                "enabled": True,
                "emailVerified": True,
            }
        ],
    }
    private_write(
        output_dir / "keycloak-platform-admin/import.json",
        json.dumps(platform_admin_import, separators=(",", ":")),
    )

    realm_document = {
        "realm": realm,
        "enabled": True,
        "registrationAllowed": False,
        "loginWithEmailAllowed": True,
        "duplicateEmailsAllowed": False,
        "roles": {"realm": [{"name": "platform-member"}, {"name": "platform-admin"}]},
        "users": platform_admin_import["users"],
        "clients": [
            {
                "clientId": client_id,
                "enabled": True,
                "protocol": "openid-connect",
                "publicClient": False,
                "clientAuthenticatorType": "client-secret",
                "secret": client_secret,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": [f"{platform_origin}/api/v1/oauth2/callback"],
                "webOrigins": [platform_origin],
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "post.logout.redirect.uris": f"{platform_origin}/*",
                },
                "defaultClientScopes": ["web-origins", "acr", "profile", "email"],
            }
        ],
    }
    private_write(
        output_dir / "keycloak-realm-import/realm.json",
        json.dumps(realm_document, separators=(",", ":")),
    )
    manifest = {
        "version": 1,
        "secrets": {
            name: {"keys": list(keys)}
            for name, keys in _secret_layout(postgres_enabled).items()
        },
    }
    private_write(output_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def validate(
    output_dir: Path, private_root: Path, *, postgres_enabled: bool = True
) -> None:
    validate_private_root(private_root, output_dir)
    output_metadata = os.lstat(output_dir)
    if (
        not stat.S_ISDIR(output_metadata.st_mode)
        or stat.S_IMODE(output_metadata.st_mode) != 0o700
    ):
        raise ValueError("Identity Secret output directory is missing or not mode 0700")
    if not postgres_enabled and (output_dir / "identity-postgres").exists():
        raise ValueError(
            "external Identity database mode forbids bundled PostgreSQL artifacts"
        )
    for secret_name, keys in _secret_layout(postgres_enabled).items():
        for key in keys:
            path = output_dir / secret_name / key
            if not read_private(path):
                raise ValueError(
                    f"invalid Identity Secret artifact: {secret_name}/{key}"
                )
    manifest_path = output_dir / "manifest.json"
    if not read_private(manifest_path):
        raise ValueError("invalid Identity Secret manifest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or validate Identity Plane Secret artifacts"
    )
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--realm", default="aileron")
    parser.add_argument("--platform-origin", default="https://aileron.example.test")
    parser.add_argument("--client-id", default="aileron-frontend")
    parser.add_argument("--platform-admin-subject")
    parser.add_argument(
        "--homelab-insecure-defaults",
        action="store_true",
        help="Use documented local-only platform administrator credentials",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--values", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    postgres_enabled = True
    if arguments.values is not None:
        try:
            values = json.loads(arguments.values.read_text(encoding="utf-8"))
            postgres_enabled = values["postgres"]["enabled"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Identity values are unreadable or invalid") from exc
        if not isinstance(postgres_enabled, bool):
            raise ValueError("Identity values postgres.enabled is invalid")
    if not arguments.validate_only:
        if arguments.platform_admin_subject is None:
            raise ValueError(
                "platform administrator subject is required for generation"
            )
        generate(
            arguments.output_dir,
            private_root=arguments.private_root,
            realm=arguments.realm,
            platform_origin=arguments.platform_origin.rstrip("/"),
            client_id=arguments.client_id,
            platform_admin_subject=arguments.platform_admin_subject,
            homelab_insecure_defaults=arguments.homelab_insecure_defaults,
            postgres_enabled=postgres_enabled,
        )
    validate(
        arguments.output_dir,
        arguments.private_root,
        postgres_enabled=postgres_enabled,
    )
    print(f"Identity Secret artifacts are valid: {arguments.output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"Identity Secret validation failed: {error}", file=os.sys.stderr)
        raise SystemExit(1)
