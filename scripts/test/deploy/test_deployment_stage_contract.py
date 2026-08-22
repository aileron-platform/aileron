import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _normalize_requirement_name(value: str) -> str:
    return value.lower().replace("_", "-")


def _assert_hashed_lock(requirements: Path) -> dict[str, str]:
    lines = requirements.read_text(encoding="utf-8").splitlines()
    package_indexes = [
        index for index, line in enumerate(lines) if line and not line.startswith(" ")
    ]
    assert package_indexes
    locked_versions: dict[str, str] = {}
    for position, start in enumerate(package_indexes):
        end = (
            package_indexes[position + 1]
            if position + 1 < len(package_indexes)
            else len(lines)
        )
        stanza = lines[start:end]
        assert "==" in stanza[0] and stanza[0].endswith(" \\")
        assert len(stanza) > 1
        hashes = [line.strip().removesuffix(" \\") for line in stanza[1:]]
        assert all(
            re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", digest)
            and digest != f"--hash=sha256:{'0' * 64}"
            for digest in hashes
        )
        assert not stanza[-1].endswith(" \\")
        name, version = stanza[0].removesuffix(" \\").split("==", 1)
        locked_versions[_normalize_requirement_name(name)] = version
    return locked_versions


def _assert_direct_requirements_are_locked(
    requirements_input: Path, requirements_lock: Path
) -> None:
    direct_requirements = requirements_input.read_text(encoding="utf-8").splitlines()
    assert direct_requirements
    assert all("==" in requirement for requirement in direct_requirements)
    locked_versions = _assert_hashed_lock(requirements_lock)
    for requirement in direct_requirements:
        name, version = requirement.split("==", 1)
        base_name = name.split("[", 1)[0]
        assert locked_versions[_normalize_requirement_name(base_name)] == version


def test_rke2_runtime_dependencies_have_one_pinned_bootstrap_contract() -> None:
    requirements_input = ROOT / "scripts/deploy/rke2/requirements.in"
    requirements = ROOT / "scripts/deploy/rke2/requirements.txt"
    assert requirements_input.read_text(encoding="utf-8").splitlines() == [
        "jsonschema==4.25.1",
        "PyYAML==6.0.2",
    ]
    _assert_direct_requirements_are_locked(requirements_input, requirements)
    bootstrap = (
        "/root/aileron-private/python/bin/python -m pip install "
        "--disable-pip-version-check --require-hashes --requirement "
        "scripts/deploy/rke2/requirements.txt"
    )
    document = (ROOT / "scripts/deploy/rke2/README.md").read_text(encoding="utf-8")
    assert "python3 -m venv /root/aileron-private/python" in document
    assert bootstrap in document


def test_static_hashed_lock_gate_rejects_placeholder_digest(tmp_path: Path) -> None:
    counterfeit = tmp_path / "requirements.txt"
    counterfeit.write_text(
        "example==1.0.0 \\\n" f"    --hash=sha256:{'0' * 64}\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError):
        _assert_hashed_lock(counterfeit)


def test_python39_amd64_stage_installs_the_production_deployment_lock() -> None:
    dockerfile = (ROOT / "scripts/test/deploy/Dockerfile").read_text(encoding="utf-8")
    stage_start = re.search(
        r"(?m)^FROM --platform=linux/amd64 "
        r"python:3\.9-slim@sha256:[0-9a-f]{64} AS deployment-python39-lock$",
        dockerfile,
    )
    assert stage_start is not None
    final_stage = dockerfile.index("\nFROM ", stage_start.end())
    python39_stage = dockerfile[stage_start.start() : final_stage]
    assert (
        "COPY scripts/deploy/rke2/requirements.txt "
        "/opt/aileron-deploy/requirements.txt" in python39_stage
    )
    assert "--require-hashes" in python39_stage
    assert "python -m pip check" in python39_stage
    assert "import sys, jsonschema, yaml" in python39_stage
    assert "sys.version_info[:2] == (3, 9)" in python39_stage
    assert "COPY scripts/deploy/rke2 /repo/scripts/deploy/rke2" in python39_stage
    assert "for script_path in /repo/scripts/deploy/rke2/*.py" in python39_stage
    assert 'python "${script_path}" --help' in python39_stage
    assert "python39-lock.verified" in python39_stage
    assert (
        "COPY --from=deployment-python39-lock "
        "/opt/aileron-deploy/python39-lock.verified "
        "/opt/aileron-deploy/python39-lock.verified" in dockerfile[final_stage:]
    )


def test_built_container_contains_python39_production_lock_marker() -> None:
    marker = Path("/opt/aileron-deploy/python39-lock.verified")
    assert marker.read_text(encoding="utf-8") == ("python3.9-locked-runtime=verified\n")


def test_container_python_dependencies_use_complete_hashed_locks() -> None:
    contracts = (
        (
            ROOT / "scripts/test/deploy/requirements.in",
            ROOT / "scripts/test/deploy/requirements.txt",
            ROOT / "scripts/test/deploy/Dockerfile",
        ),
        (
            ROOT / "scripts/test/kubernetes/product-conformance/requirements.in",
            ROOT / "scripts/test/kubernetes/product-conformance/requirements.txt",
            ROOT / "scripts/test/kubernetes/product-conformance/Dockerfile",
        ),
    )
    for requirements_input, requirements_lock, dockerfile in contracts:
        _assert_direct_requirements_are_locked(requirements_input, requirements_lock)
        assert "--require-hashes" in dockerfile.read_text(encoding="utf-8")


def test_only_acceptance_aggregator_can_claim_complete_deployment() -> None:
    deploy = (ROOT / "scripts/deploy/rke2/deploy.sh").read_text(encoding="utf-8")
    acceptance = (ROOT / "scripts/deploy/rke2/acceptance_evidence.py").read_text(
        encoding="utf-8"
    )

    assert "core-stage=passed" in deploy
    assert "deployment=passed" not in deploy
    assert 'print("deployment=passed")' in acceptance


def test_legacy_bearer_smoke_is_not_a_deployment_surface() -> None:
    deployment_directory = ROOT / "scripts/deploy/rke2"
    assert not (deployment_directory / "smoke.sh").exists()
    assert not (deployment_directory / "smoke_kubeconfig.py").exists()

    current_contract_documents = [
        ROOT / "docs-site/docs/installation/kubernetes.md",
        ROOT
        / "docs-site/i18n/en/docusaurus-plugin-content-docs/current/installation/kubernetes.md",
        deployment_directory / "README.md",
    ]
    for document in current_contract_documents:
        content = document.read_text(encoding="utf-8")
        assert "smoke.sh" not in content
        assert "AILERON_API_TOKEN" not in content


def test_internal_runbooks_expose_only_the_homelab_lifecycle_facade() -> None:
    deployment_directory = ROOT / "scripts/deploy/rke2"
    current_documents = [deployment_directory / "README.md"]
    direct_internal_command = re.compile(
        r"(?m)^\s*(?:python3\s+)?scripts/deploy/rke2/"
        r"(?:bootstrap_acceptance_trust|build-push-images|prepare_release_inventory|"
        r"prepare_backend_attestor|ensure_installation_namespaces|acceptance_producer|"
        r"reset_plan|install|prepare_browser_input|acceptance_bundle|acceptance_evidence)"
        r"(?:\.py|\.sh)?\b"
    )
    for path in current_documents:
        document = path.read_text(encoding="utf-8")
        assert "scripts/deploy/rke2/homelab.py stage" in document
        assert "scripts/deploy/rke2/homelab.py apply" in document
        assert "scripts/deploy/rke2/homelab.py status" in document
        assert "newInstallation" in document
        assert "requiredApprovalDigest" in document
        assert direct_internal_command.search(document) is None
        assert "--browser-input" not in document
        for removed_selector in (
            "--acceptance-directory",
            "--inventory-output",
            "--execution-state-output",
            "--execution-lock-file",
        ):
            assert removed_selector not in document


def test_deploy_requires_context_and_pins_every_cluster_command() -> None:
    deploy = (ROOT / "scripts/deploy/rke2/deploy.sh").read_text(encoding="utf-8")

    assert '[ -n "${context}" ] || usage' in deploy
    assert "kubectl_target() {" in deploy
    assert 'kubectl --context "${context}" "$@"' in deploy
    assert "helm_target() {" in deploy
    assert 'helm --kube-context "${context}" "$@"' in deploy
    assert not re.search(
        r"(?m)^\s*(?:if\s+)?(?:!\s+)?kubectl\s+(?:apply|get|patch|delete|wait)\b",
        deploy,
    )
    assert not re.search(
        r"(?m)^\s*(?:if\s+)?(?:!\s+)?helm\s+"
        r"(?:status|get|list|upgrade|rollback|uninstall)\b",
        deploy,
    )


def test_deploy_revalidates_live_identity_and_full_preflight_before_mutation() -> None:
    deploy = (ROOT / "scripts/deploy/rke2/deploy.sh").read_text(encoding="utf-8")

    for required_input in (
        "--identity-mode MODE",
        "--harbor-dockerconfig FILE",
        "--apps-tls-cert FILE",
        "--oidc-issuer URL",
        "--oidc-ca FILE",
        "--platform-artifacts DIR",
    ):
        assert required_input in deploy
    assert "preflight_receipt" not in deploy
    assert "preflight_receipt.py" not in deploy
    identity_attestation = deploy.index("assert-equivalent-manifests")
    oidc_readiness = deploy.index("wait_for_oidc.py")
    full_preflight = deploy.index('preflight.sh"')
    namespace_apply = deploy.index("ensure_installation_namespaces.py")
    crd_apply = deploy.index("kubectl_target apply")
    helm_upgrade = deploy.index("helm_target upgrade --install aileron")
    assert (
        identity_attestation
        < oidc_readiness
        < full_preflight
        < namespace_apply
        < crd_apply
        < helm_upgrade
    )
    assert "SKIP_PREFLIGHT" not in deploy
    assert "--signing-key" not in deploy


def test_preflight_requires_context_and_pins_every_cluster_command() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    assert '[ -n "${expected_context}" ] || usage' in preflight
    assert "kubectl_target() {" in preflight
    assert 'kubectl --context "${expected_context}" "$@"' in preflight
    assert "helm_target() {" in preflight
    assert 'helm --kube-context "${expected_context}" "$@"' in preflight
    assert not re.search(
        r"(?m)^\s*(?:if\s+)?(?:!\s+)?kubectl\s+"
        r"(?:apply|cluster-info|get|patch|delete|wait)\b",
        preflight,
    )
    assert not re.search(
        r"(?m)^\s*(?:if\s+)?(?:!\s+)?helm\s+"
        r"(?:status|get|list|upgrade|rollback|uninstall)\b",
        preflight,
    )


def test_preflight_gates_supported_helm_version_and_required_capabilities() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    assert "helm_contract.py" in preflight
    assert "validate-version" in preflight
    assert "Helm client must be a stable release >=3.13.0 and <4.0.0" in preflight
    for capability in (
        "--atomic",
        "--history-max",
        "--dry-run",
        "server-side dry-run",
        "--cleanup-on-fail",
    ):
        assert capability in preflight


def test_capacity_preflight_derives_release_mode_and_passes_it_to_solver() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    release_inventory = preflight.index("helm_target list")
    capacity = preflight.index("validate-execution-plane-capacity")
    assert release_inventory < capacity
    assert 'release-mode "${core_release_inventory}"' in preflight
    assert '--deployment-mode "${core_deployment_mode}"' in preflight


def test_preflight_uses_verified_live_turn_namespace_for_network_security() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    assert (
        'kubectl_target get namespace "${turn_namespace}" -o json '
        '> "${turn_namespace_manifest}"' in preflight
    )
    assert 'validate-privileged-namespace "${turn_namespace_manifest}"' in preflight
    assert '--namespace "${turn_namespace}"' in preflight
    assert '--owner-marker "aileron-installer"' in preflight
    assert (
        'validate-network-security "${rendered}" \\\n  --additional-manifest "${turn_namespace_manifest}"'
        in preflight
    )


def test_core_preflight_uses_planned_platform_inputs_before_secret_apply() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    assert "--harbor-dockerconfig FILE" in preflight
    assert "--apps-tls-cert FILE" in preflight
    assert (
        'validate-image-pull-secret \\\n      "${planned_image_pull_secret}"'
        in preflight
    )
    assert 'install -m 0600 "${apps_tls_cert}" "${tls_crt}"' in preflight
    assert 'kubectl_target get secret "${image_pull_secret}"' not in preflight
    assert 'kubectl_target get secret "${tls_secret}"' not in preflight
    assert (
        '"${RUNTIME_ASSERTION_SIGNER_SECRET:-runtime-assertion-signer}"'
        not in preflight
    )
    assert (
        '"${RUNTIME_ASSERTION_JWKS_SECRET:-runtime-assertion-public-jwks}"'
        not in preflight
    )
    assert '"${BROWSER_KEYRING_SECRET:-browser-credential-keyring}"' not in preflight


def test_core_preflight_pins_all_registry_access_to_private_dockerconfig() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")

    assert (
        'install -m 0600 "${harbor_dockerconfig}" '
        '"${docker_config_directory}/config.json"' in preflight
    )
    assert 'docker --config "${docker_config_directory}" pull ' in preflight
    assert 'docker --config "${docker_config_directory}" image inspect ' in preflight
    assert re.search(r"(?m)^\s*docker pull ", preflight) is None
    assert re.search(r"(?m)^\s*docker image inspect ", preflight) is None


def test_storage_preflight_requires_and_pins_delegated_context() -> None:
    preflight = (ROOT / "scripts/deploy/rke2/preflight.sh").read_text(encoding="utf-8")
    storage = (ROOT / "scripts/deploy/rke2/preflight-storage.sh").read_text(
        encoding="utf-8"
    )

    assert re.search(
        r'preflight-storage\.sh"\s+\\?\s*--context\s+"\$\{expected_context\}"',
        preflight,
    )
    assert 'test -n "${context}" || usage' in storage
    assert "kubectl_target() {" in storage
    assert '"${KUBECTL}" --context "${context}" "$@"' in storage
    assert storage.count('"${KUBECTL}"') == 1
