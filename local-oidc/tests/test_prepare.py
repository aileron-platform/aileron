from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


LOCAL_OIDC_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = LOCAL_OIDC_DIR / "prepare.py"
SPEC = importlib.util.spec_from_file_location("local_oidc_prepare", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("local OIDC prepare module is unavailable")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class RealmRenderContractTest(unittest.TestCase):
    def test_renders_keycloak_realm_with_the_platform_bootstrap_admin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            client_secret = root / "oidc-client-secret"
            platform_admin_password = root / "platform-admin-password"
            client_secret.write_text("manager-secret", encoding="utf-8")
            platform_admin_password.write_text("admin123", encoding="utf-8")
            environment = {
                "PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.test",
                "OIDC_CLIENT_ID": "aileron-manager",
                "OIDC_CLIENT_SECRET_FILE": str(client_secret),
                "BOOTSTRAP_ADMIN_SUBJECT": "00000000-0000-4000-8000-000000000001",
                "BOOTSTRAP_ADMIN_USERNAME": "admin",
                "BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
                "LOCAL_OIDC_PLATFORM_ADMIN_PASSWORD_FILE": str(platform_admin_password),
            }

            with patch.dict(os.environ, environment, clear=True):
                PREPARE.render(LOCAL_OIDC_DIR / "aileron-realm.template.json", root)

            realm = json.loads((root / "aileron-realm.json").read_text(encoding="utf-8"))

        self.assertFalse(realm["registrationAllowed"])
        self.assertNotIn("components", realm)
        self.assertEqual("aileron-manager", realm["clients"][0]["clientId"])
        self.assertEqual("manager-secret", realm["clients"][0]["secret"])
        self.assertEqual(
            "00000000-0000-4000-8000-000000000001",
            realm["users"][0]["id"],
        )
        self.assertEqual("admin", realm["users"][0]["username"])
        self.assertEqual("admin@example.test", realm["users"][0]["email"])
        self.assertEqual("admin123", realm["users"][0]["credentials"][0]["value"])

    def test_render_does_not_create_ldap_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "oidc-client-secret").write_text("manager-secret", encoding="utf-8")
            (root / "platform-admin-password").write_text("admin123", encoding="utf-8")
            environment = {
                "PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.test",
                "OIDC_CLIENT_ID": "aileron-manager",
                "OIDC_CLIENT_SECRET_FILE": str(root / "oidc-client-secret"),
                "BOOTSTRAP_ADMIN_SUBJECT": "00000000-0000-4000-8000-000000000001",
                "BOOTSTRAP_ADMIN_USERNAME": "admin",
                "BOOTSTRAP_ADMIN_EMAIL": "admin@example.test",
                "LOCAL_OIDC_PLATFORM_ADMIN_PASSWORD_FILE": str(root / "platform-admin-password"),
            }

            with patch.dict(os.environ, environment, clear=True):
                PREPARE.render(LOCAL_OIDC_DIR / "aileron-realm.template.json", root)

            self.assertEqual(["aileron-realm.json", "oidc-client-secret", "platform-admin-password"], sorted(path.name for path in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
