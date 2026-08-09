from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare.py"
SPEC = importlib.util.spec_from_file_location("local_oidc_prepare", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("local OIDC prepare module is unavailable")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class SecretFileContractTest(unittest.TestCase):
    def test_exact_secret_rejects_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            secret_path = Path(temporary_directory) / "ldap-admin-password"
            secret_path.write_text("test-secret\n", encoding="utf-8")
            with patch.dict(os.environ, {"LDAP_ADMIN_PASSWORD_FILE": str(secret_path)}):
                with self.assertRaisesRegex(ValueError, "without surrounding whitespace"):
                    PREPARE.read_secret(
                        "LDAP_ADMIN_PASSWORD_FILE",
                        reject_surrounding_whitespace=True,
                    )

    def test_exact_secret_preserves_non_whitespace_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            secret_path = Path(temporary_directory) / "ldap-admin-password"
            secret_path.write_text("test-secret", encoding="utf-8")
            with patch.dict(os.environ, {"LDAP_ADMIN_PASSWORD_FILE": str(secret_path)}):
                value = PREPARE.read_secret(
                    "LDAP_ADMIN_PASSWORD_FILE",
                    reject_surrounding_whitespace=True,
                )

        self.assertEqual("test-secret", value)


if __name__ == "__main__":
    unittest.main()
