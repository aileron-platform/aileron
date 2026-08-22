import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml

REPOSITORY_ROOT = Path(os.environ.get("REPOSITORY_ROOT", "/repo"))
CONTRACT_PATH = REPOSITORY_ROOT / "contracts/platform-configuration/contract.json"
VECTORS_PATH = (
    REPOSITORY_ROOT / "contracts/platform-configuration/conformance-vectors.json"
)
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts/platform-configuration/validate.py"
HELM_CHART_PATH = REPOSITORY_ROOT / "helm/aileron"
IDENTITY_HELM_CHART_PATH = REPOSITORY_ROOT / "helm/aileron-identity"
DATA_SERVICE_PREFLIGHT_PATH = (
    REPOSITORY_ROOT / "contracts/platform-configuration/data-service-preflight.json"
)
DATA_SERVICE_PREFLIGHT_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "contracts/platform-configuration/data-service-preflight.schema.json"
)


def run_validator(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class ValidatorCliConformanceTest(unittest.TestCase):
    def _render_chart_with_values(
        self, chart_path: Path, values: dict[str, object]
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".yaml",
        ) as values_file:
            yaml.safe_dump(values, values_file)
            values_file.flush()
            return subprocess.run(
                [
                    "helm",
                    "template",
                    "data-service-schema-test",
                    str(chart_path),
                    "--namespace",
                    "workspace-system",
                    "--values",
                    values_file.name,
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_core_data_service_mode_schema_contract(self) -> None:
        external = {
            "postgres": {"enabled": False},
            "platformDatabase": {
                "revision": "platform-database-v1",
                "caSecretName": "platform-database-ca",
                "caSecretKey": "ca.crt",
            },
            "redis": {
                "enabled": False,
                "connections": {
                    name: {
                        "revision": f"{name.lower()}-redis-v1",
                        "urlSecretName": f"{name.lower()}-redis",
                        "urlSecretKey": "url",
                    }
                    for name in ("general", "jobQueue", "jobResult")
                },
            },
        }
        result = self._render_chart_with_values(HELM_CHART_PATH, external)
        self.assertEqual(0, result.returncode, result.stderr)
        documents = [
            document
            for document in yaml.safe_load_all(result.stdout)
            if isinstance(document, dict)
        ]

        def component(
            items: list[dict[str, object]],
            name: str,
            kind: str,
            hook: str | None = None,
        ) -> dict[str, object]:
            return next(
                document
                for document in items
                if document.get("kind") == kind
                and document.get("metadata", {}).get("name", "").endswith(f"-{name}")
                and (
                    hook is None
                    or document.get("metadata", {})
                    .get("annotations", {})
                    .get("helm.sh/hook")
                    == hook
                )
            )

        lifecycle_hook = "pre-install,pre-upgrade,pre-rollback"
        postgres_init = component(
            documents, "postgres-init", "ConfigMap", lifecycle_hook
        )
        preflight_script = component(
            documents, "data-service-preflight", "ConfigMap", lifecycle_hook
        )
        preflight_job = component(documents, "data-service-preflight", "Job")
        cleanup_hooks = [
            document
            for document in documents
            if document.get("kind") == "ConfigMap"
            and document.get("metadata", {})
            .get("labels", {})
            .get("app.kubernetes.io/component")
            == "data-service-hook-cleanup"
        ]
        postgres_bootstrap = component(documents, "postgres-bootstrap", "Job")
        admin_bootstrap = component(documents, "admin-bootstrap", "Job")
        workspace_manager = component(documents, "workspace-manager", "Deployment")
        self.assertEqual(
            "pre-install,pre-upgrade,pre-rollback",
            postgres_init["metadata"]["annotations"]["helm.sh/hook"],
        )
        for resource in (
            preflight_script,
            preflight_job,
            postgres_bootstrap,
            admin_bootstrap,
        ):
            self.assertEqual(
                "pre-install,pre-upgrade,pre-rollback",
                resource["metadata"]["annotations"]["helm.sh/hook"],
            )
        self.assertEqual(
            {
                preflight_script["metadata"]["name"],
                postgres_init["metadata"]["name"],
            },
            {
                resource["metadata"]["name"]
                for resource in cleanup_hooks
            },
        )
        for resource in cleanup_hooks:
            annotations = resource["metadata"]["annotations"]
            self.assertEqual("post-delete", annotations["helm.sh/hook"])
            self.assertEqual(
                "before-hook-creation,hook-succeeded",
                annotations["helm.sh/hook-delete-policy"],
            )
        self.assertEqual(
            "-30",
            postgres_init["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            "-30",
            preflight_script["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            "-20",
            preflight_job["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            "-10",
            postgres_bootstrap["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            "0",
            admin_bootstrap["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertNotIn(
            "initContainers",
            workspace_manager["spec"]["template"]["spec"],
        )
        self.assertFalse(
            any(
                document.get("kind") == "StatefulSet"
                and document.get("metadata", {}).get("name", "").endswith("-postgres")
                for document in documents
            )
        )

        bundled = self._render_chart_with_values(HELM_CHART_PATH, {})
        self.assertEqual(0, bundled.returncode, bundled.stderr)
        bundled_documents = [
            document
            for document in yaml.safe_load_all(bundled.stdout)
            if isinstance(document, dict)
        ]
        bundled_postgres_bootstrap = component(
            bundled_documents, "postgres-bootstrap", "Job"
        )
        bundled_preflight = component(
            bundled_documents, "data-service-preflight", "Job"
        )
        bundled_admin_bootstrap = component(bundled_documents, "admin-bootstrap", "Job")
        bundled_workspace_manager = component(
            bundled_documents, "workspace-manager", "Deployment"
        )
        self.assertNotIn(
            "helm.sh/hook",
            bundled_postgres_bootstrap.get("metadata", {}).get("annotations", {}),
        )
        self.assertNotIn(
            "helm.sh/hook",
            bundled_preflight.get("metadata", {}).get("annotations", {}),
        )
        self.assertEqual(
            "wait-for-data-service-preflight",
            bundled_postgres_bootstrap["spec"]["template"]["spec"]["initContainers"][0][
                "name"
            ],
        )
        self.assertEqual(
            "wait-for-platform-schema",
            bundled_admin_bootstrap["spec"]["template"]["spec"]["initContainers"][0][
                "name"
            ],
        )
        self.assertEqual(
            ["wait-for-platform-schema", "wait-for-admin-bootstrap"],
            [
                container["name"]
                for container in bundled_workspace_manager["spec"]["template"]["spec"][
                    "initContainers"
                ]
            ],
        )

        missing_platform_database = {"postgres": {"enabled": False}}
        result = self._render_chart_with_values(
            HELM_CHART_PATH, missing_platform_database
        )
        self.assertNotEqual(0, result.returncode)

        missing_redis_connections = {"redis": {"enabled": False}}
        result = self._render_chart_with_values(
            HELM_CHART_PATH, missing_redis_connections
        )
        self.assertNotEqual(0, result.returncode)

        mixed_postgres_mode = {
            "postgres": {"enabled": True},
            "platformDatabase": {
                "revision": "platform-database-v1",
                "caSecretName": "platform-database-ca",
                "caSecretKey": "ca.crt",
            },
        }
        result = self._render_chart_with_values(HELM_CHART_PATH, mixed_postgres_mode)
        self.assertNotEqual(0, result.returncode)

        incomplete_ca_reference = {
            "postgres": {"enabled": False},
            "platformDatabase": {
                "revision": "platform-database-v1",
                "caSecretName": "platform-database-ca",
            },
        }
        result = self._render_chart_with_values(
            HELM_CHART_PATH, incomplete_ca_reference
        )
        self.assertNotEqual(0, result.returncode)

    def test_identity_data_service_mode_schema_contract(self) -> None:
        external = {
            "postgres": {
                "enabled": False,
                "jdbcUrl": (
                    "jdbc:postgresql://identity-postgres.example.test:5432/identity"
                    "?sslmode=verify-full"
                ),
                "caSecretName": "identity-database-ca",
                "caSecretKey": "ca.crt",
                "revision": "identity-database-v1",
            },
            "networkPolicy": {"externalDatabaseEgress": {"mode": "disabled"}},
        }
        result = self._render_chart_with_values(IDENTITY_HELM_CHART_PATH, external)
        self.assertEqual(0, result.returncode, result.stderr)
        documents = [
            document
            for document in yaml.safe_load_all(result.stdout)
            if isinstance(document, dict)
        ]
        preflight_config = next(
            document
            for document in documents
            if document.get("kind") == "ConfigMap"
            and document.get("metadata", {})
            .get("name", "")
            .endswith("-data-service-preflight")
            and document.get("metadata", {})
            .get("annotations", {})
            .get("helm.sh/hook")
            == "pre-install,pre-upgrade,pre-rollback"
        )
        preflight_job = next(
            document
            for document in documents
            if document.get("kind") == "Job"
            and document.get("metadata", {})
            .get("name", "")
            .endswith("-data-service-preflight")
        )
        self.assertEqual(
            "-30",
            preflight_config["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            "-20",
            preflight_job["metadata"]["annotations"]["helm.sh/hook-weight"],
        )
        self.assertEqual(
            {
                "runAsNonRoot": True,
                "runAsUser": 70,
                "runAsGroup": 70,
                "fsGroup": 70,
                "fsGroupChangePolicy": "OnRootMismatch",
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            preflight_job["spec"]["template"]["spec"]["securityContext"],
        )
        preflight_container = preflight_job["spec"]["template"]["spec"]["containers"][0]
        self.assertFalse(
            any(
                environment["name"] in {"PGUSER", "PGPASSWORD"}
                for environment in preflight_container["env"]
            )
        )

        for invalid in (
            {"postgres": {"enabled": False}},
            {
                "postgres": {
                    "enabled": False,
                    "jdbcUrl": "jdbc:postgresql://identity.example.test/identity",
                }
            },
            {
                "postgres": {
                    "enabled": False,
                    "jdbcUrl": (
                        "jdbc:postgresql://user:password@identity.example.test/identity"
                    ),
                },
                "networkPolicy": {"externalDatabaseEgress": {"mode": "disabled"}},
            },
            {
                "postgres": {
                    "enabled": False,
                    "jdbcUrl": (
                        "jdbc:postgresql://identity.example.test/identity?password=x"
                    ),
                },
                "networkPolicy": {"externalDatabaseEgress": {"mode": "disabled"}},
            },
            {
                "postgres": {
                    "enabled": True,
                    "jdbcUrl": "jdbc:postgresql://identity.example.test/identity",
                }
            },
        ):
            result = self._render_chart_with_values(IDENTITY_HELM_CHART_PATH, invalid)
            self.assertNotEqual(0, result.returncode, invalid)

    def test_data_service_preflight_contract_matches_schema(self) -> None:
        contract = json.loads(DATA_SERVICE_PREFLIGHT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(
            DATA_SERVICE_PREFLIGHT_SCHEMA_PATH.read_text(encoding="utf-8")
        )

        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(contract)

    def test_data_service_preflight_dag_has_distinct_mode_ordering(self) -> None:
        contract = json.loads(DATA_SERVICE_PREFLIGHT_PATH.read_text(encoding="utf-8"))
        external = contract["preflightDag"]["external"]
        bundled = contract["preflightDag"]["bundled"]

        self.assertEqual("postgres.enabled=false", external["modeSelector"])
        external_by_name = {
            resource["name"]: resource for resource in external["resources"]
        }
        self.assertEqual(
            (-30, -20, -10, 0),
            tuple(
                external_by_name[name]["weight"]
                for name in (
                    "preflight-script-configmap",
                    "external-data-service-preflight",
                    "schema-bootstrap",
                    "admin-bootstrap",
                )
            ),
        )
        self.assertIn(
            "must itself be a hook",
            external_by_name["preflight-script-configmap"]["visibility"],
        )
        self.assertEqual("postgres.enabled=true", bundled["modeSelector"])
        self.assertTrue(
            all(resource["weight"] is None for resource in bundled["resources"])
        )
        self.assertIn("init gates", bundled["workloadGate"])

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
                "key: {{ .Values.connectivityEvidenceGateway.auth.agentTokensJsonKey }}"
            )
            replacement = (
                "key: {{ .Values.connectivityEvidenceGateway.auth.internalTokenKey }}"
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
            ("platformDatabase.caSecretName", "platformDatabase.caSecretKey"),
            references["platformDatabaseCa"],
        )
        self.assertEqual(
            (
                "redis.connections.general.urlSecretName",
                "redis.connections.general.urlSecretKey",
            ),
            references["generalRedisUrl"],
        )
        self.assertEqual(
            (
                "redis.connections.jobQueue.urlSecretName",
                "redis.connections.jobQueue.urlSecretKey",
            ),
            references["jobQueueRedisUrl"],
        )
        self.assertEqual(
            (
                "redis.connections.jobResult.urlSecretName",
                "redis.connections.jobResult.urlSecretKey",
            ),
            references["jobResultRedisUrl"],
        )
        contract_items = {
            item["logicalName"]: item for item in contract["helmSecretReferences"]
        }
        self.assertEqual(
            ["bundledPostgres"], contract_items["postgresUsername"]["requiredModes"]
        )
        self.assertEqual(
            ["bundledPostgres"], contract_items["postgresPassword"]["requiredModes"]
        )
        self.assertEqual(
            ["externalRedis"], contract_items["generalRedisUrl"]["requiredModes"]
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
        self.assertEqual(
            (
                "coturn.auth.existingSecretName",
                "coturn.auth.restSharedSecretKey",
            ),
            references["coturnRestSharedSecret"],
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

    def test_compose_data_service_adapters_are_explicit_and_convergent(self) -> None:
        def render(*files: str) -> dict[str, object]:
            command = [
                "docker",
                "compose",
                "--env-file",
                ".env.example",
            ]
            for file_name in files:
                command.extend(("--file", file_name))
            command.extend(("config", "--format", "json"))
            result = subprocess.run(
                command,
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)

        external = render("docker-compose.yml")
        external_services = external["services"]
        self.assertNotIn("postgres", external_services)
        self.assertNotIn("redis", external_services)
        for service in external_services.values():
            dependencies = service.get("depends_on", {})
            self.assertNotIn("postgres", dependencies)
            self.assertNotIn("redis", dependencies)
        manager_environment = external_services["workspace-manager"]["environment"]
        self.assertEqual(
            "/run/secrets/platform-database-url",
            manager_environment["DATABASE_URL_FILE"],
        )
        self.assertEqual(
            "/run/secrets/redis-general-url",
            manager_environment["REDIS_URL_FILE"],
        )
        self.assertEqual(
            {
                "data-service-preflight": {
                    "condition": "service_completed_successfully",
                    "required": True,
                }
            },
            external_services["platform-schema-bootstrap"]["depends_on"],
        )

        bundled = render(
            "docker-compose.yml", "docker-compose.bundled-data-services.yml"
        )
        bundled_services = bundled["services"]
        self.assertIn("postgres", bundled_services)
        self.assertIn("redis", bundled_services)
        self.assertEqual(
            {"postgres", "redis"},
            set(bundled_services["data-service-preflight"]["depends_on"]),
        )
        self.assertIn(
            "/docker-entrypoint-initdb.d/001_platform_login.sh",
            {volume["target"] for volume in bundled_services["postgres"]["volumes"]},
        )
        self.assertEqual(
            ["/opt/aileron/postgres-secret-entrypoint.sh"],
            bundled_services["postgres"]["entrypoint"],
        )
        self.assertEqual(["postgres"], bundled_services["postgres"]["command"])
        self.assertIn(
            "/opt/aileron/postgres-secret-entrypoint.sh",
            {volume["target"] for volume in bundled_services["postgres"]["volumes"]},
        )

        tls = render("docker-compose.yml", "docker-compose.data-service-tls.yml")
        tls_services = tls["services"]
        self.assertEqual(
            "/etc/aileron/data-service-ca/redis-general/ca.crt",
            tls_services["workspace-manager"]["environment"]["REDIS_CA_CERT_FILE"],
        )
        for service_name in (
            "data-service-preflight",
            "platform-schema-bootstrap",
            "identity-bootstrap",
            "workspace-manager",
        ):
            self.assertIn(
                "/etc/aileron/data-service-ca/platform-database/ca.crt",
                {volume["target"] for volume in tls_services[service_name]["volumes"]},
            )

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
