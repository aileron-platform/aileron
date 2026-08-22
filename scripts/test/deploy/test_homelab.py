"""Public HomeLab lifecycle facade contract tests."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator

from scripts.deploy.rke2 import homelab as MODULE

COMMIT = "a" * 40
RUN_ID = "run-0123456789abcdef0123456789abcdef"
SECOND_RUN_ID = "run-11111111111111111111111111111111"
THIRD_RUN_ID = "run-22222222222222222222222222222222"
STEP_IDS = [
    "newInstallation",
    "releasePreparation",
    "reset",
    "install",
    "acceptance",
]
RESET_APPROVAL_DIGEST = "b" * 64
CONTRACT_DIRECTORY = (
    Path(__file__).resolve().parents[3] / "contracts/homelab-deployment"
)


class RecordingPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, request: object) -> object:
        self.calls.append(request)
        raise AssertionError("stage and status must not use the execution port")


class FixedSourceInspector:
    def __init__(self, *, commit: str = COMMIT, clean: bool = True) -> None:
        self.commit = commit
        self.clean = clean
        self.calls = 0

    def inspect(self) -> object:
        self.calls += 1
        return MODULE.SourceSnapshot(head_commit=self.commit, clean=self.clean)


class ApprovalPort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, request: object) -> object:
        assert isinstance(request, MODULE.ExecutionRequest)
        assert isinstance(request.profile, MODULE.HomelabProfile)
        self.calls.append(request)
        if (
            request.step is MODULE.ExecutionStep.RESET
            and request.approval_digest != RESET_APPROVAL_DIGEST
        ):
            return MODULE.ExecutionReceipt(
                step=request.step,
                disposition=MODULE.ExecutionDisposition.AWAITING_APPROVAL,
                digest=RESET_APPROVAL_DIGEST,
            )
        return MODULE.ExecutionReceipt(
            step=request.step,
            disposition=MODULE.ExecutionDisposition.COMPLETED,
            digest=hashlib.sha256(
                f"{request.step.value}:{request.attempt}".encode()
            ).hexdigest(),
        )


class FailOncePort:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.failed = False

    def execute(self, request: object) -> object:
        assert isinstance(request, MODULE.ExecutionRequest)
        self.calls.append(request)
        if request.step is MODULE.ExecutionStep.INSTALL and not self.failed:
            self.failed = True
            raise MODULE.ExecutionPortError("installUnavailable")
        return MODULE.ExecutionReceipt(
            step=request.step,
            disposition=MODULE.ExecutionDisposition.COMPLETED,
            digest=hashlib.sha256(
                f"{request.step.value}:{request.attempt}".encode()
            ).hexdigest(),
        )


class CapturePort:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, request: object) -> object:
        assert isinstance(request, MODULE.ExecutionRequest)
        self.calls.append(request)
        return MODULE.ExecutionReceipt(
            step=request.step,
            disposition=MODULE.ExecutionDisposition.AWAITING_APPROVAL,
            digest="e" * 64,
        )


class BlockingFirstPort:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.entered = threading.Event()
        self.release = threading.Event()

    def execute(self, request: object) -> object:
        assert isinstance(request, MODULE.ExecutionRequest)
        self.calls.append(request)
        if len(self.calls) == 1:
            self.entered.set()
            self.release.wait()
        return MODULE.ExecutionReceipt(
            step=request.step,
            disposition=MODULE.ExecutionDisposition.COMPLETED,
            digest=hashlib.sha256(
                f"{request.step.value}:{request.attempt}".encode()
            ).hexdigest(),
        )


def _directory(path: Path) -> Path:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _staged_profile_document(source: dict) -> dict:
    return {
        **{key: value for key, value in source.items() if key != "privateInputs"},
        "schemaVersion": "aileron-homelab-staged-profile/v1",
    }


def _private_profile(root: Path, document: dict | None = None) -> tuple[Path, bytes]:
    profile = root / "inputs/homelab-profile.json"
    _directory(profile.parent)
    if document is None:
        document, _ = _full_private_input_profile(root)
    content = (
        json.dumps(
            document,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    profile.write_bytes(content)
    profile.chmod(0o600)
    return profile, content


def _flatten_kubeconfig(command: list[str], *, environment: dict[str, str]) -> str:
    raw_snapshot = Path(command[command.index("--kubeconfig") + 1])
    assert environment == {"KUBECONFIG": str(raw_snapshot)}
    return raw_snapshot.read_text(encoding="utf-8")


def _full_private_input_profile(root: Path) -> tuple[dict, dict[str, bytes]]:
    kubeconfig = json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": "rke",
            "clusters": [
                {
                    "name": "rke",
                    "cluster": {
                        "server": "https://192.0.2.10:6443",
                        "certificate-authority-data": "Y2E=",
                    },
                }
            ],
            "contexts": [
                {
                    "name": "rke",
                    "context": {"cluster": "rke", "user": "rke"},
                }
            ],
            "users": [
                {
                    "name": "rke",
                    "user": {
                        "client-certificate-data": "Y2VydA==",
                        "client-key-data": "a2V5",
                    },
                }
            ],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    contents = {
        "kubeconfig": kubeconfig,
        "backendExecutionProfile": b'{"schemaVersion":"fixture/v1"}\n',
        "harborDockerconfig": b'{"auths":{"harbor.rke.soez.tw":{}}}\n',
        "registryCa": b"registry-ca\n",
        "appsTlsCertificate": b"apps-certificate\n",
        "appsTlsPrivateKey": b"apps-private-key\n",
        "appsTlsCa": b"apps-ca\n",
        "oidcCa": b"oidc-ca\n",
        "identityTlsCertificate": b"identity-certificate\n",
        "identityTlsPrivateKey": b"identity-private-key\n",
    }
    source_paths: dict[str, str | None] = {
        "externalOidcClientSecret": None,
        "oidcLoginUsername": None,
        "oidcLoginPassword": None,
        "coreDataServiceValues": None,
        "identityDataServiceValues": None,
        "platformDatabaseUrl": None,
        "platformDatabaseCa": None,
        "redisGeneralUrl": None,
        "redisJobQueueUrl": None,
        "redisJobResultUrl": None,
        "redisGeneralCa": None,
        "redisJobQueueCa": None,
        "redisJobResultCa": None,
        "identityDatabaseUsername": None,
        "identityDatabasePassword": None,
        "identityDatabaseCa": None,
    }
    for name, content in contents.items():
        path = root / "inputs" / f"{name}.input"
        _directory(path.parent)
        path.write_bytes(content)
        path.chmod(0o600)
        source_paths[name] = str(path)
    return (
        {
            "schemaVersion": "aileron-homelab-profile/v1",
            "profileId": "rke2-207",
            "context": "rke",
            "registry": {"host": "harbor.rke.soez.tw", "project": "library"},
            "endpoints": {
                "platformUrl": "https://aileron.apps.rke.soez.tw",
                "turnUrl": "turn:turn.apps.rke.soez.tw:3478",
            },
            "identity": {
                "mode": "bundledKeycloak",
                "issuerUrl": "https://keycloak.apps.rke.soez.tw/realms/aileron",
                "adminConsoleUrl": (
                    "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
                ),
                "clientId": "aileron-frontend",
            },
            "acceptance": {
                "loginMode": "breakGlass",
                "loginDriver": {"kind": "keycloak"},
            },
            "privateInputs": source_paths,
            "installationIntent": "newInstallation",
        },
        contents,
    )


def _set_private_input(
    document: dict,
    *,
    root: Path,
    name: str,
    content: bytes | None,
) -> Path | None:
    if content is None:
        document["privateInputs"][name] = None
        return None
    path = root / "inputs" / f"{name}.input"
    _directory(path.parent)
    path.write_bytes(content)
    path.chmod(0o600)
    document["privateInputs"][name] = str(path)
    return path


def _invoke(
    argv: list[str],
    *,
    private_root: Path,
    port: object,
    source_inspector: object | None = None,
    run_id: str = RUN_ID,
) -> tuple[int, dict, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = MODULE.main(
        argv,
        execution_port=port,
        private_root=private_root,
        stdout=stdout,
        stderr=stderr,
        run_id_factory=lambda: run_id,
        source_inspector=source_inspector or FixedSourceInspector(),
        kubeconfig_runner=_flatten_kubeconfig,
    )
    output = stdout.getvalue()
    return exit_code, json.loads(output) if output else {}, stderr.getvalue()


def _stage_run(
    private_root: Path,
    port: object,
    *,
    run_id: str = RUN_ID,
) -> tuple[Path, str]:
    profile, _ = _private_profile(private_root)
    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
        run_id=run_id,
    )
    assert (exit_code, error) == (0, "")
    return private_root / "homelab/runs" / run_id, output["approvalDigest"]


def test_public_surface_and_parser_expose_only_the_lifecycle_facade() -> None:
    assert MODULE.__all__ == [
        "AcceptanceLoginDriver",
        "ExecutionDisposition",
        "ExecutionPort",
        "ExecutionPortError",
        "ExecutionReceipt",
        "ExecutionRequest",
        "ExecutionStep",
        "HomelabProfile",
        "SourceInspector",
        "SourceSnapshot",
        "StagedInput",
        "main",
    ]

    parser = MODULE._build_parser()
    assert vars(
        parser.parse_args(
            [
                "stage",
                "--profile",
                "/root/aileron-private/homelab-profile.json",
                "--commit",
                "a" * 40,
            ]
        )
    ) == {
        "command": "stage",
        "profile": Path("/root/aileron-private/homelab-profile.json"),
        "commit": "a" * 40,
    }
    assert vars(
        parser.parse_args(
            [
                "apply",
                "--run-id",
                "run-0123456789abcdef0123456789abcdef",
                "--approve-digest",
                "b" * 64,
            ]
        )
    ) == {
        "command": "apply",
        "run_id": "run-0123456789abcdef0123456789abcdef",
        "approve_digest": "b" * 64,
    }
    assert vars(
        parser.parse_args(
            ["status", "--run-id", "run-0123456789abcdef0123456789abcdef"]
        )
    ) == {
        "command": "status",
        "run_id": "run-0123456789abcdef0123456789abcdef",
    }

    with pytest.raises(SystemExit):
        parser.parse_args(["deploy"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "apply",
                "--run-id",
                "run-0123456789abcdef0123456789abcdef",
                "--approve-digest",
                "b" * 64,
                "--kubeconfig",
                "/tmp/kubeconfig",
            ]
        )


def test_apply_without_an_injected_port_builds_the_production_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    _, approval_digest = _stage_run(private_root, RecordingPort())
    port = ApprovalPort()
    factory_calls: list[dict] = []

    def factory(**arguments: object) -> object:
        factory_calls.append(arguments)
        return port

    monkeypatch.setattr(
        MODULE.HOMELAB_EXECUTION,
        "create_production_execution_port",
        factory,
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = MODULE.main(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            approval_digest,
        ],
        private_root=private_root,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue())["phase"] == "awaitingApproval"
    assert factory_calls == [
        {
            "facade": MODULE,
            "repository_root": Path(MODULE.__file__).resolve().parents[3],
        }
    ]
    assert all(isinstance(call, MODULE.ExecutionRequest) for call in port.calls)


def test_default_apply_sanitizes_invalid_operation_module_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    run_directory, approval_digest = _stage_run(private_root, RecordingPort())
    journal_path = run_directory / "journal.json"
    staged_journal = journal_path.read_bytes()
    secret = "/private/deployment/homelab_acceptance_operation.py"

    def operation_type(*_args: object, **_kwargs: object) -> None:
        return None

    reset_module = SimpleNamespace(
        ResetOperationRequest=operation_type,
        ResetOperationProfile=operation_type,
        ResetOperationInput=operation_type,
        ResetOperationResult=operation_type,
        ResetOperationError=RuntimeError,
        execute_reset_operation=operation_type,
    )
    invalid_acceptance_module = SimpleNamespace(
        __file__=secret,
        AcceptanceOperationRequest=operation_type,
        AcceptanceOperationResult=operation_type,
        AcceptanceOperationError=RuntimeError,
        BrowserLoginDriver=operation_type,
        WorkspaceIdentity=operation_type,
    )
    modules = {
        "scripts.deploy.rke2.homelab_reset_operation": reset_module,
        "scripts.deploy.rke2.homelab_acceptance_operation": (invalid_acceptance_module),
    }
    imports: list[str] = []

    def import_module(name: str) -> object:
        imports.append(name)
        return modules[name]

    monkeypatch.setattr(
        MODULE.HOMELAB_EXECUTION.importlib,
        "import_module",
        import_module,
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = MODULE.main(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            approval_digest,
        ],
        private_root=private_root,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 75
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ('{"error":{"code":"executionAdapterUnavailable"}}\n')
    assert secret not in stderr.getvalue()
    assert journal_path.read_bytes() == staged_journal
    assert imports == [
        "scripts.deploy.rke2.homelab_reset_operation",
        "scripts.deploy.rke2.homelab_acceptance_operation",
    ]


def test_apply_with_an_injected_port_does_not_build_the_production_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    _, approval_digest = _stage_run(private_root, RecordingPort())
    port = ApprovalPort()

    def unexpected_factory(**_arguments: object) -> object:
        raise AssertionError("injected ports must bypass production preflight")

    monkeypatch.setattr(
        MODULE.HOMELAB_EXECUTION,
        "create_production_execution_port",
        unexpected_factory,
    )

    exit_code, output, error = _invoke(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            approval_digest,
        ],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 0
    assert error == ""
    assert output["phase"] == "awaitingApproval"
    assert all(isinstance(call, MODULE.ExecutionRequest) for call in port.calls)


def test_direct_script_help_runs_outside_the_checkout(tmp_path: Path) -> None:
    completed = subprocess.run(
        ["python3", str(Path(MODULE.__file__).resolve()), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "{stage,apply,status}" in completed.stdout
    assert completed.stderr == ""


def test_profile_schema_and_python_parser_agree_for_supported_identity_modes() -> None:
    schema = json.loads(
        (CONTRACT_DIRECTORY / "homelab-profile.schema.json").read_text(encoding="utf-8")
    )
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema)
    assert schema["definitions"]["registry"]["properties"]["host"]["pattern"] == (
        MODULE.REGISTRY_HOST_PATTERN.pattern
    )
    assert (
        schema["definitions"]["registry"]["properties"]["project"]["pattern"]
        == MODULE.REGISTRY_PROJECT_PATTERN.pattern
    )
    assert (
        schema["definitions"]["endpoints"]["properties"]["platformUrl"]["pattern"]
        == MODULE.PLATFORM_URL_PATTERN.pattern
    )
    assert (
        schema["definitions"]["endpoints"]["properties"]["turnUrl"]["pattern"]
        == MODULE.TURN_URL_PATTERN.pattern
    )
    bundled = json.loads(
        (CONTRACT_DIRECTORY / "homelab-profile.example.json").read_text(
            encoding="utf-8"
        )
    )
    external = json.loads(json.dumps(bundled))
    external["profileId"] = "rke2-207-external"
    external["identity"] = {
        "mode": "externalOidc",
        "issuerUrl": "https://login.example.test/realms/aileron",
        "clientId": "aileron-homelab",
    }
    external["acceptance"] = {
        "loginMode": "files",
        "loginDriver": {
            "kind": "form",
            "usernameSelector": "input[name='username']",
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
    }
    external["privateInputs"].update(
        {
            "identityTlsCertificate": None,
            "identityTlsPrivateKey": None,
            "externalOidcClientSecret": (
                "/root/aileron-private/source/external-oidc-client-secret"
            ),
            "oidcLoginUsername": ("/root/aileron-private/source/oidc-login-username"),
            "oidcLoginPassword": ("/root/aileron-private/source/oidc-login-password"),
        }
    )

    for document, expected_mode, expected_login in (
        (bundled, "bundledKeycloak", "breakGlass"),
        (external, "externalOidc", "files"),
    ):
        assert list(validator.iter_errors(document)) == []
        parsed = MODULE._SourceProfile.from_document(document)
        assert parsed.profile.identity_mode == expected_mode
        assert parsed.profile.acceptance_login_mode == expected_login
        assert all(
            value is None or Path(value).is_absolute()
            for value in document["privateInputs"].values()
        )

    invalid_mode_combinations = []
    external_break_glass = json.loads(json.dumps(external))
    external_break_glass["acceptance"] = {
        **external_break_glass["acceptance"],
        "loginMode": "breakGlass",
    }
    invalid_mode_combinations.append(external_break_glass)
    bundled_with_external_secret = json.loads(json.dumps(bundled))
    bundled_with_external_secret["privateInputs"][
        "externalOidcClientSecret"
    ] = "/root/aileron-private/source/external-oidc-client-secret"
    invalid_mode_combinations.append(bundled_with_external_secret)
    external_without_login = json.loads(json.dumps(external))
    external_without_login["privateInputs"]["oidcLoginPassword"] = None
    invalid_mode_combinations.append(external_without_login)
    bundled_without_admin_console = json.loads(json.dumps(bundled))
    bundled_without_admin_console["identity"].pop("adminConsoleUrl")
    invalid_mode_combinations.append(bundled_without_admin_console)
    bundled_with_insecure_admin_console = json.loads(json.dumps(bundled))
    bundled_with_insecure_admin_console["identity"][
        "adminConsoleUrl"
    ] = "http://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
    invalid_mode_combinations.append(bundled_with_insecure_admin_console)
    external_with_admin_console = json.loads(json.dumps(external))
    external_with_admin_console["identity"][
        "adminConsoleUrl"
    ] = "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
    invalid_mode_combinations.append(external_with_admin_console)

    invalid_registry = json.loads(json.dumps(bundled))
    invalid_registry["registry"]["host"] = "https://harbor.rke.soez.tw"
    invalid_mode_combinations.append(invalid_registry)
    for registry_host in (
        "harbor.rke.soez.tw:70000",
        "harbor.rke.soez.tw.",
        "harbor..rke.soez.tw",
    ):
        invalid_registry_host = json.loads(json.dumps(bundled))
        invalid_registry_host["registry"]["host"] = registry_host
        invalid_mode_combinations.append(invalid_registry_host)
    invalid_platform_origin = json.loads(json.dumps(bundled))
    invalid_platform_origin["endpoints"][
        "platformUrl"
    ] = "https://aileron.apps.rke.soez.tw/path"
    invalid_mode_combinations.append(invalid_platform_origin)
    invalid_platform_hostname = json.loads(json.dumps(bundled))
    invalid_platform_hostname["endpoints"][
        "platformUrl"
    ] = "https://aileron_apps.rke.soez.tw"
    invalid_mode_combinations.append(invalid_platform_hostname)
    invalid_turn_url = json.loads(json.dumps(bundled))
    invalid_turn_url["endpoints"]["turnUrl"] = "turn:turn.apps.rke.soez.tw:70000"
    invalid_mode_combinations.append(invalid_turn_url)
    invalid_private_path = json.loads(json.dumps(bundled))
    invalid_private_path["privateInputs"]["registryCa"] = "relative/registry-ca.crt"
    invalid_mode_combinations.append(invalid_private_path)

    for document in invalid_mode_combinations:
        assert list(validator.iter_errors(document))
        with pytest.raises(MODULE._LifecycleError):
            MODULE._SourceProfile.from_document(document)


def test_profile_requires_an_exact_identity_specific_login_driver() -> None:
    bundled = {
        "schemaVersion": "aileron-homelab-staged-profile/v1",
        "profileId": "rke2-207",
        "context": "rke",
        "registry": {"host": "harbor.example.test", "project": "library"},
        "endpoints": {
            "platformUrl": "https://platform.example.test",
            "turnUrl": "turn:turn.example.test:3478",
        },
        "identity": {
            "mode": "bundledKeycloak",
            "issuerUrl": "https://keycloak.apps.rke.soez.tw/realms/aileron",
            "adminConsoleUrl": (
                "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
            ),
            "clientId": "aileron-frontend",
        },
        "acceptance": {
            "loginMode": "breakGlass",
            "loginDriver": {"kind": "keycloak"},
        },
        "installationIntent": "newInstallation",
    }

    parsed = MODULE.HomelabProfile.from_document(bundled)

    assert isinstance(parsed.acceptance_login_driver, MODULE.AcceptanceLoginDriver)
    assert parsed.acceptance_login_driver.kind == "keycloak"
    assert parsed.admin_console_url == (
        "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
    )
    assert parsed.to_document() == bundled

    for invalid_admin_identity in (
        {
            key: value
            for key, value in bundled["identity"].items()
            if key != "adminConsoleUrl"
        },
        {
            **bundled["identity"],
            "adminConsoleUrl": "http://keycloak-admin.example.test/",
        },
        {
            **bundled["identity"],
            "adminConsoleUrl": "https://admin:secret@example.test/",
        },
    ):
        invalid = json.loads(json.dumps(bundled))
        invalid["identity"] = invalid_admin_identity
        with pytest.raises(MODULE._LifecycleError, match="profileIdentityInvalid"):
            MODULE.HomelabProfile.from_document(invalid)

    external = json.loads(json.dumps(bundled))
    external["identity"] = {
        "mode": "externalOidc",
        "issuerUrl": "https://identity.example.test/realms/aileron",
        "clientId": "aileron",
    }
    external["acceptance"] = {
        "loginMode": "files",
        "loginDriver": {
            "kind": "form",
            "usernameSelector": "input[name='username']",
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
    }
    external_with_admin = json.loads(json.dumps(external))
    external_with_admin["identity"][
        "adminConsoleUrl"
    ] = "https://keycloak-admin.example.test/admin/master/console/"
    with pytest.raises(MODULE._LifecycleError, match="profileIdentityInvalid"):
        MODULE.HomelabProfile.from_document(external_with_admin)
    parsed_external = MODULE.HomelabProfile.from_document(external)
    assert parsed_external.to_document() == external

    for invalid_driver in (
        {"kind": "keycloak"},
        {
            "kind": "form",
            "usernameSelector": "input\n[name='username']",
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
        {
            "kind": "form",
            "usernameSelector": "x" * 257,
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
        {
            "kind": "form",
            "usernameSelector": " input[name='username']",
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
    ):
        invalid = json.loads(json.dumps(external))
        invalid["acceptance"]["loginDriver"] = invalid_driver
        with pytest.raises(MODULE._LifecycleError) as caught:
            MODULE.HomelabProfile.from_document(invalid)
        assert caught.value.code == "profileAcceptanceInvalid"


def test_stage_pins_a_typed_plan_and_journal_without_execution(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    profile, profile_content = _private_profile(private_root)
    port = RecordingPort()
    source_inspector = FixedSourceInspector()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
        source_inspector=source_inspector,
    )

    run_directory = private_root / "homelab/runs" / RUN_ID
    plan_path = run_directory / "plan.json"
    journal_path = run_directory / "journal.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    plan_digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()

    assert exit_code == 0
    assert error == ""
    assert output == {
        "approvalDigest": plan_digest,
        "phase": "staged",
        "planDigest": plan_digest,
        "runId": RUN_ID,
    }
    source_profile = json.loads(profile_content)
    assert set(plan) == {
        "schemaVersion",
        "runId",
        "commit",
        "profile",
        "sourceProfileSha256",
        "privateInputs",
        "steps",
    }
    assert plan["schemaVersion"] == "aileron-homelab-run-plan/v1"
    assert plan["runId"] == RUN_ID
    assert plan["commit"] == COMMIT
    assert plan["profile"] == _staged_profile_document(source_profile)
    assert plan["sourceProfileSha256"] == hashlib.sha256(profile_content).hexdigest()
    assert plan["steps"] == STEP_IDS
    assert journal == {
        "schemaVersion": "aileron-homelab-run-journal/v1",
        "runId": RUN_ID,
        "planDigest": plan_digest,
        "phase": "staged",
        "requiredApprovalDigest": plan_digest,
        "lastApprovedDigest": None,
        "revision": 0,
        "steps": [
            {
                "id": step,
                "status": "pending",
                "attempts": 0,
                "receiptDigest": None,
                "lastErrorCode": None,
            }
            for step in STEP_IDS
        ],
    }
    assert (run_directory / "profile.json").read_bytes() == profile_content
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in (run_directory / "profile.json", plan_path, journal_path)
    )
    global_apply_lock = private_root / "homelab/.apply.lock"
    assert global_apply_lock.is_dir()
    assert global_apply_lock.stat().st_mode & 0o777 == 0o700
    assert not (run_directory / ".apply.lock").exists()
    assert run_directory.stat().st_mode & 0o777 == 0o700
    assert port.calls == []
    assert source_inspector.calls == 1


def test_parallel_stages_share_one_write_once_global_execution_lock(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    profile, _ = _private_profile(private_root)
    start = threading.Barrier(3)
    results: dict[str, tuple[int, dict, str]] = {}

    def stage(run_id: str) -> None:
        start.wait()
        results[run_id] = _invoke(
            ["stage", "--profile", str(profile), "--commit", COMMIT],
            private_root=private_root,
            port=RecordingPort(),
            run_id=run_id,
        )

    first = threading.Thread(target=stage, args=(RUN_ID,))
    second = threading.Thread(target=stage, args=(SECOND_RUN_ID,))
    first.start()
    second.start()
    start.wait()
    first.join()
    second.join()

    assert {run_id: result[0] for run_id, result in results.items()} == {
        RUN_ID: 0,
        SECOND_RUN_ID: 0,
    }
    global_lock = private_root / "homelab/.apply.lock"
    lock_inode = global_lock.stat().st_ino

    exit_code, _, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=RecordingPort(),
        run_id=THIRD_RUN_ID,
    )

    assert (exit_code, error) == (0, "")
    assert global_lock.is_dir()
    assert global_lock.stat().st_ino == lock_inode
    assert {path.name for path in (private_root / "homelab/runs").iterdir()} == {
        RUN_ID,
        SECOND_RUN_ID,
        THIRD_RUN_ID,
    }
    assert all(
        not (private_root / "homelab/runs" / run_id / ".apply.lock").exists()
        for run_id in (RUN_ID, SECOND_RUN_ID, THIRD_RUN_ID)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda profile: profile.update({"kubeconfig": "/tmp/kubeconfig"}),
        lambda profile: profile.pop("installationIntent"),
        lambda profile: profile["identity"].update(
            {"clientSecret": "must-not-be-accepted"}
        ),
        lambda profile: profile.update({"installationIntent": "upgrade"}),
        lambda profile: profile["identity"].update(
            {"issuerUrl": "http://issuer.invalid/realm"}
        ),
    ],
)
def test_stage_rejects_untyped_or_secret_bearing_profiles_before_publication(
    tmp_path: Path,
    mutate: object,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    mutate(document)
    profile, _ = _private_profile(private_root, document)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error)["error"]["code"] in {
        "profileShapeInvalid",
        "profileIdentityInvalid",
        "installationIntentInvalid",
    }
    assert not (private_root / "homelab").exists()
    assert port.calls == []


@pytest.mark.parametrize(
    ("section", "field", "value", "error_code"),
    [
        ("registry", "host", "https://harbor.rke.soez.tw", "profileRegistryInvalid"),
        ("registry", "host", "harbor/rke", "profileRegistryInvalid"),
        ("registry", "host", "harbor.rke.soez.tw:70000", "profileRegistryInvalid"),
        ("registry", "host", "harbor.rke.soez.tw.", "profileRegistryInvalid"),
        ("registry", "host", "harbor..rke.soez.tw", "profileRegistryInvalid"),
        ("registry", "project", "../library", "profileRegistryInvalid"),
        ("registry", "project", "Library", "profileRegistryInvalid"),
        (
            "endpoints",
            "platformUrl",
            "http://aileron.apps.rke.soez.tw",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "platformUrl",
            "https://aileron_apps.rke.soez.tw",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "platformUrl",
            "https://user@aileron.apps.rke.soez.tw",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "platformUrl",
            "https://aileron.apps.rke.soez.tw/path",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "platformUrl",
            "https://aileron.apps.rke.soez.tw?debug=true",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "turnUrl",
            "https://turn.apps.rke.soez.tw",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "turnUrl",
            "turn:turn.apps.rke.soez.tw:70000",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "turnUrl",
            "turn:user@turn.apps.rke.soez.tw:3478",
            "profileEndpointsInvalid",
        ),
        (
            "endpoints",
            "turnUrl",
            "turn:turn.apps.rke.soez.tw:3478?transport=http",
            "profileEndpointsInvalid",
        ),
    ],
)
def test_stage_rejects_noncanonical_deployment_targets_before_publication(
    tmp_path: Path,
    section: str,
    field: str,
    value: str,
    error_code: str,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    document[section][field] = value
    profile, _ = _private_profile(private_root, document)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": error_code}}
    assert not (private_root / "homelab").exists()
    assert port.calls == []


@pytest.mark.parametrize(
    "value", ["", "relative/input", " /private/input", "/bad\x00input"]
)
def test_stage_rejects_noncanonical_private_input_references_before_publication(
    tmp_path: Path,
    value: str,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    document["privateInputs"]["registryCa"] = value
    profile, _ = _private_profile(private_root, document)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": "profilePrivateInputsInvalid"}}
    assert not (private_root / "homelab").exists()
    assert port.calls == []


@pytest.mark.parametrize(
    ("inspector", "error_code"),
    [
        (FixedSourceInspector(clean=False), "sourceCheckoutDirty"),
        (FixedSourceInspector(commit="d" * 40), "sourceCommitMismatch"),
    ],
)
def test_stage_rejects_dirty_or_different_source_before_publication(
    tmp_path: Path,
    inspector: object,
    error_code: str,
) -> None:
    private_root = _directory(tmp_path / "private")
    profile, _ = _private_profile(private_root)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
        source_inspector=inspector,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": error_code}}
    assert not (private_root / "homelab").exists()
    assert port.calls == []


def test_git_source_inspector_uses_fixed_read_only_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append({"command": command, **kwargs})
        stdout = COMMIT + "\n" if "rev-parse" in command else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", run)

    snapshot = MODULE._GitSourceInspector(Path("/repo")).inspect()

    assert snapshot == MODULE.SourceSnapshot(head_commit=COMMIT, clean=True)
    assert [call["command"] for call in calls] == [
        [
            "git",
            "--no-optional-locks",
            "-C",
            "/repo",
            "rev-parse",
            "--verify",
            "HEAD",
        ],
        [
            "git",
            "--no-optional-locks",
            "-C",
            "/repo",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
    ]
    assert all(call["check"] is False for call in calls)
    assert all(call["stderr"] is subprocess.DEVNULL for call in calls)


def test_apply_requires_each_current_digest_and_resumes_after_approval_gate(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    port = ApprovalPort()
    run_directory, plan_digest = _stage_run(private_root, port)
    journal_path = run_directory / "journal.json"
    staged_journal = journal_path.read_bytes()

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", "c" * 64],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 64
    assert output == {}
    assert json.loads(error) == {"error": {"code": "approvalDigestMismatch"}}
    assert journal_path.read_bytes() == staged_journal
    assert port.calls == []

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=port,
    )

    assert (exit_code, error) == (0, "")
    assert output == {
        "phase": "awaitingApproval",
        "requiredApprovalDigest": RESET_APPROVAL_DIGEST,
        "runId": RUN_ID,
    }
    assert [request.step.value for request in port.calls] == STEP_IDS[:3]
    assert all(request.approval_digest == plan_digest for request in port.calls)
    awaiting_journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert awaiting_journal["phase"] == "awaitingApproval"
    assert awaiting_journal["requiredApprovalDigest"] == RESET_APPROVAL_DIGEST
    assert awaiting_journal["lastApprovedDigest"] == plan_digest
    assert [step["status"] for step in awaiting_journal["steps"]] == [
        "completed",
        "completed",
        "awaitingApproval",
        "pending",
        "pending",
    ]

    before_status = journal_path.read_bytes()
    exit_code, status, error = _invoke(
        ["status", "--run-id", RUN_ID],
        private_root=private_root,
        port=port,
    )
    assert (exit_code, error) == (0, "")
    assert status == awaiting_journal
    assert journal_path.read_bytes() == before_status
    assert len(port.calls) == 3

    exit_code, output, error = _invoke(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            RESET_APPROVAL_DIGEST,
        ],
        private_root=private_root,
        port=port,
    )

    assert (exit_code, error) == (0, "")
    assert output == {
        "phase": "succeeded",
        "requiredApprovalDigest": None,
        "runId": RUN_ID,
    }
    assert [request.step.value for request in port.calls] == [
        *STEP_IDS[:3],
        *STEP_IDS[2:],
    ]
    assert port.calls[3].approval_digest == RESET_APPROVAL_DIGEST
    completed_journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert completed_journal["phase"] == "succeeded"
    assert completed_journal["requiredApprovalDigest"] is None
    assert completed_journal["lastApprovedDigest"] == RESET_APPROVAL_DIGEST
    assert [step["status"] for step in completed_journal["steps"]] == [
        "completed"
    ] * len(STEP_IDS)
    assert completed_journal["steps"][2]["attempts"] == 2

    completed_bytes = journal_path.read_bytes()
    call_count = len(port.calls)
    exit_code, output, error = _invoke(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            RESET_APPROVAL_DIGEST,
        ],
        private_root=private_root,
        port=port,
    )
    assert (exit_code, error) == (0, "")
    assert output["phase"] == "succeeded"
    assert journal_path.read_bytes() == completed_bytes
    assert len(port.calls) == call_count


def test_global_execution_lock_serializes_different_runs_while_status_stays_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    port = BlockingFirstPort()
    _, first_plan_digest = _stage_run(private_root, port)
    _, second_plan_digest = _stage_run(
        private_root,
        port,
        run_id=SECOND_RUN_ID,
    )
    approval_by_run = {
        RUN_ID: first_plan_digest,
        SECOND_RUN_ID: second_plan_digest,
    }
    real_flock = MODULE.fcntl.flock
    execution_attempts = 0
    second_execution_attempted = threading.Event()

    def observable_flock(descriptor: int, operation: int) -> None:
        nonlocal execution_attempts
        target = MODULE.os.readlink(f"/proc/self/fd/{descriptor}")
        if operation == MODULE.fcntl.LOCK_SH:
            real_flock(descriptor, operation | MODULE.fcntl.LOCK_NB)
            return
        if operation == MODULE.fcntl.LOCK_EX and target.endswith("/.apply.lock"):
            execution_attempts += 1
            if execution_attempts == 2:
                second_execution_attempted.set()
        real_flock(descriptor, operation)

    monkeypatch.setattr(MODULE.fcntl, "flock", observable_flock)
    results: dict[str, tuple[int, dict, str]] = {}
    first_done = threading.Event()
    second_done = threading.Event()

    def apply(name: str, run_id: str, done: threading.Event) -> None:
        try:
            results[name] = _invoke(
                [
                    "apply",
                    "--run-id",
                    run_id,
                    "--approve-digest",
                    approval_by_run[run_id],
                ],
                private_root=private_root,
                port=port,
            )
        finally:
            done.set()

    first = threading.Thread(target=apply, args=("first", RUN_ID, first_done))
    second = threading.Thread(
        target=apply,
        args=("second", SECOND_RUN_ID, second_done),
    )
    first.start()
    port.entered.wait()
    try:
        status_exit, status, status_error = _invoke(
            ["status", "--run-id", RUN_ID],
            private_root=private_root,
            port=port,
        )
        assert (status_exit, status_error) == (0, "")
        assert status["phase"] == "applying"
        assert status["steps"][0] == {
            "id": "newInstallation",
            "status": "started",
            "attempts": 1,
            "receiptDigest": None,
            "lastErrorCode": None,
        }
        second_status_exit, second_status, second_status_error = _invoke(
            ["status", "--run-id", SECOND_RUN_ID],
            private_root=private_root,
            port=port,
        )
        assert (second_status_exit, second_status_error) == (0, "")
        assert second_status["phase"] == "staged"
        assert second_status["steps"][0]["status"] == "pending"

        second.start()
        second_execution_attempted.wait()
        assert not second_done.is_set()
        assert len(port.calls) == 1
    finally:
        port.release.set()
        first.join()
        if second.ident is not None:
            second.join()

    assert first_done.is_set()
    assert second_done.is_set()
    assert results["first"] == (
        0,
        {
            "phase": "succeeded",
            "requiredApprovalDigest": None,
            "runId": RUN_ID,
        },
        "",
    )
    assert results["second"] == (
        0,
        {
            "phase": "succeeded",
            "requiredApprovalDigest": None,
            "runId": SECOND_RUN_ID,
        },
        "",
    )
    assert [request.run_id for request in port.calls] == [
        *([RUN_ID] * len(STEP_IDS)),
        *([SECOND_RUN_ID] * len(STEP_IDS)),
    ]


def test_apply_rejects_a_replaced_global_execution_lock_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    _, plan_digest = _stage_run(private_root, RecordingPort())
    global_lock = private_root / "homelab/.apply.lock"
    replaced_lock = private_root / "homelab/.apply.lock-replaced"
    real_open = MODULE.os.open
    replaced = False

    def replacing_open(path: object, flags: int, *args: object) -> int:
        nonlocal replaced
        descriptor = real_open(path, flags, *args)
        if Path(path) == global_lock and not replaced:
            replaced = True
            global_lock.rename(replaced_lock)
            global_lock.mkdir(mode=0o700)
        return descriptor

    monkeypatch.setattr(MODULE.os, "open", replacing_open)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": "executionLockInvalid"}}
    assert replaced
    assert global_lock.stat().st_ino != replaced_lock.stat().st_ino
    assert port.calls == []


@pytest.mark.parametrize("drift", ["revision", "attempt"])
def test_apply_refuses_to_overwrite_a_changed_started_checkpoint(
    tmp_path: Path,
    drift: str,
) -> None:
    private_root = _directory(tmp_path / "private")
    run_directory, plan_digest = _stage_run(private_root, RecordingPort())
    journal_path = run_directory / "journal.json"
    drifted_content = b""

    class DriftingPort:
        def execute(self, request: object) -> object:
            nonlocal drifted_content
            assert isinstance(request, MODULE.ExecutionRequest)
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            if drift == "revision":
                journal["revision"] += 1
            else:
                journal["steps"][0]["attempts"] += 1
            drifted_content = (
                json.dumps(journal, separators=(",", ":"), sort_keys=True) + "\n"
            ).encode()
            journal_path.write_bytes(drifted_content)
            journal_path.chmod(0o600)
            return MODULE.ExecutionReceipt(
                step=request.step,
                disposition=MODULE.ExecutionDisposition.COMPLETED,
                digest="f" * 64,
            )

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=DriftingPort(),
    )

    assert exit_code == 75
    assert output == {}
    assert json.loads(error) == {"error": {"code": "executionCheckpointChanged"}}
    assert journal_path.read_bytes() == drifted_content


def test_apply_resumes_forward_from_a_durable_started_step(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    port = FailOncePort()
    run_directory, plan_digest = _stage_run(private_root, port)

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 75
    assert output == {}
    assert json.loads(error) == {"error": {"code": "installUnavailable"}}
    failed_journal = json.loads(
        (run_directory / "journal.json").read_text(encoding="utf-8")
    )
    assert failed_journal["phase"] == "failed"
    assert [step["status"] for step in failed_journal["steps"]] == [
        "completed",
        "completed",
        "completed",
        "started",
        "pending",
    ]
    assert failed_journal["steps"][3]["lastErrorCode"] == "installUnavailable"

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=port,
    )

    assert (exit_code, error) == (0, "")
    assert output["phase"] == "succeeded"
    assert [request.step.value for request in port.calls] == [
        *STEP_IDS[:4],
        *STEP_IDS[3:],
    ]
    assert (
        json.loads((run_directory / "journal.json").read_text(encoding="utf-8"))[
            "steps"
        ][3]["attempts"]
        == 2
    )


def test_apply_rejects_noncanonical_staged_plan_without_execution(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    port = ApprovalPort()
    run_directory, plan_digest = _stage_run(private_root, port)
    plan_path = run_directory / "plan.json"
    journal_path = run_directory / "journal.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    plan_path.chmod(0o600)
    journal_before = journal_path.read_bytes()

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", plan_digest],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": "planEncodingInvalid"}}
    assert journal_path.read_bytes() == journal_before
    assert port.calls == []


def test_stage_snapshots_the_complete_profile_and_all_private_inputs(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, source_contents = _full_private_input_profile(private_root)
    profile, profile_content = _private_profile(private_root, document)
    flatten_calls: list[tuple[list[str], dict[str, str]]] = []

    def flatten_kubeconfig(command: list[str], *, environment: dict[str, str]) -> str:
        flatten_calls.append((command, environment))
        raw_snapshot = Path(command[command.index("--kubeconfig") + 1])
        return raw_snapshot.read_text(encoding="utf-8")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = MODULE.main(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        execution_port=RecordingPort(),
        private_root=private_root,
        stdout=stdout,
        stderr=stderr,
        run_id_factory=lambda: RUN_ID,
        source_inspector=FixedSourceInspector(),
        kubeconfig_runner=flatten_kubeconfig,
    )

    assert (exit_code, stderr.getvalue()) == (0, "")
    run_directory = private_root / "homelab/runs" / RUN_ID
    plan = json.loads((run_directory / "plan.json").read_text(encoding="utf-8"))
    assert plan["sourceProfileSha256"] == hashlib.sha256(profile_content).hexdigest()
    assert plan["profile"] == {
        "schemaVersion": "aileron-homelab-staged-profile/v1",
        "profileId": "rke2-207",
        "context": "rke",
        "registry": {"host": "harbor.rke.soez.tw", "project": "library"},
        "endpoints": {
            "platformUrl": "https://aileron.apps.rke.soez.tw",
            "turnUrl": "turn:turn.apps.rke.soez.tw:3478",
        },
        "identity": document["identity"],
        "acceptance": {
            "loginMode": "breakGlass",
            "loginDriver": {"kind": "keycloak"},
        },
        "installationIntent": "newInstallation",
    }
    records = {record["name"]: record for record in plan["privateInputs"]}
    assert set(records) == {
        "kubeconfigRaw",
        "kubeconfig",
        *(set(source_contents) - {"kubeconfig"}),
    }
    for name, record in records.items():
        snapshot = run_directory / record["snapshot"]
        assert snapshot.is_file()
        assert snapshot.stat().st_mode & 0o777 == 0o600
        assert record["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
        assert record["sizeBytes"] == len(snapshot.read_bytes())
        assert str(private_root / "inputs") not in json.dumps(record)
        if name not in {"kubeconfigRaw", "kubeconfig"}:
            assert snapshot.read_bytes() == source_contents[name]
    assert records["kubeconfigRaw"]["snapshot"] == "inputs/kubeconfig.raw"
    assert records["kubeconfig"]["snapshot"] == "inputs/kubeconfig"
    assert records["harborDockerconfig"]["snapshot"] == "inputs/docker/config.json"
    assert (run_directory / "inputs/docker").stat().st_mode & 0o777 == 0o700
    assert records["registryCa"]["snapshot"] == "inputs/registry-ca.crt"
    assert records["appsTlsCa"]["snapshot"] == "inputs/apps-ca.crt"
    assert records["oidcCa"]["snapshot"] == "inputs/oidc-ca.crt"
    assert len(flatten_calls) == 1
    flatten_command, flatten_environment = flatten_calls[0]
    assert flatten_command[:2] == ["kubectl", "--kubeconfig"]
    assert Path(flatten_command[2]).name == "kubeconfig.raw"
    assert Path(flatten_command[2]).parent.name == "inputs"
    assert Path(flatten_command[2]).parents[1].name.startswith(".stage-")
    assert flatten_command[3:] == [
        "--context",
        "rke",
        "config",
        "view",
        "--raw",
        "--flatten",
        "--minify",
        "--output=json",
    ]
    assert flatten_environment == {"KUBECONFIG": flatten_command[2]}


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("externalBreakGlass", "profileAcceptanceInvalid"),
        ("bundledMissingIdentityKey", "profilePrivateInputModeInvalid"),
        ("filesMissingLoginPassword", "profilePrivateInputModeInvalid"),
    ],
)
def test_stage_rejects_invalid_identity_and_login_input_combinations(
    tmp_path: Path,
    case: str,
    error_code: str,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    if case == "externalBreakGlass":
        document["identity"] = {
            "mode": "externalOidc",
            "issuerUrl": "https://login.example.test/issuer",
            "clientId": "external-client",
        }
        _set_private_input(
            document,
            root=private_root,
            name="identityTlsCertificate",
            content=None,
        )
        _set_private_input(
            document,
            root=private_root,
            name="identityTlsPrivateKey",
            content=None,
        )
        _set_private_input(
            document,
            root=private_root,
            name="externalOidcClientSecret",
            content=b"external-secret\n",
        )
    elif case == "bundledMissingIdentityKey":
        _set_private_input(
            document,
            root=private_root,
            name="identityTlsPrivateKey",
            content=None,
        )
    else:
        document["acceptance"] = {
            "loginMode": "files",
            "loginDriver": {"kind": "keycloak"},
        }
        _set_private_input(
            document,
            root=private_root,
            name="oidcLoginUsername",
            content=b"future-directory-user\n",
        )
    profile, _ = _private_profile(private_root, document)

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=RecordingPort(),
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": error_code}}
    assert not (private_root / "homelab").exists()


def test_apply_exposes_only_run_scoped_snapshots_for_external_file_login(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    document["identity"] = {
        "mode": "externalOidc",
        "issuerUrl": "https://login.example.test/issuer",
        "clientId": "external-client",
    }
    document["acceptance"] = {
        "loginMode": "files",
        "loginDriver": {
            "kind": "form",
            "usernameSelector": "input[name='username']",
            "passwordSelector": "input[name='password']",
            "submitSelector": "button[type='submit']",
            "errorSelector": "[role='alert']",
        },
    }
    _set_private_input(
        document,
        root=private_root,
        name="identityTlsCertificate",
        content=None,
    )
    _set_private_input(
        document,
        root=private_root,
        name="identityTlsPrivateKey",
        content=None,
    )
    _set_private_input(
        document,
        root=private_root,
        name="externalOidcClientSecret",
        content=b"external-secret\n",
    )
    _set_private_input(
        document,
        root=private_root,
        name="oidcLoginUsername",
        content=b"future-directory-user\n",
    )
    _set_private_input(
        document,
        root=private_root,
        name="oidcLoginPassword",
        content=b"future-directory-password\n",
    )
    profile, _ = _private_profile(private_root, document)
    port = CapturePort()

    exit_code, staged, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
    )
    assert (exit_code, error) == (0, "")
    original_paths = {
        Path(value) for value in document["privateInputs"].values() if value is not None
    }
    for path in original_paths:
        path.write_bytes(b"changed-after-stage\n")
        path.chmod(0o600)

    exit_code, output, error = _invoke(
        [
            "apply",
            "--run-id",
            RUN_ID,
            "--approve-digest",
            staged["approvalDigest"],
        ],
        private_root=private_root,
        port=port,
    )

    assert (exit_code, error) == (0, "")
    assert output["phase"] == "awaitingApproval"
    assert len(port.calls) == 1
    request = port.calls[0]
    assert request.profile.identity_mode == "externalOidc"
    assert request.profile.acceptance_login_mode == "files"
    assert {item.name for item in request.inputs} == {
        "kubeconfig",
        "backendExecutionProfile",
        "harborDockerconfig",
        "registryCa",
        "appsTlsCertificate",
        "appsTlsPrivateKey",
        "appsTlsCa",
        "oidcCa",
        "externalOidcClientSecret",
        "oidcLoginUsername",
        "oidcLoginPassword",
    }
    run_directory = private_root / "homelab/runs" / RUN_ID
    assert all(
        item.path.is_relative_to(run_directory / "inputs") for item in request.inputs
    )
    assert all(item.path not in original_paths for item in request.inputs)
    assert all(item.name != "kubeconfigRaw" for item in request.inputs)
    assert (
        next(item.path for item in request.inputs if item.name == "harborDockerconfig")
        == run_directory / "inputs/docker/config.json"
    )
    assert (
        next(
            item.path
            for item in request.inputs
            if item.name == "externalOidcClientSecret"
        ).read_bytes()
        == b"external-secret\n"
    )
    assert "ldap" not in json.dumps(request.profile.to_document()).lower()


def test_stage_rejects_an_invalid_private_input_without_publishing_the_run(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    document, _ = _full_private_input_profile(private_root)
    registry_ca = Path(document["privateInputs"]["registryCa"])
    registry_ca.chmod(0o644)
    profile, _ = _private_profile(private_root, document)
    port = RecordingPort()

    exit_code, output, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": "privateInputSnapshotFailed"}}
    runs = private_root / "homelab/runs"
    assert runs.is_dir()
    assert list(runs.iterdir()) == []
    assert port.calls == []


def test_stage_fsyncs_nested_private_input_directories_and_run_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = _directory(tmp_path / "private")
    profile, _ = _private_profile(private_root)
    synchronized: list[str] = []
    real_fsync = MODULE.os.fsync

    def fsync(descriptor: int) -> None:
        synchronized.append(MODULE.os.readlink(f"/proc/self/fd/{descriptor}"))
        real_fsync(descriptor)

    monkeypatch.setattr(MODULE.os, "fsync", fsync)

    exit_code, _, error = _invoke(
        ["stage", "--profile", str(profile), "--commit", COMMIT],
        private_root=private_root,
        port=RecordingPort(),
    )

    assert (exit_code, error) == (0, "")
    assert any(path.endswith("/inputs/docker/config.json") for path in synchronized)
    assert any(path.endswith("/inputs/docker") for path in synchronized)
    assert str(private_root / "homelab/runs") in synchronized


def test_apply_rejects_a_tampered_snapshot_selector_without_execution(
    tmp_path: Path,
) -> None:
    private_root = _directory(tmp_path / "private")
    port = ApprovalPort()
    run_directory, approval_digest = _stage_run(private_root, port)
    plan_path = run_directory / "plan.json"
    journal_path = run_directory / "journal.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["privateInputs"][0]["snapshot"] = "../../outside"
    plan_path.write_text(
        json.dumps(plan, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    plan_path.chmod(0o600)
    journal_before = journal_path.read_bytes()

    exit_code, output, error = _invoke(
        ["apply", "--run-id", RUN_ID, "--approve-digest", approval_digest],
        private_root=private_root,
        port=port,
    )

    assert exit_code == 65
    assert output == {}
    assert json.loads(error) == {"error": {"code": "planPrivateInputInvalid"}}
    assert journal_path.read_bytes() == journal_before
    assert port.calls == []
