#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(os.environ.get("REPOSITORY_ROOT", "/repo"))
CONTRACT_PATH = REPOSITORY_ROOT / "contracts/platform-configuration/contract.json"
VECTORS_PATH = REPOSITORY_ROOT / "contracts/platform-configuration/conformance-vectors.json"
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts/platform-configuration/validate.py"
HELM_CHART_PATH = REPOSITORY_ROOT / "helm/aileron"


def run_validator(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class ValidatorCliConformanceTest(unittest.TestCase):
    def test_repository_accepts_secret_directory_option_name(self) -> None:
        result = run_validator("validate-repository", "--skip-compose-config")

        self.assertEqual(0, result.returncode, result.stderr)

    def test_container_uses_pinned_helm_version(self) -> None:
        result = subprocess.run(
            ["helm", "version", "--short"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.startswith("v3.18.4"), result.stdout)

    def test_actual_helm_render_rejects_unknown_environment_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = Path(temporary_directory) / "aileron"
            shutil.copytree(HELM_CHART_PATH, chart_path)
            template_path = chart_path / "templates/connectivity-evidence-gateway.yaml"
            template = template_path.read_text(encoding="utf-8")
            expected = "CONNECTIVITY_AGENT_TOKENS_FILE"
            replacement = "CONNECTIVITY_AGENT_TOKENS_JSON_FILE"
            self.assertEqual(1, template.count(expected))
            template_path.write_text(
                template.replace(expected, replacement),
                encoding="utf-8",
            )

            result = run_validator(
                "validate-helm-adapter",
                "--chart-path",
                str(chart_path),
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(
            "unknown Helm output: Deployment.connectivity-evidence-gateway.gateway.environment.CONNECTIVITY_AGENT_TOKENS_JSON_FILE",
            result.stderr,
        )
        self.assertIn(
            "missing classified Helm output: Deployment.connectivity-evidence-gateway.gateway.environment.CONNECTIVITY_AGENT_TOKENS_FILE",
            result.stderr,
        )

    def test_actual_helm_render_rejects_secret_key_environment_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = Path(temporary_directory) / "aileron"
            shutil.copytree(HELM_CHART_PATH, chart_path)
            template_path = chart_path / "templates/workspace-manager-deployment.yaml"
            template = template_path.read_text(encoding="utf-8")
            expected = """            - name: OIDC_CLIENT_SECRET_FILE
              value: /run/secrets/aileron/oidc-client-secret"""
            replacement = """            - name: OIDC_CLIENT_SECRET_FILE
              valueFrom:
                secretKeyRef:
                  name: aileron-oidc-client
                  key: client-secret"""
            self.assertEqual(1, template.count(expected))
            template_path.write_text(
                template.replace(expected, replacement),
                encoding="utf-8",
            )

            result = run_validator(
                "validate-helm-adapter",
                "--chart-path",
                str(chart_path),
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("Helm plaintext Secret environment source:", result.stderr)
        self.assertIn("OIDC_CLIENT_SECRET_FILE", result.stderr)

    def test_actual_helm_render_rejects_secret_process_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = Path(temporary_directory) / "aileron"
            shutil.copytree(HELM_CHART_PATH, chart_path)
            template_path = chart_path / "templates/secret-process-argument-test.yaml"
            template_path.write_text(
                """apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: platform-config-validator-secret-argument
spec:
  selector:
    matchLabels:
      app: secret-argument
  template:
    metadata:
      labels:
        app: secret-argument
    spec:
      containers:
        - name: coturn
          image: example.invalid/coturn:test
          args:
            - --static-auth-secret=forbidden-test-value
""",
                encoding="utf-8",
            )

            result = run_validator(
                "validate-helm-adapter",
                "--chart-path",
                str(chart_path),
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(
            "plaintext Secret process argument: "
            "DaemonSet/platform-config-validator-secret-argument.coturn."
            "STATIC_AUTH_SECRET",
            result.stderr,
        )

    def test_actual_helm_render_rejects_wrong_secret_volume_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = Path(temporary_directory) / "aileron"
            shutil.copytree(HELM_CHART_PATH, chart_path)
            template_path = chart_path / "templates/connectivity-evidence-gateway.yaml"
            template = template_path.read_text(encoding="utf-8")
            expected = (
                "key: {{ .Values.connectivityEvidenceGateway.auth."
                "agentTokensJsonKey }}"
            )
            replacement = (
                "key: {{ .Values.connectivityEvidenceGateway.auth."
                "internalTokenKey }}"
            )
            self.assertEqual(1, template.count(expected))
            template_path.write_text(
                template.replace(expected, replacement),
                encoding="utf-8",
            )

            result = run_validator(
                "validate-helm-adapter",
                "--chart-path",
                str(chart_path),
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(
            "invalid Helm Secret source: "
            "-connectivity-evidence-gateway.gateway."
            "/run/secrets/aileron-connectivity/agent-tokens.json",
            result.stderr,
        )

    def test_actual_helm_render_rejects_dead_platform_config_map_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            chart_path = Path(temporary_directory) / "aileron"
            shutil.copytree(HELM_CHART_PATH, chart_path)
            template_path = chart_path / "templates/platform-configmap.yaml"
            template = template_path.read_text(encoding="utf-8")
            template_path.write_text(
                template
                + '\n  PUBLIC_RUNTIME_PATH_PATTERN: "/workspaces/{workspaceId}/runtime"\n',
                encoding="utf-8",
            )

            result = run_validator(
                "validate-helm-adapter",
                "--chart-path",
                str(chart_path),
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(
            "unknown Helm platform ConfigMap output: PUBLIC_RUNTIME_PATH_PATTERN",
            result.stderr,
        )

    def test_contract_models_helm_secret_name_and_key_references(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

        references = {
            item["logicalName"]: (
                item["mapping"]["secretNameValuesPath"],
                item["mapping"]["secretKeyValuesPath"],
            )
            for item in contract["helmSecretReferences"]
        }

        self.assertEqual(
            (
                "platformSecrets.existingSecretName",
                "platformSecrets.databaseUrlKey",
            ),
            references["platformDatabaseUrl"],
        )
        self.assertEqual(
            ("oidc.clientSecretName", "oidc.clientSecretKey"),
            references["oidcClientSecret"],
        )
        self.assertEqual(
            (
                "runtimeAssertions.privateKeySecretName",
                "runtimeAssertions.privateKeySecretKey",
            ),
            references["runtimeAssertionPrivateKey"],
        )

    def test_compose_and_helm_derive_identical_public_paths(self) -> None:
        workspace_id = "e0e4aba0-8442-4851-a9c4-5c45f9e74fb6"
        result = run_validator(
            "validate-parity",
            "--origin",
            "https://platform.example.test:8443",
            "--workspace-id",
            workspace_id,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        normalized = json.loads(result.stdout)
        expected = {
            "oidcCallbackUrl": (
                "https://platform.example.test:8443/api/v1/oauth2/callback"
            ),
            "platformPublicOrigin": "https://platform.example.test:8443",
            "workspaceBrowserPath": f"/workspaces/{workspace_id}/browser",
            "workspaceCanvasPath": f"/workspaces/{workspace_id}/canvas",
            "workspaceRuntimePath": f"/workspaces/{workspace_id}/runtime",
        }
        self.assertEqual(expected, normalized["compose"])
        self.assertEqual(expected, normalized["helm"])

    def test_conformance_vectors_through_cli(self) -> None:
        vectors = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]

        for vector in vectors:
            with self.subTest(vector=vector["id"]):
                result = run_validator("validate-vector", "--vector", vector["id"])
                expected_code = 0 if vector["valid"] else 1
                self.assertEqual(expected_code, result.returncode, result.stderr)
                if not vector["valid"]:
                    self.assertIn(vector["diagnostic"], result.stderr)

    def test_repository_contract_and_compose_config_through_cli(self) -> None:
        result = run_validator("validate-repository")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_product_secret_fixture_is_rejected_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_path = (
                Path(temporary_directory)
                / "workspace-operator/tests/fixtures/turn-integration-shared-secret"
            )
            fixture_path.parent.mkdir(parents=True)
            fixture_path.write_text("forbidden-secret-material\n", encoding="utf-8")

            result = run_validator(
                "validate-product-secret-fixtures",
                "--root",
                temporary_directory,
            )

        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn(
            "persistent product Secret fixture: "
            "workspace-operator/tests/fixtures/turn-integration-shared-secret",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
