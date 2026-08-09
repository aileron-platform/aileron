"""OIDC fixture secret-file contract tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class OidcFixtureSecretFileTest(unittest.TestCase):
    def test_client_secret_is_required_from_file(self) -> None:
        environment = {
            **os.environ,
            "OIDC_FIXTURE_ISSUER": "https://oidc-fixture:8443",
            "OIDC_FIXTURE_CLIENT_SECRET": "forbidden-plaintext-secret",
        }
        environment.pop("OIDC_FIXTURE_CLIENT_SECRET_FILE", None)

        completed = subprocess.run(
            [sys.executable, "-c", "import product_conformance.oidc_fixture"],
            check=False,
            capture_output=True,
            env=environment,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("OIDC_FIXTURE_CLIENT_SECRET_FILE", completed.stderr)

    def test_client_secret_is_loaded_from_required_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            secret_path = Path(temporary_directory) / "client-secret"
            secret_path.write_text("runtime-generated-secret\n", encoding="utf-8")
            environment = {
                **os.environ,
                "OIDC_FIXTURE_ISSUER": "https://oidc-fixture:8443",
                "OIDC_FIXTURE_CLIENT_SECRET_FILE": str(secret_path),
            }
            environment.pop("OIDC_FIXTURE_CLIENT_SECRET", None)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from product_conformance.oidc_fixture import STATE; "
                        "print(STATE.client_secret)"
                    ),
                ],
                check=False,
                capture_output=True,
                env=environment,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "runtime-generated-secret")


if __name__ == "__main__":
    unittest.main()
