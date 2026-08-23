"""Production HomeLab execution-port contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import stat
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.deploy.rke2 import homelab as FACADE
from scripts.deploy.rke2 import homelab_execution as MODULE

COMMIT = "a" * 40
RUN_ID = "run-0123456789abcdef0123456789abcdef"
PLAN_DIGEST = "b" * 64
APPROVAL_DIGEST = "c" * 64


INPUT_PATHS = {
    "kubeconfig": "inputs/kubeconfig",
    "backendExecutionProfile": "inputs/backend-execution-profile.json",
    "harborDockerconfig": "inputs/docker/config.json",
    "registryCa": "inputs/registry-ca.crt",
    "appsTlsCertificate": "inputs/apps-tls.crt",
    "appsTlsPrivateKey": "inputs/apps-tls.key",
    "appsTlsCa": "inputs/apps-ca.crt",
    "oidcCa": "inputs/oidc-ca.crt",
    "externalOidcClientSecret": "inputs/external-oidc-client-secret",
    "oidcLoginUsername": "inputs/oidc-login-username",
    "oidcLoginPassword": "inputs/oidc-login-password",
}


class FixedSourceInspector:
    def __init__(self, *, commit: str = COMMIT, clean: bool = True) -> None:
        self.commit = commit
        self.clean = clean
        self.calls = 0

    def inspect(self) -> object:
        self.calls += 1
        return SimpleNamespace(head_commit=self.commit, clean=self.clean)


class CaptureRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
    ) -> str:
        actual_environment = dict(environment or {})
        self.calls.append((command, actual_environment))
        output = actual_environment.get("OUTPUT_FILE")
        if output is not None:
            destination = Path(output)
            destination.write_text(
                "workspace-manager\t"
                f"{COMMIT}\tlinux/amd64\t"
                "harbor.example.test/library/workspace-manager:git-"
                f"{COMMIT}\t"
                "harbor.example.test/library/workspace-manager@sha256:"
                f"{'d' * 64}\n",
                encoding="utf-8",
            )
            destination.chmod(0o600)
        return ""


class MissingPrerequisite(RuntimeError):
    exit_code = 78


class FakeInstallModule:
    InstallationPrerequisiteError = MissingPrerequisite

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.validate_attempts = 0

    def install_rke2(self, **arguments: Any) -> None:
        self.calls.append(arguments)
        if arguments["phase"] == "validate":
            self.validate_attempts += 1
            if self.validate_attempts == 1:
                raise MissingPrerequisite("namespaces are absent")


class FakeResetDisposition(str, Enum):
    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaitingApproval"


class FakeResetError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FakeResetInput:
    name: str
    path: Path
    digest: str


@dataclass(frozen=True)
class FakeResetProfile:
    context: str
    registry_host: str
    platform_url: str
    identity_mode: str
    issuer_url: str
    admin_console_url: str | None
    client_id: str
    acceptance_login_mode: str


@dataclass(frozen=True)
class FakeResetRequest:
    run_id: str
    plan_digest: str
    approval_digest: str
    commit: str
    profile: FakeResetProfile
    inputs: tuple[FakeResetInput, ...]


@dataclass(frozen=True)
class FakeResetResult:
    disposition: FakeResetDisposition
    reset_snapshot_digest: str
    post_reset_report_digest: str | None


class FakeResetModule:
    ResetOperationDisposition = FakeResetDisposition
    ResetOperationError = FakeResetError
    ResetOperationInput = FakeResetInput
    ResetOperationProfile = FakeResetProfile
    ResetOperationRequest = FakeResetRequest
    ResetOperationResult = FakeResetResult

    def __init__(self, result: FakeResetResult | None = None) -> None:
        self.result = result or FakeResetResult(
            disposition=FakeResetDisposition.COMPLETED,
            reset_snapshot_digest="d" * 64,
            post_reset_report_digest="e" * 64,
        )
        self.calls: list[FakeResetRequest] = []

    def execute_reset_operation(self, request: FakeResetRequest) -> FakeResetResult:
        self.calls.append(request)
        return self.result


class FakeAcceptanceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FakeBrowserLoginDriver:
    kind: str
    username_selector: str | None = None
    password_selector: str | None = None
    submit_selector: str | None = None
    error_selector: str | None = None


@dataclass(frozen=True)
class FakeAcceptanceRequest:
    expected_commit: str
    deployment_run_id: str
    authentication_mode: str
    context: str
    kubeconfig: Path
    platform_url: str
    issuer_url: str
    admin_console_url: str | None
    client_id: str
    image_inventory: Path
    reset_snapshot_digest: str
    apps_ca: Path
    oidc_ca: Path
    identity_artifacts_directory: Path | None
    browser_login_mode: str
    browser_login_driver: FakeBrowserLoginDriver
    browser_login_username: Path | None = None
    browser_login_password: Path | None = None


@dataclass(frozen=True)
class FakeWorkspaceIdentity:
    id: str
    user_subject: str


@dataclass(frozen=True)
class FakeAcceptanceResult:
    bundle_path: Path
    bundle_sha256: str
    workspace: FakeWorkspaceIdentity
    completed_sections: tuple[str, ...]
    reused_sections: tuple[str, ...]


class FakeAcceptanceModule:
    AcceptanceOperationError = FakeAcceptanceError
    AcceptanceOperationRequest = FakeAcceptanceRequest
    AcceptanceOperationResult = FakeAcceptanceResult
    BrowserLoginDriver = FakeBrowserLoginDriver
    WorkspaceIdentity = FakeWorkspaceIdentity

    def __init__(self) -> None:
        self.calls: list[FakeAcceptanceRequest] = []

    def execute_acceptance_operation(
        self, request: FakeAcceptanceRequest
    ) -> FakeAcceptanceResult:
        self.calls.append(request)
        return FakeAcceptanceResult(
            bundle_path=request.image_inventory.parent / "acceptance-bundle.json",
            bundle_sha256="f" * 64,
            workspace=FakeWorkspaceIdentity(
                id="workspace-1",
                user_subject="directory-user-1",
            ),
            completed_sections=("cleanReset", "oidcWorkspace", "browser"),
            reused_sections=(() if len(self.calls) == 1 else ("cleanReset",)),
        )


def _private_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for directory in (path.parent, *path.parents):
        if directory.exists() and directory.name in {"inputs", "docker"}:
            directory.chmod(0o700)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def _request(tmp_path: Path, step: FACADE.ExecutionStep) -> FACADE.ExecutionRequest:
    run_directory = tmp_path / "private/homelab/runs" / RUN_ID
    run_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_directory.chmod(0o700)
    profile = FACADE.HomelabProfile(
        profile_id="rke2-homelab",
        context="rke",
        registry_host="harbor.example.test",
        registry_project="library",
        platform_url="https://platform.example.test",
        turn_url="turn:turn.example.test:3478",
        identity_mode="externalOidc",
        issuer_url="https://identity.example.test/realms/aileron",
        admin_console_url=None,
        client_id="aileron",
        acceptance_login_mode="files",
        acceptance_login_driver=FACADE.AcceptanceLoginDriver(
            kind="form",
            username_selector="input[name='username']",
            password_selector="input[name='password']",
            submit_selector="button[type='submit']",
            error_selector="[role='alert']",
        ),
    )
    staged = []
    for name, relative in INPUT_PATHS.items():
        content = f"private-{name}\n".encode()
        path = _private_file(run_directory / relative, content)
        staged.append(
            FACADE.StagedInput(
                name=name,
                path=path,
                digest=hashlib.sha256(content).hexdigest(),
            )
        )
    return FACADE.ExecutionRequest(
        run_id=RUN_ID,
        plan_digest=PLAN_DIGEST,
        approval_digest=APPROVAL_DIGEST,
        commit=COMMIT,
        step=step,
        attempt=1,
        profile=profile,
        inputs=tuple(staged),
    )


def _port(
    tmp_path: Path,
    **overrides: Any,
) -> MODULE.ProductionExecutionPort:
    defaults: dict[str, Any] = {
        "facade": FACADE,
        "repository_root": tmp_path / "repository",
        "source_inspector": FixedSourceInspector(),
        "new_installation_operation": lambda **_arguments: {},
        "release_inventory_operation": lambda **_arguments: {},
        "command_runner": CaptureRunner(),
        "registry_trust_validator": lambda **_arguments: None,
        "install_module": FakeInstallModule(),
        "reset_module": FakeResetModule(),
        "acceptance_module": FakeAcceptanceModule(),
    }
    defaults.update(overrides)
    return MODULE.ProductionExecutionPort(**defaults)


def _new_installation_result(request: FACADE.ExecutionRequest) -> dict[str, Any]:
    return {
        "schemaVersion": "aileron-new-installation-transaction/v1",
        "operation": "noOp",
        "commit": request.commit,
        "context": request.profile.context,
        "clusterUid": "11111111-1111-4111-8111-111111111111",
        "identityMode": request.profile.identity_mode,
        "issuerUrl": request.profile.issuer_url,
        "clientId": request.profile.client_id,
        "oldInstallationId": "22222222-2222-4222-8222-222222222222",
        "newInstallationId": "22222222-2222-4222-8222-222222222222",
        "oldSecret": {"uid": "secret-uid", "resourceVersion": "17"},
        "resultSecret": {"uid": "secret-uid", "resourceVersion": "17"},
        "acceptanceNamespace": {
            "uid": "namespace-uid",
            "resourceVersion": "21",
        },
        "quarantine": {},
        "state": "completed",
        "pointOfNoReturn": False,
    }


def test_new_installation_uses_the_only_public_tri_state_seam(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION)
    calls: list[dict[str, Any]] = []

    def operation(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return _new_installation_result(request)

    inspector = FixedSourceInspector()
    port = _port(
        tmp_path,
        source_inspector=inspector,
        new_installation_operation=operation,
    )

    first = port.execute(request)
    second = port.execute(request)

    assert first == second
    assert isinstance(first, FACADE.ExecutionReceipt)
    assert first.step is FACADE.ExecutionStep.NEW_INSTALLATION
    assert first.disposition is FACADE.ExecutionDisposition.COMPLETED
    assert len(first.digest) == 64
    assert inspector.calls == 2
    assert (
        calls
        == [
            {
                "commit": COMMIT,
                "kubeconfig": next(
                    item.path for item in request.inputs if item.name == "kubeconfig"
                ),
                "context": "rke",
                "identity_mode": "externalOidc",
                "issuer_url": "https://identity.example.test/realms/aileron",
                "client_id": "aileron",
                "confirm_forward_only": True,
            }
        ]
        * 2
    )


def test_release_validates_registry_trust_builds_with_run_docker_config_and_signs(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.RELEASE_PREPARATION)
    trust_calls: list[dict[str, Any]] = []
    preparation_calls: list[dict[str, Any]] = []
    runner = CaptureRunner()
    created = True

    def trust(**arguments: Any) -> None:
        trust_calls.append(arguments)

    def prepare(**arguments: Any) -> dict[str, Any]:
        nonlocal created
        preparation_calls.append(arguments)
        result = {
            "schemaVersion": "aileron-release-inventory-preparation-result/v1",
            "commit": COMMIT,
            "context": "rke",
            "imageCount": 11,
            "created": created,
            "signedInventorySha256": "e" * 64,
        }
        created = False
        return result

    port = _port(
        tmp_path,
        command_runner=runner,
        registry_trust_validator=trust,
        release_inventory_operation=prepare,
    )

    first = port.execute(request)
    second = port.execute(request)

    assert first == second
    registry_ca = next(
        item.path for item in request.inputs if item.name == "registryCa"
    )
    assert (
        trust_calls
        == [{"registry_host": "harbor.example.test", "registry_ca": registry_ca}] * 2
    )
    assert len(runner.calls) == 2
    for command, environment in runner.calls:
        assert command == [
            str(tmp_path / "repository/scripts/deploy/rke2/build-push-images.sh")
        ]
        assert environment["DOCKER_CONFIG"] == str(request.inputs[2].path.parent)
        assert environment["HARBOR_REGISTRY"] == "harbor.example.test"
        assert environment["HARBOR_PROJECT"] == "library"
        assert environment["EXPECTED_COMMIT"] == COMMIT
        assert environment["OMIT_IMAGE_COMPONENTS"] == ""
        assert environment["OUTPUT_FILE"].endswith(f"/{RUN_ID}/release/images.tsv")
    inventory = Path(runner.calls[-1][1]["OUTPUT_FILE"])
    assert stat.S_IMODE(inventory.stat().st_mode) == 0o600
    assert (
        preparation_calls
        == [
            {
                "commit": COMMIT,
                "context": "rke",
                "kubeconfig": next(
                    item.path for item in request.inputs if item.name == "kubeconfig"
                ),
                "inventory": inventory,
                "docker_config": next(
                    item.path
                    for item in request.inputs
                    if item.name == "harborDockerconfig"
                ),
                "registry": "harbor.example.test",
                "project": "library",
                "omitted_components": frozenset(),
            }
        ]
        * 2
    )


def test_release_omits_external_redis_image_from_publish_contract(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.RELEASE_PREPARATION)
    run_directory = request.inputs[0].path.parent.parent
    content = b"redis:\n  enabled: false\n"
    values = _private_file(
        run_directory / MODULE.INPUT_PATHS["coreDataServiceValues"], content
    )
    request = FACADE.ExecutionRequest(
        **{
            **request.__dict__,
            "inputs": (
                *request.inputs,
                FACADE.StagedInput(
                    name="coreDataServiceValues",
                    path=values,
                    digest=hashlib.sha256(content).hexdigest(),
                ),
            ),
        }
    )
    runner = CaptureRunner()
    calls: list[dict[str, Any]] = []

    def prepare(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return {
            "schemaVersion": "aileron-release-inventory-preparation-result/v1",
            "commit": COMMIT,
            "context": "rke",
            "imageCount": 10,
            "created": True,
            "signedInventorySha256": "e" * 64,
        }

    _port(
        tmp_path,
        command_runner=runner,
        release_inventory_operation=prepare,
    ).execute(request)

    assert runner.calls[0][1]["OMIT_IMAGE_COMPONENTS"] == "platform-redis"
    assert calls[0]["omitted_components"] == frozenset({"platform-redis"})


def test_install_prepares_namespaces_only_for_prerequisite_78_and_uses_profile_url(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.INSTALL)
    run_directory = request.inputs[0].path.parent.parent
    release_directory = run_directory / "release"
    release_directory.mkdir(mode=0o700)
    inventory = release_directory / "images.tsv"
    inventory.write_text("signed-release-input\n", encoding="utf-8")
    inventory.chmod(0o600)
    _private_file(
        tmp_path / "private/install" / COMMIT / "signed-image-inventory.json",
        b"signed-inventory\n",
    )
    install_module = FakeInstallModule()
    port = _port(tmp_path, install_module=install_module)

    receipt = port.execute(request)

    assert receipt.disposition is FACADE.ExecutionDisposition.COMPLETED
    assert [call["phase"] for call in install_module.calls] == [
        "validate",
        "prepare-cluster",
        "validate",
        "apply",
    ]
    assert install_module.calls[1]["confirm_create_namespaces"] is True
    assert all(
        call["platform_url"] == "https://platform.example.test"
        for call in install_module.calls
    )
    assert all(call["inventory_path"] == inventory for call in install_module.calls)
    assert all(
        call["work_directory"] == tmp_path / "private/install" / COMMIT
        for call in install_module.calls
    )


def test_install_projects_optional_core_data_service_inputs(tmp_path: Path) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.INSTALL)
    run_directory = request.inputs[0].path.parent.parent
    release_directory = run_directory / "release"
    release_directory.mkdir(mode=0o700)
    inventory = release_directory / "images.tsv"
    inventory.write_text("signed-release-input\n", encoding="utf-8")
    inventory.chmod(0o600)
    _private_file(
        tmp_path / "private/install" / COMMIT / "signed-image-inventory.json",
        b"signed-inventory\n",
    )
    additional = []
    for name, content in (
        ("coreDataServiceValues", b"postgres:\n  enabled: false\n"),
        ("platformDatabaseUrl", b"postgresql://platform@db/platform"),
        ("platformDatabaseCa", b"certificate"),
    ):
        path = _private_file(run_directory / MODULE.INPUT_PATHS[name], content)
        additional.append(
            FACADE.StagedInput(
                name=name,
                path=path,
                digest=hashlib.sha256(content).hexdigest(),
            )
        )
    request = FACADE.ExecutionRequest(
        **{
            **request.__dict__,
            "inputs": (*request.inputs, *additional),
        }
    )
    install_module = FakeInstallModule()

    _port(tmp_path, install_module=install_module).execute(request)

    assert all(
        call["core_data_service_values"]
        == run_directory / MODULE.INPUT_PATHS["coreDataServiceValues"]
        for call in install_module.calls
    )
    assert all(
        call["core_data_service_inputs"]
        == (
            (
                "database-url",
                run_directory / MODULE.INPUT_PATHS["platformDatabaseUrl"],
            ),
            (
                "platform-database-ca",
                run_directory / MODULE.INPUT_PATHS["platformDatabaseCa"],
            ),
        )
        for call in install_module.calls
    )


def test_reset_projects_neutral_types_and_uses_snapshot_as_approval_receipt(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.RESET)
    reset_module = FakeResetModule(
        FakeResetResult(
            disposition=FakeResetDisposition.AWAITING_APPROVAL,
            reset_snapshot_digest="d" * 64,
            post_reset_report_digest=None,
        )
    )
    port = _port(tmp_path, reset_module=reset_module)

    receipt = port.execute(request)

    assert receipt.disposition is FACADE.ExecutionDisposition.AWAITING_APPROVAL
    assert receipt.digest == "d" * 64
    assert len(reset_module.calls) == 1
    projected = reset_module.calls[0]
    assert isinstance(projected, FakeResetRequest)
    assert projected.approval_digest == APPROVAL_DIGEST
    assert projected.profile == FakeResetProfile(
        context="rke",
        registry_host="harbor.example.test",
        platform_url="https://platform.example.test",
        identity_mode="externalOidc",
        issuer_url="https://identity.example.test/realms/aileron",
        admin_console_url=None,
        client_id="aileron",
        acceptance_login_mode="files",
    )
    assert all(isinstance(item, FakeResetInput) for item in projected.inputs)


def test_acceptance_uses_reset_approval_and_emits_a_deterministic_safe_receipt(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.ACCEPTANCE)
    signed_inventory = (
        tmp_path / "private/install" / COMMIT / "signed-image-inventory.json"
    )
    _private_file(signed_inventory, b"signed-inventory\n")
    acceptance_module = FakeAcceptanceModule()
    port = _port(tmp_path, acceptance_module=acceptance_module)

    first = port.execute(request)
    second = port.execute(request)

    assert first == second
    assert first.disposition is FACADE.ExecutionDisposition.COMPLETED
    assert len(acceptance_module.calls) == 2
    projected = acceptance_module.calls[0]
    assert projected.reset_snapshot_digest == APPROVAL_DIGEST
    assert projected.image_inventory == signed_inventory
    assert projected.admin_console_url is None
    assert projected.identity_artifacts_directory is None
    assert projected.browser_login_driver == FakeBrowserLoginDriver(
        kind="form",
        username_selector="input[name='username']",
        password_selector="input[name='password']",
        submit_selector="button[type='submit']",
        error_selector="[role='alert']",
    )
    assert projected.browser_login_username == next(
        item.path for item in request.inputs if item.name == "oidcLoginUsername"
    )
    assert projected.browser_login_password == next(
        item.path for item in request.inputs if item.name == "oidcLoginPassword"
    )


def test_external_identity_postgres_selects_its_installed_artifact_directory(
    tmp_path: Path,
) -> None:
    private_root = tmp_path / "private"
    inputs = SimpleNamespace(
        private_root=private_root,
        paths={"identityDatabaseUsername": private_root / "inputs/username"},
    )

    assert MODULE._identity_artifacts_directory(
        inputs,
        identity_mode="bundledKeycloak",
    ) == (
        private_root
        / "install-secrets/rke2/identity-artifacts/postgres-disabled"
    )


@pytest.mark.parametrize(
    ("commit", "clean", "code"),
    (
        (COMMIT, False, "sourceCheckoutNotClean"),
        ("f" * 40, True, "sourceCommitMismatch"),
    ),
)
def test_every_step_fails_closed_on_source_identity_drift(
    tmp_path: Path,
    commit: str,
    clean: bool,
    code: str,
) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION)
    secret = "must-not-leak"

    def operation(**_arguments: Any) -> dict[str, Any]:
        raise RuntimeError(secret)

    port = _port(
        tmp_path,
        source_inspector=FixedSourceInspector(commit=commit, clean=clean),
        new_installation_operation=operation,
    )

    with pytest.raises(FACADE.ExecutionPortError) as caught:
        port.execute(request)

    assert caught.value.code == code
    assert secret not in str(caught.value)


def test_factory_uses_the_exact_facade_types_for_direct_script_loading(
    tmp_path: Path,
) -> None:
    facade_path = Path(FACADE.__file__).resolve()
    specification = importlib.util.spec_from_file_location(
        "homelab_direct", facade_path
    )
    assert specification and specification.loader
    direct_facade = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = direct_facade
    try:
        specification.loader.exec_module(direct_facade)
    finally:
        sys.modules.pop(specification.name, None)
    source = FixedSourceInspector()
    port = MODULE.create_production_execution_port(
        facade=direct_facade,
        repository_root=tmp_path / "repository",
        source_inspector=source,
        new_installation_operation=lambda **_arguments: {
            **_new_installation_result(
                _request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION)
            )
        },
        release_inventory_operation=lambda **_arguments: {},
        command_runner=CaptureRunner(),
        registry_trust_validator=lambda **_arguments: None,
        install_module=FakeInstallModule(),
    )
    profile = direct_facade.HomelabProfile(
        **_request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION).profile.__dict__
    )
    request = direct_facade.ExecutionRequest(
        run_id=RUN_ID,
        plan_digest=PLAN_DIGEST,
        approval_digest=APPROVAL_DIGEST,
        commit=COMMIT,
        step=direct_facade.ExecutionStep.NEW_INSTALLATION,
        attempt=1,
        profile=profile,
        inputs=tuple(
            direct_facade.StagedInput(
                name=item.name,
                path=item.path,
                digest=item.digest,
            )
            for item in _request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION).inputs
        ),
    )

    receipt = port.execute(request)

    assert type(receipt) is direct_facade.ExecutionReceipt
    assert receipt.step is direct_facade.ExecutionStep.NEW_INSTALLATION
    assert type(receipt.step) is direct_facade.ExecutionStep


def test_factory_eagerly_resolves_and_pins_all_operation_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_module = FakeResetModule()
    acceptance_module = FakeAcceptanceModule()
    modules = {
        "scripts.deploy.rke2.homelab_reset_operation": reset_module,
        "scripts.deploy.rke2.homelab_acceptance_operation": acceptance_module,
    }
    imports: list[str] = []

    def import_module(name: str) -> object:
        imports.append(name)
        return modules[name]

    monkeypatch.setattr(MODULE.importlib, "import_module", import_module)

    port = MODULE.create_production_execution_port(
        facade=FACADE,
        repository_root=tmp_path / "repository",
        source_inspector=FixedSourceInspector(),
        new_installation_operation=lambda **_arguments: {},
        release_inventory_operation=lambda **_arguments: {},
        command_runner=CaptureRunner(),
        registry_trust_validator=lambda **_arguments: None,
        install_module=FakeInstallModule(),
    )

    assert imports == [
        "scripts.deploy.rke2.homelab_reset_operation",
        "scripts.deploy.rke2.homelab_acceptance_operation",
    ]
    assert port.reset_module is reset_module
    assert port.acceptance_module is acceptance_module


def test_operation_failure_maps_to_a_safe_stable_code(tmp_path: Path) -> None:
    request = _request(tmp_path, FACADE.ExecutionStep.NEW_INSTALLATION)
    secret = str(next(iter(request.inputs)).path)

    def operation(**_arguments: Any) -> dict[str, Any]:
        raise RuntimeError(f"raw stderr and private path: {secret}")

    port = _port(tmp_path, new_installation_operation=operation)

    with pytest.raises(FACADE.ExecutionPortError) as caught:
        port.execute(request)

    assert caught.value.code == "newInstallationFailed"
    assert secret not in str(caught.value)
    assert "stderr" not in str(caught.value)
