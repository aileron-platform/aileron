"""Rendered shell-manifest contracts for the formal product stack."""

from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

PRODUCT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]


class InstallProductStackTest(unittest.TestCase):
    def test_installation_transaction_does_not_mutate_assertion_key_identity(
        self,
    ) -> None:
        source = (PRODUCT_DIR / "verify-installation-transaction.sh").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("runtimeAssertions.activeKid", source)
        self.assertIn(".metadata.uid != $previous", source)
        self.assertIn('.type == "Ready" and .status == "True"', source)
        self.assertIn('run_transaction_driver "prepare-transaction-workspace"', source)
        self.assertIn('run_transaction_driver "cleanup-transaction-workspace"', source)
        self.assertLess(
            source.index('run_transaction_driver "prepare-transaction-workspace"'),
            source.index("runtime_deployment="),
        )
        self.assertLess(
            source.index('run_transaction_driver "cleanup-transaction-workspace"'),
            source.index('helm rollback "${release}"'),
        )

        hook = (PRODUCT_DIR / "product-conformance-hook.sh").read_text(
            encoding="utf-8"
        )
        run_position = hook.index('"${script_dir}/run-product-conformance.sh"')
        delete_position = hook.index("delete job product-conformance")
        transaction_position = hook.index("verify-installation-transaction.sh")
        self.assertLess(run_position, delete_position)
        self.assertLess(delete_position, transaction_position)

        k3s_runner = (
            REPO_ROOT / "scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
        ).read_text(encoding="utf-8")
        self.assertLess(
            k3s_runner.rfind("\ndelete_workspace_and_assert_absence\n"),
            k3s_runner.rfind("\nassert_product_hook\n"),
        )

    def test_k3s_operator_and_product_driver_share_the_platform_origin(self) -> None:
        expected = "https://aileron.example.test"
        k3s_runner = (
            REPO_ROOT / "scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
        ).read_text(encoding="utf-8")
        product_runner = (PRODUCT_DIR / "run-product-conformance.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn(f"value: {expected}", k3s_runner)
        self.assertIn(f"value: {expected}", product_runner)

    def test_product_driver_uses_the_installed_platform_database_secret(self) -> None:
        product_runner = (PRODUCT_DIR / "run-product-conformance.sh").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("postgresql://postgres:postgres@", product_runner)
        self.assertEqual(product_runner.count("name: aileron-platform-secrets"), 1)
        self.assertEqual(product_runner.count("key: database-url"), 1)

    def test_external_tls_uses_short_cn_and_complete_service_san(self) -> None:
        source = (PRODUCT_DIR / "install-product-stack.sh").read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count("openssl req -config /dev/null"), 2)
        self.assertIn("basicConstraints=critical,CA:TRUE", source)
        self.assertIn("basicConstraints=critical,CA:FALSE", source)
        self.assertIn('-subj "/CN=external-${service}"', source)
        self.assertIn("subjectAltName=DNS:%s", source)
        self.assertNotIn('-subj "/CN=${service_host}"', source)

    def _render(
        self,
        storage_mode: str,
        *,
        mount_options: str = "vers=4.1\nhard\ntimeo=321\nretrans=7",
        runtime_image: str | None = None,
        redis_image: str = "registry.example/platform-redis:test",
        postgres_image: str = "registry.example/platform-postgres:test",
        include_rwo_storage_class: bool = True,
        runtime_home_storage_class: str | None = None,
        runtime_home_access_mode: str | None = None,
        runtime_home_provisioner: str = "kubernetes.io/no-provisioner",
        runtime_home_binding_mode: str = "Immediate",
        runtime_home_reclaim_policy: str = "Retain",
        data_service_mode: str = "bundled",
        expected_returncode: int = 0,
    ) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bin_dir = root / "bin"
            capture_dir = root / "capture"
            bin_dir.mkdir()
            capture_dir.mkdir()
            kubectl = bin_dir / "kubectl"
            kubectl.write_text(
                textwrap.dedent("""\
                    #!/bin/sh
                    set -eu
                    case "$1" in
                      apply)
                        source_file=""
                        previous=""
                        for argument in "$@"; do
                          if [ "$previous" = "-f" ]; then source_file="$argument"; fi
                          previous="$argument"
                        done
                        case "$source_file" in
                          *harness-rbac.yaml) cp "$source_file" "$CAPTURE_DIR/rbac.yaml" ;;
                          *product-storage.yaml) cp "$source_file" "$CAPTURE_DIR/storage.yaml" ;;
                          *storage-preparer.yaml) cp "$source_file" "$CAPTURE_DIR/storage-preparer.yaml" ;;
                          *runtime-home-preparer.yaml) cp "$source_file" "$CAPTURE_DIR/runtime-home-preparer.yaml" ;;
                          *keygen-job.yaml) cp "$source_file" "$CAPTURE_DIR/keygen-job.yaml" ;;
                          *external-oidc-fixture.yaml) cp "$source_file" "$CAPTURE_DIR/oidc-fixture.yaml" ;;
                          *external-data-services.yaml) cp "$source_file" "$CAPTURE_DIR/external-data-services.yaml" ;;
                          *platform-data-service-secrets.yaml) cp "$source_file" "$CAPTURE_DIR/platform-data-service-secrets.yaml" ;;
                        esac
                        ;;
                      create)
                        printf '%s\n' "$*" > "$CAPTURE_DIR/kubectl-create.txt"
                        for argument in "$@"; do
                          case "$argument" in
                            --from-file=client-secret=*)
                              secret_file="${argument#--from-file=client-secret=}"
                              stat -c '%a' "$secret_file" > "$CAPTURE_DIR/client-secret-mode.txt"
                              wc -c < "$secret_file" | tr -d ' ' > "$CAPTURE_DIR/client-secret-length.txt"
                              ;;
                          esac
                        done
                        ;;
                      get)
                        printf '%s\n' "$*" >> "$CAPTURE_DIR/kubectl-get.txt"
                        case "$*" in
                          *'get job product-assertion-keygen'*'Complete'*)
                            printf '%s' True
                            ;;
                          *'get pvc knowledge-bases-pvc'*'status.phase'*)
                            printf '%s' Bound
                            ;;
                          *'get pvc knowledge-bases-pvc'*'spec.volumeName'*)
                            printf '%s' source-knowledge-bases-pv
                            ;;
                          *'get pv source-knowledge-bases-pv'*'spec.nfs.server'*)
                            printf '%s' nfs-server
                            ;;
                          *'get pv source-knowledge-bases-pv'*'spec.mountOptions'*)
                            printf '%s\n' "$SOURCE_MOUNT_OPTIONS"
                            ;;
                          *'get storageclass '*'jsonpath={.provisioner}'*)
                            printf '%s' "$RUNTIME_HOME_PROVISIONER"
                            ;;
                          *'get storageclass '*'jsonpath={.volumeBindingMode}'*)
                            printf '%s' "$RUNTIME_HOME_BINDING_MODE"
                            ;;
                          *'get storageclass '*'jsonpath={.reclaimPolicy}'*)
                            printf '%s' "$RUNTIME_HOME_RECLAIM_POLICY"
                            ;;
                          *'app.kubernetes.io/component=workspace-manager'*)
                            printf '%s' product-manager-pod
                            ;;
                        esac
                        ;;
                      set)
                        printf '%s\n' "$*" > "$CAPTURE_DIR/operator-set-env.txt"
                        ;;
                      exec)
                        printf '%s\n' \
                          'fastapi RUNNING pid 1, uptime 0:00:10' \
                          'celery-worker RUNNING pid 2, uptime 0:00:10' \
                          'celery-beat RUNNING pid 3, uptime 0:00:10'
                        ;;
                    esac
                    """),
                encoding="utf-8",
            )
            kubectl.chmod(0o755)
            helm = bin_dir / "helm"
            helm.write_text(
                '#!/bin/sh\nprintf \'%s\\n\' "$*" > "$CAPTURE_DIR/helm.txt"\n',
                encoding="utf-8",
            )
            helm.chmod(0o755)
            manager_digest = "a" * 64
            runtime_digest = "b" * 64
            browser_digest = "c" * 64
            canvas_digest = "d" * 64
            environment = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "CAPTURE_DIR": str(capture_dir),
                "SOURCE_MOUNT_OPTIONS": mount_options,
                "RUNTIME_HOME_PROVISIONER": runtime_home_provisioner,
                "RUNTIME_HOME_BINDING_MODE": runtime_home_binding_mode,
                "RUNTIME_HOME_RECLAIM_POLICY": runtime_home_reclaim_policy,
                "REPO_ROOT": "/repo",
                "E2E_NAMESPACE": "workspace-e2e-run-1",
                "E2E_RUN_ID": "run-1",
                "E2E_STORAGE_MODE": storage_mode,
                "RWX_STORAGE_CLASS": "nfs-rwx-run-1",
                "RWO_STORAGE_CLASS": (
                    "nfs-rwx-run-1"
                    if storage_mode == "static-nfs"
                    else "local-rwo-run-1"
                ),
                "E2E_SHARED_STORAGE_SIZE": "10Gi",
                "E2E_RWO_STORAGE_SIZE": "20Gi",
                "E2E_RUNTIME_HOME_STORAGE_SIZE": "30Gi",
                "PRODUCT_DRIVER_IMAGE": "driver:test",
                "MANAGER_IMAGE": f"registry.example/manager@sha256:{manager_digest}",
                "RUNTIME_IMAGE": runtime_image
                or f"registry.example/runtime@sha256:{runtime_digest}",
                "BROWSER_IMAGE": f"registry.example/browser@sha256:{browser_digest}",
                "CANVAS_IMAGE": f"registry.example/canvas@sha256:{canvas_digest}",
                "REDIS_IMAGE": redis_image,
                "POSTGRES_IMAGE": postgres_image,
                "IMAGE_PULL_SECRET_NAME": "harbor-pull",
                "PRODUCT_DATA_SERVICE_MODE": data_service_mode,
            }
            if storage_mode == "static-nfs":
                environment["NFS_SERVER"] = "nfs-server"
            if runtime_home_storage_class is not None:
                environment["RUNTIME_HOME_STORAGE_CLASS"] = runtime_home_storage_class
            if runtime_home_access_mode is not None:
                environment["RUNTIME_HOME_STORAGE_ACCESS_MODE"] = (
                    runtime_home_access_mode
                )
            if not include_rwo_storage_class:
                environment.pop("RWO_STORAGE_CLASS")
            completed = subprocess.run(
                [str(PRODUCT_DIR / "install-product-stack.sh")],
                check=False,
                capture_output=True,
                env=environment,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                expected_returncode,
                msg=f"stdout={completed.stdout}\nstderr={completed.stderr}",
            )
            if expected_returncode != 0:
                return {
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            storage_path = capture_dir / "storage.yaml"
            return {
                "rbac": (capture_dir / "rbac.yaml").read_text(encoding="utf-8"),
                "storage": (
                    storage_path.read_text(encoding="utf-8")
                    if storage_path.exists()
                    else ""
                ),
                "storage_preparer": (
                    (capture_dir / "storage-preparer.yaml").read_text(encoding="utf-8")
                    if (capture_dir / "storage-preparer.yaml").exists()
                    else ""
                ),
                "runtime_home_preparer": (
                    (capture_dir / "runtime-home-preparer.yaml").read_text(
                        encoding="utf-8"
                    )
                    if (capture_dir / "runtime-home-preparer.yaml").exists()
                    else ""
                ),
                "keygen_job": (capture_dir / "keygen-job.yaml").read_text(
                    encoding="utf-8"
                ),
                "oidc_fixture": (capture_dir / "oidc-fixture.yaml").read_text(
                    encoding="utf-8"
                ),
                "external_data_services": (
                    (capture_dir / "external-data-services.yaml").read_text(
                        encoding="utf-8"
                    )
                    if (capture_dir / "external-data-services.yaml").exists()
                    else ""
                ),
                "platform_data_service_secrets": (
                    (capture_dir / "platform-data-service-secrets.yaml").read_text(
                        encoding="utf-8"
                    )
                ),
                "operator_env": (capture_dir / "operator-set-env.txt").read_text(
                    encoding="utf-8"
                ),
                "helm": (capture_dir / "helm.txt").read_text(encoding="utf-8"),
                "kubectl_get": (capture_dir / "kubectl-get.txt").read_text(
                    encoding="utf-8"
                ),
                "kubectl_create": (capture_dir / "kubectl-create.txt").read_text(
                    encoding="utf-8"
                ),
                "client_secret_mode": (
                    capture_dir / "client-secret-mode.txt"
                ).read_text(encoding="utf-8"),
                "client_secret_length": int(
                    (capture_dir / "client-secret-length.txt").read_text(
                        encoding="utf-8"
                    )
                ),
                "manager_digest": manager_digest,
                "runtime_digest": runtime_digest,
                "browser_digest": browser_digest,
                "canvas_digest": canvas_digest,
            }

    def test_static_nfs_renders_mount_contract_and_operator_rewire(self) -> None:
        rendered = self._render("static-nfs")

        rbac = rendered["rbac"]
        role, cluster_role = rbac.split("kind: ClusterRole", maxsplit=1)
        self.assertNotIn('resources: ["namespaces"]', role)
        self.assertIn(
            'resources: ["serviceaccounts"]\n' '    verbs: ["get", "list", "watch"]',
            role,
        )
        self.assertIn('resources: ["deployments/scale"]', role)
        self.assertIn('verbs: ["get", "update", "patch"]', role)
        self.assertIn('resources: ["pods/exec"]', role)
        self.assertIn('verbs: ["get", "create"]', role)
        role_document = next(
            resource
            for resource in yaml.safe_load_all(rbac)
            if resource["kind"] == "Role"
        )
        self.assertEqual(
            [
                rule
                for rule in role_document["rules"]
                if rule["apiGroups"] == ["discovery.k8s.io"]
            ],
            [
                {
                    "apiGroups": ["discovery.k8s.io"],
                    "resources": ["endpointslices"],
                    "verbs": ["list"],
                }
            ],
        )
        self.assertFalse(
            any(
                "endpoints" in rule["resources"]
                for rule in role_document["rules"]
                if rule["apiGroups"] == [""]
            )
        )
        self.assertIn('resources: ["namespaces"]', cluster_role)
        self.assertIn('verbs: ["get"]', cluster_role)
        self.assertEqual(
            rbac.count("aileron.io/product-conformance-run: run-1"),
            2,
        )
        self.assertIn("imagePullSecrets:\n  - name: harbor-pull", rbac)
        self.assertIn(
            "imagePullSecrets:\n    - name: harbor-pull",
            rendered["storage_preparer"],
        )
        self.assertIn(
            "imagePullSecrets:\n        - name: harbor-pull",
            rendered["keygen_job"],
        )

        storage = rendered["storage"]
        self.assertEqual(
            storage.count("aileron.io/product-conformance-run: run-1"),
            7,
        )
        self.assertNotIn("kind: StorageClass", storage)
        self.assertEqual(storage.count("kind: PersistentVolume\n"), 7)
        self.assertEqual(storage.count("  nfs:\n"), 7)
        self.assertEqual(storage.count("  mountOptions:\n"), 7)
        for expected in (
            '    - "vers=4.1"\n',
            '    - "hard"\n',
            '    - "timeo=321"\n',
            '    - "retrans=7"\n',
        ):
            self.assertEqual(storage.count(expected), 7)
        self.assertNotIn("vers=4.2", storage)
        self.assertIn("name: product-runtime-homes-root-pvc", storage)
        self.assertIn("path: /runtime-homes", storage)
        self.assertIn("name: product-runtime-home-run-1", storage)
        self.assertIn("path: /runtime-homes/product-run-1", storage)
        runtime_home_pv = next(
            resource
            for resource in yaml.safe_load_all(storage)
            if resource["metadata"]["name"] == "product-runtime-home-run-1"
        )
        self.assertNotIn("claimRef", runtime_home_pv["spec"])
        self.assertEqual(
            runtime_home_pv["spec"]["storageClassName"],
            "nfs-rwx-run-1",
        )
        self.assertEqual(runtime_home_pv["spec"]["accessModes"], ["ReadWriteOnce"])
        self.assertEqual(runtime_home_pv["spec"]["capacity"]["storage"], "30Gi")
        runtime_home_preparer = rendered["runtime_home_preparer"]
        self.assertIn(
            "mkdir -p /runtime-homes/product-run-1",
            runtime_home_preparer,
        )
        self.assertIn(
            "claimName: product-runtime-homes-root-pvc",
            runtime_home_preparer,
        )
        self.assertIn("readOnlyRootFilesystem: true", runtime_home_preparer)
        self.assertIn(
            'jsonpath={range .spec.mountOptions[*]}{@}{"\\n"}{end}',
            rendered["kubectl_get"],
        )
        self.assertIn(
            "get storageclass nfs-rwx-run-1 -o " "jsonpath={.provisioner}",
            rendered["kubectl_get"],
        )
        self.assertIn(
            "get storageclass nfs-rwx-run-1 -o " "jsonpath={.volumeBindingMode}",
            rendered["kubectl_get"],
        )
        self.assertIn(
            "get storageclass nfs-rwx-run-1 -o " "jsonpath={.reclaimPolicy}",
            rendered["kubectl_get"],
        )

        for expected in (
            "AILERON_MANAGER_INTERNAL_URL=http://product-aileron-workspace-manager:3001",
            "KNOWLEDGE_BASES_PVC_NAME=product-knowledge-bases-pvc",
            "RUNTIME_HOME_STORAGE_CLASS_NAME=nfs-rwx-run-1",
            "RUNTIME_HOME_STORAGE_SIZE=30Gi",
            "RUNTIME_HOME_STORAGE_ACCESS_MODE=ReadWriteOnce",
        ):
            self.assertIn(expected, rendered["operator_env"])
        for forbidden in (
            "PLATFORM_MANAGER_URL",
            "PLATFORM_INTERNAL_API_TOKEN_SECRET_NAME",
            "PLATFORM_INTERNAL_API_TOKEN_SECRET_KEY",
            "PLATFORM_INTERNAL_API_TOKEN_REVISION",
            "PLATFORM_DATABASE_URL",
            "PLATFORM_REDIS_URL",
            "PLATFORM_OIDC_CLIENT_SECRET",
            "PLATFORM_OIDC_ISSUER_URL",
            "PLATFORM_OIDC_DISCOVERY_URL",
            "PLATFORM_OIDC_CLIENT_ID",
            "PLATFORM_OIDC_SCOPES",
        ):
            self.assertNotIn(forbidden, rendered["operator_env"])

        self.assertIn(
            "workspaceManager.image.repository=registry.example/manager",
            rendered["helm"],
        )
        self.assertIn(
            f"workspaceManager.image.digest=sha256:{rendered['manager_digest']}",
            rendered["helm"],
        )
        self.assertIn(
            "workspaceManager.image.tag=",
            rendered["helm"],
        )
        for values_path, repository, digest in (
            (
                "workspaceOperator.runtimeImage",
                "registry.example/runtime",
                rendered["runtime_digest"],
            ),
            (
                "kubernetes.browserImage",
                "registry.example/browser",
                rendered["browser_digest"],
            ),
            (
                "kubernetes.canvasImage",
                "registry.example/canvas",
                rendered["canvas_digest"],
            ),
        ):
            self.assertIn(
                f"{values_path}.repository={repository}",
                rendered["helm"],
            )
            self.assertIn(
                f"{values_path}.digest=sha256:{digest}",
                rendered["helm"],
            )
            self.assertIn(f"{values_path}.tag=", rendered["helm"])
        self.assertIn(
            "global.imagePullSecrets[0].name=harbor-pull",
            rendered["helm"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.storageClassName=nfs-rwx-run-1",
            rendered["helm"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.accessMode=ReadWriteOnce",
            rendered["helm"],
        )
        self.assertNotIn("global.storageClass=", rendered["helm"])
        for expected in (
            "kubernetes.managerState.storageClassName=nfs-rwx-run-1",
            "postgres.persistence.storageClassName=nfs-rwx-run-1",
            "redis.persistence.storageClassName=nfs-rwx-run-1",
        ):
            self.assertIn(expected, rendered["helm"])
        for expected in (
            "kubernetes.workspaceData.size=10Gi",
            "kubernetes.knowledgeBases.size=10Gi",
            "kubernetes.runtimeHome.size=30Gi",
            "kubernetes.managerState.size=20Gi",
            "postgres.persistence.size=20Gi",
            "redis.persistence.size=20Gi",
        ):
            self.assertIn(expected, rendered["helm"])
        for expected in (
            "redis.image.repository=registry.example/platform-redis",
            "redis.image.tag=test",
            "redis.image.pullPolicy=Never",
            "postgres.image.repository=registry.example/platform-postgres",
            "postgres.image.tag=test",
            "postgres.image.pullPolicy=Never",
            "oidc.issuerUrl=https://product-aileron-oidc-fixture:8443",
            "oidc.clientSecretName=external-oidc-client",
            "oidc.caSecretName=external-oidc-tls",
        ):
            self.assertIn(expected, rendered["helm"])
        self.assertIn('args: ["prepare-oidc-fixture-tls"]', rendered["keygen_job"])
        self.assertIn('args: ["serve-oidc-fixture"]', rendered["oidc_fixture"])
        self.assertIn("scheme: HTTPS", rendered["oidc_fixture"])
        self.assertIn("secretName: external-oidc-tls", rendered["oidc_fixture"])
        self.assertNotIn("kind: Secret", rendered["oidc_fixture"])
        self.assertNotIn("OIDC_FIXTURE_CLIENT_SECRET\n", rendered["oidc_fixture"])
        self.assertIn(
            "OIDC_FIXTURE_CLIENT_SECRET_FILE", rendered["oidc_fixture"]
        )
        self.assertIn("secretName: external-oidc-client", rendered["oidc_fixture"])
        self.assertIn("defaultMode: 0400", rendered["oidc_fixture"])
        self.assertIn("readOnly: true", rendered["oidc_fixture"])
        self.assertEqual(rendered["client_secret_mode"].strip(), "600")
        self.assertGreaterEqual(rendered["client_secret_length"], 43)
        self.assertIn(
            "create secret generic external-oidc-client",
            rendered["kubectl_create"],
        )
        self.assertIn(
            "--from-file=client-secret=", rendered["kubectl_create"]
        )
        self.assertNotIn("--from-literal", rendered["kubectl_create"])
        self.assertNotIn("keycloak", rendered["helm"].lower())

    def test_dynamic_storage_uses_csi_without_static_nfs_resources(self) -> None:
        rendered = self._render("dynamic")

        self.assertEqual(rendered["storage"], "")
        self.assertIn("kind: ClusterRole", rendered["rbac"])
        self.assertIn('resources: ["namespaces"]', rendered["rbac"])
        self.assertNotIn('resources: ["persistentvolumes"]', rendered["rbac"])
        self.assertNotIn("get pvc knowledge-bases-pvc", rendered["kubectl_get"])
        self.assertNotIn("get pv ", rendered["kubectl_get"])
        self.assertNotIn("jsonpath={.provisioner}", rendered["kubectl_get"])
        self.assertNotIn("jsonpath={.volumeBindingMode}", rendered["kubectl_get"])
        self.assertNotIn("jsonpath={.reclaimPolicy}", rendered["kubectl_get"])
        self.assertNotIn("global.storageClass=", rendered["helm"])
        self.assertIn(
            "kubernetes.workspaceData.storageClassName=nfs-rwx-run-1",
            rendered["helm"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.storageClassName=local-rwo-run-1",
            rendered["helm"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.accessMode=ReadWriteOnce",
            rendered["helm"],
        )
        for expected in (
            "kubernetes.managerState.storageClassName=local-rwo-run-1",
            "postgres.persistence.storageClassName=local-rwo-run-1",
            "redis.persistence.storageClassName=local-rwo-run-1",
        ):
            self.assertIn(expected, rendered["helm"])

    def test_dynamic_runtime_home_uses_explicit_class_and_access_mode(
        self,
    ) -> None:
        rendered = self._render(
            "dynamic",
            runtime_home_storage_class="runtime-home-rwx-run-1",
            runtime_home_access_mode="ReadWriteMany",
        )

        self.assertIn(
            "kubernetes.runtimeHome.storageClassName=runtime-home-rwx-run-1",
            rendered["helm"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.accessMode=ReadWriteMany",
            rendered["helm"],
        )
        self.assertIn(
            "RUNTIME_HOME_STORAGE_CLASS_NAME=runtime-home-rwx-run-1",
            rendered["operator_env"],
        )
        self.assertIn(
            "RUNTIME_HOME_STORAGE_ACCESS_MODE=ReadWriteMany",
            rendered["operator_env"],
        )
        self.assertIn(
            "get storageclass runtime-home-rwx-run-1",
            rendered["kubectl_get"],
        )

    def test_static_nfs_runtime_home_uses_explicit_access_mode(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_home_storage_class="nfs-rwx-run-1",
            runtime_home_access_mode="ReadWriteMany",
        )
        runtime_home_pv = next(
            resource
            for resource in yaml.safe_load_all(rendered["storage"])
            if resource["metadata"]["name"] == "product-runtime-home-run-1"
        )

        self.assertEqual(
            runtime_home_pv["spec"]["storageClassName"],
            "nfs-rwx-run-1",
        )
        self.assertEqual(
            runtime_home_pv["spec"]["accessModes"],
            ["ReadWriteMany"],
        )
        self.assertIn(
            "kubernetes.runtimeHome.accessMode=ReadWriteMany",
            rendered["helm"],
        )
        self.assertIn(
            "RUNTIME_HOME_STORAGE_ACCESS_MODE=ReadWriteMany",
            rendered["operator_env"],
        )

    def test_static_nfs_rejects_a_different_runtime_home_class(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_home_storage_class="different-static-class",
            expected_returncode=1,
        )

        self.assertIn(
            "static-nfs requires RUNTIME_HOME_STORAGE_CLASS to match "
            "RWX_STORAGE_CLASS",
            rendered["stderr"],
        )

    def test_static_nfs_rejects_a_dynamic_runtime_home_class(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_home_provisioner="nfs.csi.k8s.io",
            expected_returncode=1,
        )

        self.assertIn(
            "static-nfs Runtime HOME StorageClass must use "
            "kubernetes.io/no-provisioner",
            rendered["stderr"],
        )

    def test_static_nfs_rejects_delayed_runtime_home_binding(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_home_binding_mode="WaitForFirstConsumer",
            expected_returncode=1,
        )

        self.assertIn(
            "static-nfs Runtime HOME StorageClass must use Immediate binding",
            rendered["stderr"],
        )

    def test_static_nfs_rejects_disposable_runtime_home_storage(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_home_reclaim_policy="Delete",
            expected_returncode=1,
        )

        self.assertIn(
            "static-nfs Runtime HOME StorageClass must use Retain reclaim policy",
            rendered["stderr"],
        )

    def test_rejects_invalid_runtime_home_access_mode_before_rendering(
        self,
    ) -> None:
        rendered = self._render(
            "dynamic",
            runtime_home_access_mode="ReadOnlyMany",
            expected_returncode=1,
        )

        self.assertIn(
            "RUNTIME_HOME_STORAGE_ACCESS_MODE must be ReadWriteOnce or "
            "ReadWriteMany",
            rendered["stderr"],
        )

    def test_rejects_invalid_storage_mode_before_rendering(self) -> None:
        rendered = self._render(
            "external",
            expected_returncode=1,
        )

        self.assertIn(
            "E2E_STORAGE_MODE must be static-nfs or dynamic",
            rendered["stderr"],
        )

    def test_product_hook_forwards_runtime_home_storage_contract(self) -> None:
        hook = (PRODUCT_DIR / "product-conformance-hook.sh").read_text(encoding="utf-8")

        self.assertIn(
            'runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-',
            hook,
        )
        self.assertIn(
            'runtime_home_storage_access_mode="${'
            'RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"',
            hook,
        )
        self.assertIn(
            'RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}"',
            hook,
        )
        self.assertIn(
            "RUNTIME_HOME_STORAGE_ACCESS_MODE=" '"${runtime_home_storage_access_mode}"',
            hook,
        )
        self.assertIn(
            'data_service_mode="${PRODUCT_DATA_SERVICE_MODE:-bundled}"',
            hook,
        )
        self.assertIn(
            'PRODUCT_DATA_SERVICE_MODE="${data_service_mode}"',
            hook,
        )
        for source, local_name, default in (
            ("E2E_SHARED_STORAGE_SIZE", "shared_storage_size", "1Gi"),
            ("E2E_RWO_STORAGE_SIZE", "rwo_storage_size", "1Gi"),
            (
                "E2E_RUNTIME_HOME_STORAGE_SIZE",
                "runtime_home_storage_size",
                "2Gi",
            ),
        ):
            self.assertIn(
                f'{local_name}="${{{source}:-{default}}}"',
                hook,
            )
            self.assertIn(
                f'{source}="${{{local_name}}}"',
                hook,
            )

    def test_immutable_infrastructure_images_are_forwarded_to_helm(self) -> None:
        digests = {
            "redis": "e" * 64,
            "postgres": "f" * 64,
        }
        rendered = self._render(
            "dynamic",
            redis_image=f"registry.example/platform-redis@sha256:{digests['redis']}",
            postgres_image=(
                f"registry.example/platform-postgres@sha256:{digests['postgres']}"
            ),
        )

        for values_path, repository, digest in (
            ("redis.image", "registry.example/platform-redis", digests["redis"]),
            (
                "postgres.image",
                "registry.example/platform-postgres",
                digests["postgres"],
            ),
        ):
            self.assertIn(f"{values_path}.repository={repository}", rendered["helm"])
            self.assertIn(
                f"{values_path}.digest=sha256:{digest}",
                rendered["helm"],
            )
            self.assertIn(f"{values_path}.tag=", rendered["helm"])

    def test_external_data_services_use_non_chart_tls_endpoints(self) -> None:
        rendered = self._render("dynamic", data_service_mode="external")

        external = rendered["external_data_services"]
        self.assertIn("name: workspace-e2e-run-1-data", external)
        self.assertIn("name: external-postgres", external)
        self.assertIn("name: external-redis", external)
        self.assertIn("ssl=on", external)
        self.assertIn("--tls-port", external)
        self.assertIn("--tls-auth-clients", external)
        self.assertIn(
            '"--sni", "external-redis.workspace-e2e-run-1-data.svc.cluster.local"',
            external,
        )
        self.assertIn('"-h", "127.0.0.1"', external)
        self.assertIn("platform_login", external)
        self.assertIn("CREATEROLE INHERIT NOREPLICATION", external)
        self.assertIn("GRANT pg_signal_backend", external)
        resources = list(yaml.safe_load_all(external))
        claims = {
            resource["metadata"]["name"]: resource
            for resource in resources
            if resource["kind"] == "PersistentVolumeClaim"
        }
        self.assertEqual(
            set(claims), {"external-postgres-data", "external-redis-data"}
        )
        deployments = {
            resource["metadata"]["name"]: resource
            for resource in resources
            if resource["kind"] == "Deployment"
        }
        for service in ("external-postgres", "external-redis"):
            data_volume = next(
                volume
                for volume in deployments[service]["spec"]["template"]["spec"][
                    "volumes"
                ]
                if volume["name"] == "data"
            )
            self.assertEqual(
                data_volume["persistentVolumeClaim"]["claimName"],
                f"{service}-data",
            )
            self.assertNotIn("emptyDir", data_volume)

        secrets = rendered["platform_data_service_secrets"]
        self.assertIn("sslmode=verify-full", secrets)
        self.assertIn(
            "sslrootcert=/etc/aileron/data-service-ca/platform-database/ca.crt",
            secrets,
        )
        self.assertEqual(secrets.count("rediss://"), 3)
        self.assertIn("name: product-platform-database-ca", secrets)
        self.assertIn("name: product-redis-general-ca", secrets)
        self.assertIn("name: product-redis-job-queue-ca", secrets)
        self.assertIn("name: product-redis-job-result-ca", secrets)

        for expected in (
            "postgres.enabled=false",
            "platformDatabase.caSecretName=product-platform-database-ca",
            "redis.enabled=false",
            "redis.connections.general.urlSecretName=product-redis-general",
            "redis.connections.jobQueue.urlSecretName=product-redis-job-queue",
            "redis.connections.jobResult.urlSecretName=product-redis-job-result",
        ):
            self.assertIn(expected, rendered["helm"])
        self.assertIn("--set postgres.enabled=false", rendered["helm"])
        self.assertIn("--set redis.enabled=false", rendered["helm"])
        self.assertIn(
            "platformPublicOrigin=https://aileron.example.test", rendered["helm"]
        )
        self.assertNotIn("workspaceManager.env", rendered["helm"])
        self.assertNotIn("oidc.discoveryUrl", rendered["helm"])

    def test_static_nfs_rejects_unsafe_inherited_mount_option(self) -> None:
        rendered = self._render(
            "static-nfs",
            mount_options="vers=4.1\nhard\nunsafe option",
            expected_returncode=1,
        )

        self.assertIn(
            "source PV contains an unsafe NFS mountOption",
            rendered["stderr"],
        )

    def test_product_storage_access_modes_match_dynamic_provisioning(self) -> None:
        values = (
            REPO_ROOT / "helm/aileron/tests/values/product-conformance.yaml"
        ).read_text(encoding="utf-8")

        parsed_values = yaml.safe_load(values)
        self.assertEqual(
            parsed_values["kubernetes"]["managerState"]["accessModes"],
            ["ReadWriteOnce"],
        )
        self.assertEqual(
            parsed_values["kubernetes"]["runtimeHome"]["accessMode"],
            "ReadWriteOnce",
        )

    def test_requires_explicit_rwo_storage_class(self) -> None:
        rendered = self._render(
            "dynamic",
            include_rwo_storage_class=False,
            expected_returncode=2,
        )

        self.assertIn("RWO_STORAGE_CLASS is required", rendered["stderr"])

    def test_rejects_mutable_runtime_image_before_cluster_changes(self) -> None:
        rendered = self._render(
            "static-nfs",
            runtime_image="registry.example/runtime:test",
            expected_returncode=1,
        )

        self.assertIn(
            "RUNTIME_IMAGE must be an immutable sha256 reference",
            rendered["stderr"],
        )


if __name__ == "__main__":
    unittest.main()
