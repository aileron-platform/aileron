from __future__ import annotations

import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "generate_secrets.py"
SUBJECT_ARGS = [
    "--platform-admin-subject",
    "00000000-0000-4000-8000-000000000001",
]


class IdentitySecretStoreTest(unittest.TestCase):
    def test_external_postgres_store_omits_bundled_database_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = (
                private_root
                / "secrets/identity-artifacts/postgres-disabled"
            )
            values = private_root / "identity-values.json"
            values.write_text(
                json.dumps({"postgres": {"enabled": False}}), encoding="utf-8"
            )
            values.chmod(0o600)

            command = [
                "python3",
                str(SCRIPT),
                *SUBJECT_ARGS,
                "--private-root",
                str(private_root),
                "--output-dir",
                str(output_dir),
                "--values",
                str(values),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(
                [*command, "--validate-only"],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("identity-postgres", manifest["secrets"])
            self.assertFalse((output_dir / "identity-postgres").exists())
            self.assertTrue(
                all(
                    stat.S_IMODE(path.stat().st_mode) == 0o700
                    for path in (
                        private_root / "secrets",
                        private_root / "secrets/identity-artifacts",
                        output_dir,
                    )
                )
            )

    def test_generate_is_non_interactive_private_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = private_root / "identity-secrets"
            first = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )
            realm = json.loads(
                (output_dir / "keycloak-realm-import/realm.json").read_text(
                    encoding="utf-8"
                )
            )
            secret_files = sorted(
                path
                for path in output_dir.rglob("*")
                if path.is_file() and path.name != "manifest.json"
            )
            values = [path.read_text(encoding="utf-8") for path in secret_files]

            second = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(
                values, [path.read_text(encoding="utf-8") for path in secret_files]
            )
            self.assertEqual(0o700, stat.S_IMODE(output_dir.stat().st_mode))
            self.assertTrue(
                all(
                    stat.S_IMODE(path.stat().st_mode) == 0o600
                    for path in [*secret_files, output_dir / "manifest.json"]
                )
            )
            self.assertEqual(
                {
                    "aileron-oidc-client",
                    "identity-postgres",
                    "keycloak-bootstrap-admin",
                    "keycloak-platform-admin",
                    "keycloak-break-glass",
                    "keycloak-realm-import",
                },
                set(manifest["secrets"]),
            )
            self.assertEqual(
                ["subject", "username", "email", "password", "import.json"],
                manifest["secrets"]["keycloak-platform-admin"]["keys"],
            )
            self.assertEqual(
                ["username", "email", "password"],
                manifest["secrets"]["keycloak-break-glass"]["keys"],
            )
            self.assertFalse((output_dir / "keycloak-break-glass/subject").exists())
            self.assertFalse(realm["registrationAllowed"])
            self.assertNotIn("components", realm)
            self.assertEqual(
                [
                    {
                        "id": SUBJECT_ARGS[1],
                        "username": "admin",
                        "email": "admin@aileron.com",
                        "firstName": "Platform",
                        "lastName": "Administrator",
                        "enabled": True,
                        "emailVerified": True,
                    }
                ],
                realm["users"],
            )
            self.assertNotIn("credentials", realm["users"][0])
            platform_import = json.loads(
                (output_dir / "keycloak-platform-admin/import.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("SKIP", platform_import["ifResourceExists"])
            self.assertEqual(realm["users"], platform_import["users"])
            self.assertNotIn("credentials", platform_import["users"][0])
            for value in values:
                self.assertNotIn(
                    value, first.stdout + first.stderr + second.stdout + second.stderr
                )

    def test_homelab_defaults_are_explicit_and_generic_password_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            generic = private_root / "generic"
            homelab = private_root / "homelab"
            for output_dir, extra in (
                (generic, []),
                (homelab, ["--homelab-insecure-defaults"]),
            ):
                subprocess.run(
                    [
                        "python3",
                        str(SCRIPT),
                        *SUBJECT_ARGS,
                        "--private-root",
                        str(private_root),
                        "--output-dir",
                        str(output_dir),
                        *extra,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            self.assertEqual(
                "admin",
                (homelab / "keycloak-platform-admin/username").read_text(),
            )
            self.assertEqual(
                "admin123",
                (homelab / "keycloak-platform-admin/password").read_text(),
            )
            self.assertNotEqual(
                "admin123",
                (generic / "keycloak-platform-admin/password").read_text(),
            )
            self.assertEqual(
                "admin",
                (generic / "keycloak-platform-admin/username").read_text(),
            )
            self.assertGreaterEqual(
                len((generic / "keycloak-platform-admin/password").read_text()), 48
            )

    def test_validate_only_rejects_incomplete_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(private_root),
                    "--validate-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("password", result.stdout.lower())

    def test_existing_store_is_extended_without_rotating_existing_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = private_root / "identity-secrets"
            command = [
                "python3",
                str(SCRIPT),
                *SUBJECT_ARGS,
                "--private-root",
                str(private_root),
                "--output-dir",
                str(output_dir),
                "--homelab-insecure-defaults",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            preserved = {
                path.relative_to(output_dir): path.read_text(encoding="utf-8")
                for path in output_dir.rglob("*")
                if path.is_file()
                and "keycloak-platform-admin" not in path.parts
                and path.name != "manifest.json"
            }
            shutil.rmtree(output_dir / "keycloak-platform-admin")
            manifest = json.loads((output_dir / "manifest.json").read_text())
            manifest["secrets"].pop("keycloak-platform-admin")
            (output_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            (output_dir / "manifest.json").chmod(0o600)

            subprocess.run(command, check=True, capture_output=True, text=True)
            first_platform_values = {
                path.name: path.read_text(encoding="utf-8")
                for path in (output_dir / "keycloak-platform-admin").iterdir()
            }
            subprocess.run(command, check=True, capture_output=True, text=True)

            self.assertEqual(
                preserved,
                {
                    path: (output_dir / path).read_text(encoding="utf-8")
                    for path in preserved
                },
            )
            self.assertEqual(
                first_platform_values,
                {
                    path.name: path.read_text(encoding="utf-8")
                    for path in (output_dir / "keycloak-platform-admin").iterdir()
                },
            )

    def test_existing_platform_subject_mismatch_fails_without_import_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = private_root / "identity-secrets"
            base_command = [
                "python3",
                str(SCRIPT),
                *SUBJECT_ARGS,
                "--private-root",
                str(private_root),
                "--output-dir",
                str(output_dir),
            ]
            subprocess.run(base_command, check=True, capture_output=True, text=True)
            import_path = output_dir / "keycloak-platform-admin/import.json"
            original_import = import_path.read_text(encoding="utf-8")

            mismatch = subprocess.run(
                [
                    *base_command[:2],
                    "--platform-admin-subject",
                    "00000000-0000-4000-8000-000000000099",
                    *base_command[4:],
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(0, mismatch.returncode)
            self.assertIn("does not match", mismatch.stderr)
            self.assertEqual(
                SUBJECT_ARGS[1],
                (output_dir / "keycloak-platform-admin/subject").read_text(),
            )
            self.assertEqual(original_import, import_path.read_text(encoding="utf-8"))

    def test_rejects_symlinked_existing_artifact_and_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = private_root / "identity-secrets"
            subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
            )
            target = private_root / "target"
            target.write_text("do-not-read", encoding="utf-8")
            target.chmod(0o600)
            artifact = output_dir / "aileron-oidc-client/client-secret"
            artifact.unlink()
            artifact.symlink_to(target)

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(output_dir),
                    "--validate-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symbolic link", result.stderr)

    def test_generation_rejects_dangling_existing_artifact_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            private_root = Path(temporary_directory).resolve()
            output_dir = private_root / "identity-secrets"
            artifact = output_dir / "aileron-oidc-client/client-secret"
            artifact.parent.mkdir(parents=True)
            output_dir.chmod(0o700)
            artifact.parent.chmod(0o700)
            artifact.symlink_to(private_root / "missing-target")

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(private_root),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symbolic link", result.stderr)


if __name__ == "__main__":
    unittest.main()
