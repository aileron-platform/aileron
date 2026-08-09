#!/usr/bin/env python3
"""Render local OIDC and LDAP fixtures without persisting secret material."""

from __future__ import annotations

import argparse
import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def require_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def read_secret(
    environment_name: str,
    *,
    reject_surrounding_whitespace: bool = False,
) -> str:
    path = Path(require_environment(environment_name))
    raw_value = path.read_text(encoding="utf-8")
    if reject_surrounding_whitespace and raw_value != raw_value.strip():
        raise ValueError(
            f"{environment_name} must reference exact bytes without surrounding whitespace"
        )
    value = raw_value.rstrip("\r\n")
    if not value:
        raise ValueError(f"{environment_name} references an empty secret")
    return value


def validate_origin(value: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("PLATFORM_PUBLIC_ORIGIN must be an exact origin")


def replace_tokens(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: replace_tokens(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tokens(item, replacements) for item in value]
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    return value


def write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as temporary_file:
        temporary_file.write(content)
        temporary_path = Path(temporary_file.name)
    temporary_path.chmod(0o600)
    temporary_path.replace(path)


def ldif_password(value: str) -> str:
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"userPassword:: {encoded}"


def render(template_path: Path, output_dir: Path) -> None:
    origin = require_environment("PLATFORM_PUBLIC_ORIGIN")
    validate_origin(origin)

    ldap_admin_password = read_secret(
        "LDAP_ADMIN_PASSWORD_FILE",
        reject_surrounding_whitespace=True,
    )
    read_secret(
        "LDAP_CONFIG_PASSWORD_FILE",
        reject_surrounding_whitespace=True,
    )

    replacements = {
        "__PLATFORM_PUBLIC_ORIGIN__": origin,
        "__OIDC_CALLBACK_URL__": f"{origin}/api/v1/oauth2/callback",
        "__OIDC_LOGOUT_PATTERN__": f"{origin}/*",
        "__OIDC_CLIENT_ID__": require_environment("OIDC_CLIENT_ID"),
        "__OIDC_CLIENT_SECRET__": read_secret("OIDC_CLIENT_SECRET_FILE"),
        "__LDAP_BIND_CREDENTIAL__": ldap_admin_password,
        "__LOCAL_ADMIN_SUBJECT__": require_environment("BOOTSTRAP_ADMIN_SUBJECT"),
        "__LOCAL_ADMIN_USERNAME__": require_environment("BOOTSTRAP_ADMIN_USERNAME"),
        "__LOCAL_ADMIN_EMAIL__": require_environment("BOOTSTRAP_ADMIN_EMAIL"),
        "__LOCAL_ADMIN_PASSWORD__": read_secret("LOCAL_ADMIN_PASSWORD_FILE"),
    }
    template = json.loads(template_path.read_text(encoding="utf-8"))
    rendered = replace_tokens(template, replacements)
    write_private_text(
        output_dir / "aileron-realm.json",
        json.dumps(rendered, ensure_ascii=False, indent=2) + "\n",
    )

    alice_password = read_secret("LDAP_ALICE_PASSWORD_FILE")
    bob_password = read_secret("LDAP_BOB_PASSWORD_FILE")
    seed = f"""dn: ou=people,dc=aileron,dc=local
objectClass: organizationalUnit
ou: people

dn: uid=alice,ou=people,dc=aileron,dc=local
objectClass: inetOrgPerson
objectClass: organizationalPerson
cn: Alice Aileron
sn: Aileron
givenName: Alice
uid: alice
mail: alice@example.com
{ldif_password(alice_password)}

dn: uid=bob,ou=people,dc=aileron,dc=local
objectClass: inetOrgPerson
objectClass: organizationalPerson
cn: Bob Aileron
sn: Aileron
givenName: Bob
uid: bob
mail: bob@example.com
{ldif_password(bob_password)}
"""
    write_private_text(output_dir / "10-seed-users.ldif", seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare local OIDC runtime fixtures")
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    render(arguments.template, arguments.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
