from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

INSTALLATION_DIR = Path(__file__).resolve().parents[1]
NAMESPACE_UID = "11111111-1111-4111-8111-111111111111"
SUBJECT_ARGS = [
    "--platform-admin-subject",
    "00000000-0000-4000-8000-000000000001",
]


class ApplyIdentitySecretsTest(unittest.TestCase):
    def create_external_files(self, root: Path) -> list[Path]:
        docker_config = root / "dockerconfig.json"
        docker_config.write_text(
            json.dumps({"auths": {"harbor.example.test": {"auth": "dGVzdDp0ZXN0"}}}),
            encoding="utf-8",
        )
        tls_key = root / "tls.key"
        tls_certificate = root / "tls.crt"
        values = root / "identity-values.json"
        values.write_text(json.dumps({"postgres": {"enabled": True}}), encoding="utf-8")
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-subj",
                "/CN=keycloak.example.test",
                "-keyout",
                str(tls_key),
                "-out",
                str(tls_certificate),
                "-days",
                "1",
            ],
            check=True,
            capture_output=True,
        )
        files = [docker_config, tls_certificate, tls_key, values]
        for path in files:
            path.chmod(0o600)
        return files

    def test_server_dry_run_uses_exact_context_namespace_and_private_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            subprocess.run(
                [
                    "python3",
                    str(INSTALLATION_DIR / "generate_secrets.py"),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(root),
                    "--output-dir",
                    str(artifacts),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log = root / "kubectl.log"
            mock = bin_dir / "kubectl"
            mock.write_text(
                """#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$KUBECTL_TEST_LOG"
case " $* " in
  *' get namespace '*) printf '%s' '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"aileron-identity-system","uid":"11111111-1111-4111-8111-111111111111","resourceVersion":"17","labels":{"platform.aileron.dev/namespace-owner":"aileron-installer","pod-security.kubernetes.io/enforce":"restricted","pod-security.kubernetes.io/audit":"restricted","pod-security.kubernetes.io/warn":"restricted"}},"status":{"phase":"Active"}}' ;;
  *' get secret '*)
    if test "${SECRET_LOOKUP_MODE:-notfound}" = forbidden; then
      printf '%s\n' 'Error from server (Forbidden): secrets is forbidden' >&2
    else
      printf '%s\n' 'Error from server (NotFound): secrets "missing" not found' >&2
    fi
    exit 1
    ;;
  *' create secret generic '*) printf '%s\\n' '{"apiVersion":"v1","kind":"Secret","metadata":{}}' ;;
  *' label --local '*)
    previous=
    for argument do
      if test "$previous" = -f; then cat "$argument"; exit 0; fi
      previous=$argument
    done
    exit 1
    ;;
  *' apply '*)
    for manifest do :; done
    python3 - "$manifest" <<'PY'
import stat
import sys
from pathlib import Path
raise SystemExit(0 if stat.S_IMODE(Path(sys.argv[1]).stat().st_mode) == 0o600 else 1)
PY
    printf '%s\\n' 'secret/contract server-dry-run'
    ;;
esac
""",
                encoding="utf-8",
            )
            mock.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "KUBECTL_TEST_LOG": str(log),
            }
            external_files = self.create_external_files(root)
            kubeconfig = root / "kubeconfig"
            kubeconfig.write_text("test-kubeconfig", encoding="utf-8")
            kubeconfig.chmod(0o600)

            command = [
                "sh",
                str(INSTALLATION_DIR / "apply_secrets.sh"),
                "--artifact-dir",
                str(artifacts),
                "--private-root",
                str(root),
                "--context",
                "homelab-contract",
                "--kubeconfig",
                str(kubeconfig),
                "--namespace",
                "aileron-identity-system",
                "--expected-namespace-uid",
                NAMESPACE_UID,
                "--image-pull-secret-file",
                str(external_files[0]),
                "--tls-cert-file",
                str(external_files[1]),
                "--tls-key-file",
                str(external_files[2]),
                "--values",
                str(external_files[3]),
                "--dry-run",
            ]
            result = subprocess.run(
                command,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            forbidden = subprocess.run(
                command,
                env=environment | {"SECRET_LOOKUP_MODE": "forbidden"},
                capture_output=True,
                text=True,
                check=False,
            )
            calls = log.read_text(encoding="utf-8")
            secret_values = [
                path.read_text(encoding="utf-8")
                for path in artifacts.rglob("*")
                if path.is_file()
            ] + [path.read_text(encoding="utf-8") for path in external_files]

        expected_secrets = {
            "identity-postgres",
            "keycloak-bootstrap-admin",
            "keycloak-platform-admin",
            "keycloak-break-glass",
            "keycloak-realm-import",
            "harbor-rke-creds",
            "keycloak-apps-tls",
        }
        created_secrets = {
            line.split(" create secret generic ", 1)[1].split()[0]
            for line in calls.splitlines()
            if " create secret generic " in line
        }
        self.assertEqual(expected_secrets, created_secrets)
        self.assertEqual(7, calls.count(" label --local "))
        self.assertEqual(7, calls.count("--dry-run=server"))
        self.assertEqual(5, calls.count("--type=Opaque"))
        self.assertNotIn("--dry-run=client", calls.splitlines()[-1])
        self.assertTrue(
            all(
                "--context homelab-contract --namespace aileron-identity-system" in line
                for line in calls.splitlines()
                if " secret " in f" {line} " or " apply " in f" {line} "
            )
        )
        self.assertIn(
            "get namespace aileron-identity-system " "--output=json",
            calls,
        )
        self.assertIn("platform.aileron.dev/secret-owner=aileron-installer", calls)
        break_glass_creation = next(
            line
            for line in calls.splitlines()
            if "create secret generic keycloak-break-glass" in line
        )
        self.assertNotIn("subject=", break_glass_creation)
        for value in secret_values:
            self.assertNotIn(value, result.stdout + result.stderr)
        self.assertNotEqual(forbidden.returncode, 0)
        self.assertIn("ownership lookup failed", forbidden.stderr)

    def test_external_postgres_dry_run_projects_credentials_and_ca(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            external_files = self.create_external_files(root)
            external_files[3].write_text(
                json.dumps({"postgres": {"enabled": False}}), encoding="utf-8"
            )
            postgres_username = root / "postgres-username"
            postgres_password = root / "postgres-password"
            postgres_username.write_text("identity_login", encoding="utf-8")
            postgres_password.write_text("identity-password", encoding="utf-8")
            for path in (postgres_username, postgres_password):
                path.chmod(0o600)
            subprocess.run(
                [
                    "python3",
                    str(INSTALLATION_DIR / "generate_secrets.py"),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(root),
                    "--output-dir",
                    str(artifacts),
                    "--values",
                    str(external_files[3]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log = root / "kubectl.log"
            kubectl = bin_dir / "kubectl"
            kubectl.write_text(
                """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$KUBECTL_TEST_LOG"
case " $* " in
  *' get namespace '*) printf '%s' '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"aileron-identity-system","uid":"11111111-1111-4111-8111-111111111111","resourceVersion":"17","labels":{"platform.aileron.dev/namespace-owner":"aileron-installer","pod-security.kubernetes.io/enforce":"restricted","pod-security.kubernetes.io/audit":"restricted","pod-security.kubernetes.io/warn":"restricted"}},"status":{"phase":"Active"}}' ;;
  *' get secret '*) printf '%s\n' 'Error from server (NotFound): secrets "missing" not found' >&2; exit 1 ;;
  *' create secret generic '*) printf '%s\n' '{"apiVersion":"v1","kind":"Secret","metadata":{}}' ;;
  *' label --local '*)
    previous=
    for argument do
      if test "$previous" = -f; then cat "$argument"; exit 0; fi
      previous=$argument
    done
    exit 1
    ;;
  *' apply '*) printf '%s\n' 'secret/contract server-dry-run' ;;
esac
""",
                encoding="utf-8",
            )
            kubectl.chmod(0o755)
            kubeconfig = root / "kubeconfig"
            kubeconfig.write_text("test-kubeconfig", encoding="utf-8")
            kubeconfig.chmod(0o600)

            subprocess.run(
                [
                    "sh",
                    str(INSTALLATION_DIR / "apply_secrets.sh"),
                    "--artifact-dir",
                    str(artifacts),
                    "--private-root",
                    str(root),
                    "--context",
                    "homelab-contract",
                    "--kubeconfig",
                    str(kubeconfig),
                    "--namespace",
                    "aileron-identity-system",
                    "--expected-namespace-uid",
                    NAMESPACE_UID,
                    "--image-pull-secret-file",
                    str(external_files[0]),
                    "--tls-cert-file",
                    str(external_files[1]),
                    "--tls-key-file",
                    str(external_files[2]),
                    "--values",
                    str(external_files[3]),
                    "--postgres-username-file",
                    str(postgres_username),
                    "--postgres-password-file",
                    str(postgres_password),
                    "--postgres-ca-file",
                    str(external_files[1]),
                    "--dry-run",
                ],
                env=os.environ
                | {
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "KUBECTL_TEST_LOG": str(log),
                },
                check=True,
                capture_output=True,
                text=True,
            )
            calls = log.read_text(encoding="utf-8")

        self.assertIn("create secret generic identity-postgres", calls)
        self.assertIn("create secret generic aileron-identity-database-ca", calls)
        self.assertFalse((artifacts / "identity-postgres").exists())

    def test_rejects_malformed_harbor_input_before_kubernetes_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            subprocess.run(
                [
                    "python3",
                    str(INSTALLATION_DIR / "generate_secrets.py"),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(root),
                    "--output-dir",
                    str(artifacts),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            external_files = self.create_external_files(root)
            external_files[0].write_text('{"auths": {}}', encoding="utf-8")
            kubeconfig = root / "kubeconfig"
            kubeconfig.write_text("test-kubeconfig", encoding="utf-8")
            kubeconfig.chmod(0o600)
            result = subprocess.run(
                [
                    "sh",
                    str(INSTALLATION_DIR / "apply_secrets.sh"),
                    "--artifact-dir",
                    str(artifacts),
                    "--private-root",
                    str(root),
                    "--context",
                    "homelab-contract",
                    "--kubeconfig",
                    str(kubeconfig),
                    "--namespace",
                    "aileron-identity-system",
                    "--expected-namespace-uid",
                    NAMESPACE_UID,
                    "--image-pull-secret-file",
                    str(external_files[0]),
                    "--tls-cert-file",
                    str(external_files[1]),
                    "--tls-key-file",
                    str(external_files[2]),
                    "--values",
                    str(external_files[3]),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("non-empty auths", result.stderr)
        self.assertNotIn("contract-secret", result.stdout + result.stderr)

    def test_namespace_replacement_after_pending_intent_blocks_real_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            subprocess.run(
                [
                    "python3",
                    str(INSTALLATION_DIR / "generate_secrets.py"),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(root),
                    "--output-dir",
                    str(artifacts),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            external_files = self.create_external_files(root)
            kubeconfig = root / "kubeconfig"
            kubeconfig.write_text("test-kubeconfig", encoding="utf-8")
            kubeconfig.chmod(0o600)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            namespace_count = root / "namespace-count"
            mutation_called = root / "mutation-called"
            kubectl = bin_dir / "kubectl"
            kubectl.write_text(
                """#!/bin/sh
set -eu
case " $* " in
  *' get namespace '*)
    count=0
    test ! -f "$NAMESPACE_COUNT" || count=$(cat "$NAMESPACE_COUNT")
    count=$((count + 1))
    printf '%s' "$count" >"$NAMESPACE_COUNT"
    uid=11111111-1111-4111-8111-111111111111
    test "$count" -lt 5 || uid=22222222-2222-4222-8222-222222222222
    printf '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"aileron-identity-system","uid":"%s","resourceVersion":"17","labels":{"platform.aileron.dev/namespace-owner":"aileron-installer","pod-security.kubernetes.io/enforce":"restricted","pod-security.kubernetes.io/audit":"restricted","pod-security.kubernetes.io/warn":"restricted"}},"status":{"phase":"Active"}}' "$uid"
    ;;
  *' get secret '*)
    printf '%s\n' 'Error from server (NotFound): secrets "missing" not found' >&2
    exit 1
    ;;
  *' create secret generic '*)
    name=
    previous=
    for argument do
      if test "$previous" = generic; then name=$argument; break; fi
      previous=$argument
    done
    printf '{"apiVersion":"v1","kind":"Secret","metadata":{"name":"%s","namespace":"aileron-identity-system"},"type":"Opaque","data":{}}' "$name"
    ;;
  *' label --local '*)
    previous=
    for argument do
      if test "$previous" = -f; then cat "$argument"; exit 0; fi
      previous=$argument
    done
    exit 1
    ;;
  *' apply '*) exit 0 ;;
  *' create --filename '*|*' replace --filename '*)
    : >"$MUTATION_CALLED"
    exit 0
    ;;
esac
""",
                encoding="utf-8",
            )
            kubectl.chmod(0o755)
            python_wrapper = bin_dir / "python3"
            python_wrapper.write_text(
                """#!/bin/sh
set -eu
if test "${1##*/}" = installation_transaction.py && test "${2:-}" = prepare-secret-mutation; then
  printf '%s\n' '{"state":"absent","transactionMarker":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
  exit 0
fi
if test "${1##*/}" = installation_transaction.py && test "${2:-}" = record-secret-post-state; then
  exit 0
fi
exec "$REAL_PYTHON" "$@"
""",
                encoding="utf-8",
            )
            python_wrapper.chmod(0o755)
            environment = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "REAL_PYTHON": os.environ.get("PYTHON", "/usr/local/bin/python3"),
                "NAMESPACE_COUNT": str(namespace_count),
                "MUTATION_CALLED": str(mutation_called),
            }
            result = subprocess.run(
                [
                    "sh",
                    str(INSTALLATION_DIR / "apply_secrets.sh"),
                    "--artifact-dir",
                    str(artifacts),
                    "--private-root",
                    str(root),
                    "--context",
                    "homelab-contract",
                    "--kubeconfig",
                    str(kubeconfig),
                    "--namespace",
                    "aileron-identity-system",
                    "--expected-namespace-uid",
                    NAMESPACE_UID,
                    "--transaction-directory",
                    str(root / "transaction"),
                    "--transaction-commit",
                    "a" * 40,
                    "--image-pull-secret-file",
                    str(external_files[0]),
                    "--tls-cert-file",
                    str(external_files[1]),
                    "--tls-key-file",
                    str(external_files[2]),
                    "--values",
                    str(external_files[3]),
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("namespace identity changed", result.stderr)
        self.assertFalse(mutation_called.exists())

    def test_rejects_invalid_tls_before_kubernetes_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts = root / "artifacts"
            subprocess.run(
                [
                    "python3",
                    str(INSTALLATION_DIR / "generate_secrets.py"),
                    *SUBJECT_ARGS,
                    "--private-root",
                    str(root),
                    "--output-dir",
                    str(artifacts),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            external_files = self.create_external_files(root)
            external_files[1].write_text("not-a-certificate", encoding="utf-8")
            kubeconfig = root / "kubeconfig"
            kubeconfig.write_text("test-kubeconfig", encoding="utf-8")
            kubeconfig.chmod(0o600)
            result = subprocess.run(
                [
                    "sh",
                    str(INSTALLATION_DIR / "apply_secrets.sh"),
                    "--artifact-dir",
                    str(artifacts),
                    "--private-root",
                    str(root),
                    "--context",
                    "homelab-contract",
                    "--kubeconfig",
                    str(kubeconfig),
                    "--namespace",
                    "aileron-identity-system",
                    "--expected-namespace-uid",
                    NAMESPACE_UID,
                    "--image-pull-secret-file",
                    str(external_files[0]),
                    "--tls-cert-file",
                    str(external_files[1]),
                    "--tls-key-file",
                    str(external_files[2]),
                    "--values",
                    str(external_files[3]),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("TLS certificate is invalid", result.stderr)

    def test_forbidden_secret_lookup_fails_closed(self) -> None:
        source = (INSTALLATION_DIR / "apply_secrets.sh").read_text(encoding="utf-8")

        self.assertIn("Identity Secret ownership lookup failed", source)
        self.assertIn("Error from server \\(NotFound\\)", source)
        self.assertNotIn(
            "get secret \"${secret_name}\" \\\n+    -o 'jsonpath={.metadata.labels.platform\\.aileron\\.dev/secret-owner}' 2>/dev/null",
            source,
        )


if __name__ == "__main__":
    unittest.main()
