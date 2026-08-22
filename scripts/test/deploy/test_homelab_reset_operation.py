"""HomeLab reset deep-operation contract tests."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.deploy.rke2 import homelab_reset_operation as MODULE

COMMIT = "a" * 40
RUN_ID = "run-0123456789abcdef0123456789abcdef"
PLAN_DIGEST = "b" * 64
SNAPSHOT_DIGEST = "c" * 64
REPORT_DIGEST = "d" * 64

BASE_INPUT_PATHS = {
    "kubeconfig": "inputs/kubeconfig",
    "backendExecutionProfile": "inputs/backend-execution-profile.json",
    "harborDockerconfig": "inputs/docker/config.json",
    "registryCa": "inputs/registry-ca.crt",
    "appsTlsCertificate": "inputs/apps-tls.crt",
    "appsTlsPrivateKey": "inputs/apps-tls.key",
    "appsTlsCa": "inputs/apps-ca.crt",
    "oidcCa": "inputs/oidc-ca.crt",
}
BUNDLED_INPUT_PATHS = {
    "identityTlsCertificate": "inputs/identity-tls.crt",
    "identityTlsPrivateKey": "inputs/identity-tls.key",
}
EXTERNAL_INPUT_PATHS = {
    "externalOidcClientSecret": "inputs/external-oidc-client-secret",
}
LOGIN_INPUT_PATHS = {
    "oidcLoginUsername": "inputs/oidc-login-username",
    "oidcLoginPassword": "inputs/oidc-login-password",
}
DATA_SERVICE_INPUT_PATHS = {
    "coreDataServiceValues": "inputs/core-data-service-values.yaml",
    "identityDataServiceValues": "inputs/identity-data-service-values.yaml",
    "platformDatabaseUrl": "inputs/platform-database-url",
    "platformDatabaseCa": "inputs/platform-database-ca.crt",
    "redisGeneralUrl": "inputs/redis-general-url",
    "redisJobQueueUrl": "inputs/redis-job-queue-url",
    "redisJobResultUrl": "inputs/redis-job-result-url",
    "redisGeneralCa": "inputs/redis-general-ca.crt",
    "redisJobQueueCa": "inputs/redis-job-queue-ca.crt",
    "redisJobResultCa": "inputs/redis-job-result-ca.crt",
    "identityDatabaseUsername": "inputs/identity-database-username",
    "identityDatabasePassword": "inputs/identity-database-password",
    "identityDatabaseCa": "inputs/identity-database-ca.crt",
}


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


class RecordingSafety:
    def __init__(self, *, snapshot_digest: str | None = None) -> None:
        self.calls: list[object] = []
        self.snapshot_digest = snapshot_digest
        self.prerequisite_results = [
            MODULE.ResetPrerequisiteDisposition.PREPARATION_REQUIRED,
            MODULE.ResetPrerequisiteDisposition.READY,
            MODULE.ResetPrerequisiteDisposition.READY,
        ]

    def validate_staged_inputs(self, request: MODULE.ResetOperationRequest) -> None:
        self.calls.append("validateInputs")

    def resume_pre_reset_snapshot(
        self, request: MODULE.ResetOperationRequest
    ) -> str | None:
        self.calls.append("resumeSnapshot")
        return self.snapshot_digest

    def prepare_backend_attestor(
        self, request: MODULE.ResetOperationRequest, *, apply: bool
    ) -> MODULE.ResetPrerequisiteDisposition:
        self.calls.append(("prepareBackendAttestor", apply))
        return self.prerequisite_results.pop(0)

    def ensure_existing_namespaces(
        self, request: MODULE.ResetOperationRequest, *, existing_only: bool
    ) -> None:
        self.calls.append(("ensureNamespaces", existing_only))

    def create_pre_reset_snapshot(self, request: MODULE.ResetOperationRequest) -> str:
        self.calls.append("createSnapshot")
        self.snapshot_digest = SNAPSHOT_DIGEST
        return SNAPSHOT_DIGEST

    def validate_pre_reset_snapshot(
        self, request: MODULE.ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        self.calls.append(("validateSnapshot", snapshot_digest))

    def ensure_causal_root(
        self,
        request: MODULE.ResetOperationRequest,
        *,
        section: str,
        snapshot_digest: str,
    ) -> str:
        self.calls.append(("ensureRoot", section, snapshot_digest))
        return "e" * 64 if section == "suites" else "f" * 64

    def execute_approved_reset(
        self, request: MODULE.ResetOperationRequest, *, snapshot_digest: str
    ) -> None:
        self.calls.append(("executeReset", snapshot_digest))

    def ensure_post_reset_report(
        self, request: MODULE.ResetOperationRequest, *, snapshot_digest: str
    ) -> str:
        self.calls.append(("postReset", snapshot_digest))
        return REPORT_DIGEST


def _request(
    tmp_path: Path,
    *,
    approval_digest: str = PLAN_DIGEST,
    identity_mode: str = "bundledKeycloak",
    login_mode: str = "breakGlass",
):
    run_directory = tmp_path / RUN_ID
    input_paths = {
        **BASE_INPUT_PATHS,
        **(
            BUNDLED_INPUT_PATHS
            if identity_mode == "bundledKeycloak"
            else EXTERNAL_INPUT_PATHS
        ),
        **(LOGIN_INPUT_PATHS if login_mode == "files" else {}),
    }
    return MODULE.ResetOperationRequest(
        run_id=RUN_ID,
        plan_digest=PLAN_DIGEST,
        approval_digest=approval_digest,
        commit=COMMIT,
        profile=MODULE.ResetOperationProfile(
            context="rke",
            registry_host="harbor.rke.soez.tw",
            platform_url="https://aileron.apps.rke.soez.tw",
            identity_mode=identity_mode,
            issuer_url=(
                "https://keycloak.apps.rke.soez.tw/realms/aileron"
                if identity_mode == "bundledKeycloak"
                else "https://identity.example.test/realms/aileron"
            ),
            admin_console_url=(
                "https://keycloak-admin.apps.rke.soez.tw/admin/master/console/"
                if identity_mode == "bundledKeycloak"
                else None
            ),
            client_id="aileron-frontend",
            acceptance_login_mode=login_mode,
        ),
        inputs=tuple(
            MODULE.ResetOperationInput(
                name=name,
                path=run_directory / relative,
                digest="1" * 64,
            )
            for name, relative in input_paths.items()
        ),
    )


def _with_data_service_inputs(
    request: MODULE.ResetOperationRequest,
    tmp_path: Path,
    *,
    names: set[str] | None = None,
) -> MODULE.ResetOperationRequest:
    selected = set(DATA_SERVICE_INPUT_PATHS) if names is None else names
    run_directory = tmp_path / RUN_ID
    return replace(
        request,
        inputs=(
            *request.inputs,
            *(
                MODULE.ResetOperationInput(
                    name=name,
                    path=run_directory / relative,
                    digest="2" * 64,
                )
                for name, relative in DATA_SERVICE_INPUT_PATHS.items()
                if name in selected
            ),
        ),
    )


def test_first_attempt_prepares_exact_snapshot_and_requests_approval(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety()

    result = MODULE.execute_reset_operation(_request(tmp_path), safety=safety)

    assert result == MODULE.ResetOperationResult(
        disposition=MODULE.ResetOperationDisposition.AWAITING_APPROVAL,
        reset_snapshot_digest=SNAPSHOT_DIGEST,
        post_reset_report_digest=None,
    )
    assert safety.calls == [
        "validateInputs",
        "resumeSnapshot",
        ("prepareBackendAttestor", False),
        ("prepareBackendAttestor", True),
        ("prepareBackendAttestor", False),
        ("ensureNamespaces", True),
        "createSnapshot",
        ("validateSnapshot", SNAPSHOT_DIGEST),
        ("ensureRoot", "suites", SNAPSHOT_DIGEST),
        ("validateSnapshot", SNAPSHOT_DIGEST),
        ("ensureRoot", "offlineOidcConformance", SNAPSHOT_DIGEST),
        ("validateSnapshot", SNAPSHOT_DIGEST),
    ]


def test_ready_prerequisite_never_runs_apply(tmp_path: Path) -> None:
    safety = RecordingSafety()
    safety.prerequisite_results = [MODULE.ResetPrerequisiteDisposition.READY]

    result = MODULE.execute_reset_operation(_request(tmp_path), safety=safety)

    assert result.disposition is MODULE.ResetOperationDisposition.AWAITING_APPROVAL
    assert ("prepareBackendAttestor", True) not in safety.calls
    assert safety.calls[:4] == [
        "validateInputs",
        "resumeSnapshot",
        ("prepareBackendAttestor", False),
        ("ensureNamespaces", True),
    ]


def test_preparation_requires_ready_apply_and_final_validation(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety()
    safety.prerequisite_results = [
        MODULE.ResetPrerequisiteDisposition.PREPARATION_REQUIRED,
        MODULE.ResetPrerequisiteDisposition.PREPARATION_REQUIRED,
    ]

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(_request(tmp_path), safety=safety)

    assert raised.value.code == "resetPrerequisiteFailed"
    assert ("ensureNamespaces", True) not in safety.calls
    assert "createSnapshot" not in safety.calls


def test_snapshot_resume_skips_every_pre_snapshot_mutation_and_completes(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety(snapshot_digest=SNAPSHOT_DIGEST)

    result = MODULE.execute_reset_operation(
        _request(tmp_path, approval_digest=SNAPSHOT_DIGEST), safety=safety
    )

    assert result == MODULE.ResetOperationResult(
        disposition=MODULE.ResetOperationDisposition.COMPLETED,
        reset_snapshot_digest=SNAPSHOT_DIGEST,
        post_reset_report_digest=REPORT_DIGEST,
    )
    assert not any(
        call == "createSnapshot"
        or isinstance(call, tuple)
        and call[0] in {"prepareBackendAttestor", "ensureNamespaces"}
        for call in safety.calls
    )
    assert safety.calls[-2:] == [
        ("executeReset", SNAPSHOT_DIGEST),
        ("postReset", SNAPSHOT_DIGEST),
    ]


def test_snapshot_resume_with_plan_approval_returns_same_checkpoint(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety(snapshot_digest=SNAPSHOT_DIGEST)

    result = MODULE.execute_reset_operation(_request(tmp_path), safety=safety)

    assert result == MODULE.ResetOperationResult(
        disposition=MODULE.ResetOperationDisposition.AWAITING_APPROVAL,
        reset_snapshot_digest=SNAPSHOT_DIGEST,
        post_reset_report_digest=None,
    )
    assert not any(
        isinstance(call, tuple) and call[0] in {"executeReset", "postReset"}
        for call in safety.calls
    )


def test_stale_approval_is_rejected_before_report_or_reset_work(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety(snapshot_digest=SNAPSHOT_DIGEST)

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(
            _request(tmp_path, approval_digest="9" * 64), safety=safety
        )

    assert raised.value.code == "resetApprovalMismatch"
    assert safety.calls == ["validateInputs", "resumeSnapshot"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: replace(request, inputs=request.inputs[:-1]),
        lambda request: replace(
            request,
            inputs=(request.inputs[0], *request.inputs),
        ),
        lambda request: replace(
            request,
            inputs=(
                replace(
                    request.inputs[0],
                    path=request.inputs[0].path.with_name("other-kubeconfig"),
                ),
                *request.inputs[1:],
            ),
        ),
        lambda request: replace(
            request,
            inputs=(
                replace(request.inputs[0], digest="not-a-digest"),
                *request.inputs[1:],
            ),
        ),
    ],
)
def test_exact_staged_input_map_is_required_before_safety_calls(
    tmp_path: Path, mutate
) -> None:
    safety = RecordingSafety()

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(mutate(_request(tmp_path)), safety=safety)

    assert raised.value.code == "resetInputMapInvalid"
    assert safety.calls == []


def test_external_oidc_files_mode_uses_only_future_provider_neutral_inputs(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety()
    safety.prerequisite_results = [MODULE.ResetPrerequisiteDisposition.READY]
    request = _request(
        tmp_path,
        identity_mode="externalOidc",
        login_mode="files",
    )

    result = MODULE.execute_reset_operation(request, safety=safety)

    names = {item.name for item in request.inputs}
    assert result.reset_snapshot_digest == SNAPSHOT_DIGEST
    assert "externalOidcClientSecret" in names
    assert {"oidcLoginUsername", "oidcLoginPassword"} <= names
    assert "identityTlsCertificate" not in names
    assert "identityTlsPrivateKey" not in names


def test_external_data_service_inputs_are_revalidated_before_reset(
    tmp_path: Path,
) -> None:
    safety = RecordingSafety()
    safety.prerequisite_results = [MODULE.ResetPrerequisiteDisposition.READY]
    request = _with_data_service_inputs(_request(tmp_path), tmp_path)

    result = MODULE.execute_reset_operation(request, safety=safety)

    assert result.disposition is MODULE.ResetOperationDisposition.AWAITING_APPROVAL
    assert safety.calls[0] == "validateInputs"


@pytest.mark.parametrize(
    "request_factory",
    [
        lambda tmp_path: _with_data_service_inputs(
            _request(tmp_path),
            tmp_path,
            names=set(DATA_SERVICE_INPUT_PATHS) - {"redisJobResultCa"},
        ),
        lambda tmp_path: _with_data_service_inputs(
            _request(tmp_path, identity_mode="externalOidc", login_mode="files"),
            tmp_path,
        ),
    ],
)
def test_invalid_data_service_input_sets_fail_before_safety_calls(
    tmp_path: Path,
    request_factory,
) -> None:
    safety = RecordingSafety()

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(request_factory(tmp_path), safety=safety)

    assert raised.value.code == "resetInputMapInvalid"
    assert safety.calls == []


def test_reset_targets_preserve_the_bundled_admin_console_url(tmp_path: Path) -> None:
    request = _request(tmp_path)

    targets = MODULE._ProductionResetSafetyOperations._targets(request)

    assert targets.admin_console_url == request.profile.admin_console_url


def test_import_fallback_never_hides_transitive_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict | None = None,
        locals: dict | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ):
        if name == "scripts.deploy.rke2" and "acceptance_cluster" in fromlist:
            raise ModuleNotFoundError(
                "No module named 'transitive_dependency'",
                name="transitive_dependency",
            )
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    specification = importlib.util.spec_from_file_location(
        "homelab_reset_operation_import_contract",
        Path(MODULE.__file__),
    )
    assert specification is not None and specification.loader is not None
    candidate = importlib.util.module_from_spec(specification)

    with pytest.raises(ModuleNotFoundError) as raised:
        specification.loader.exec_module(candidate)

    assert raised.value.name == "transitive_dependency"


def test_snapshot_is_revalidated_after_each_causal_root(tmp_path: Path) -> None:
    class DriftingSnapshotSafety(RecordingSafety):
        validations = 0

        def validate_pre_reset_snapshot(
            self,
            request: MODULE.ResetOperationRequest,
            *,
            snapshot_digest: str,
        ) -> None:
            super().validate_pre_reset_snapshot(
                request, snapshot_digest=snapshot_digest
            )
            self.validations += 1
            if self.validations == 2:
                raise RuntimeError("snapshot target set changed")

    safety = DriftingSnapshotSafety(snapshot_digest=SNAPSHOT_DIGEST)

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(
            _request(tmp_path, approval_digest=SNAPSHOT_DIGEST), safety=safety
        )

    assert raised.value.code == "resetSnapshotInvalid"
    assert ("ensureRoot", "suites", SNAPSHOT_DIGEST) in safety.calls
    assert ("ensureRoot", "offlineOidcConformance", SNAPSHOT_DIGEST) not in safety.calls
    assert ("executeReset", SNAPSHOT_DIGEST) not in safety.calls


def test_dependency_failures_expose_only_stable_error_codes(tmp_path: Path) -> None:
    class LeakingSafety(RecordingSafety):
        def resume_pre_reset_snapshot(
            self, request: MODULE.ResetOperationRequest
        ) -> str | None:
            raise RuntimeError("/root/aileron-private/secret: private-token raw stderr")

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(_request(tmp_path), safety=LeakingSafety())

    assert raised.value.code == "resetSnapshotInvalid"
    assert str(raised.value) == "resetSnapshotInvalid"
    assert raised.value.__cause__ is None
    assert "secret" not in str(raised.value)
    assert "stderr" not in str(raised.value)


def test_reset_crash_resumes_durable_state_without_repeating_mutation(
    tmp_path: Path,
) -> None:
    class CrashResumingSafety(RecordingSafety):
        def __init__(self) -> None:
            super().__init__(snapshot_digest=SNAPSHOT_DIGEST)
            self.mutation_count = 0
            self.reset_started = False

        def execute_approved_reset(
            self, request: MODULE.ResetOperationRequest, *, snapshot_digest: str
        ) -> None:
            self.calls.append(("executeReset", snapshot_digest))
            if not self.reset_started:
                self.reset_started = True
                self.mutation_count += 1
                raise RuntimeError("connection lost after durable mutation")

    safety = CrashResumingSafety()
    request = _request(tmp_path, approval_digest=SNAPSHOT_DIGEST)

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(request, safety=safety)
    result = MODULE.execute_reset_operation(request, safety=safety)

    assert raised.value.code == "resetExecutionFailed"
    assert safety.mutation_count == 1
    assert result.disposition is MODULE.ResetOperationDisposition.COMPLETED
    assert result.reset_snapshot_digest == SNAPSHOT_DIGEST
    assert result.post_reset_report_digest == REPORT_DIGEST


def test_report_crash_resumes_exact_report_and_audit_digest(tmp_path: Path) -> None:
    class CrashAfterReportSafety(RecordingSafety):
        def __init__(self) -> None:
            super().__init__(snapshot_digest=SNAPSHOT_DIGEST)
            self.report_written = False

        def ensure_post_reset_report(
            self, request: MODULE.ResetOperationRequest, *, snapshot_digest: str
        ) -> str:
            self.calls.append(("postReset", snapshot_digest))
            if not self.report_written:
                self.report_written = True
                raise RuntimeError("process lost after signed report write")
            return REPORT_DIGEST

    safety = CrashAfterReportSafety()
    request = _request(tmp_path, approval_digest=SNAPSHOT_DIGEST)

    with pytest.raises(MODULE.ResetOperationError) as raised:
        MODULE.execute_reset_operation(request, safety=safety)
    result = MODULE.execute_reset_operation(request, safety=safety)

    assert raised.value.code == "resetPostReportInvalid"
    assert result == MODULE.ResetOperationResult(
        disposition=MODULE.ResetOperationDisposition.COMPLETED,
        reset_snapshot_digest=SNAPSHOT_DIGEST,
        post_reset_report_digest=REPORT_DIGEST,
    )


def test_production_input_gate_recomputes_every_staged_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    request = _request(tmp_path)
    for item in request.inputs:
        _directory(item.path.parent)
        content = f"fixture:{item.name}".encode()
        item.path.write_bytes(content)
        item.path.chmod(0o600)
    request = replace(
        request,
        inputs=tuple(
            replace(item, digest=hashlib.sha256(item.path.read_bytes()).hexdigest())
            for item in request.inputs
        ),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_private_root",
        staticmethod(lambda: tmp_path),
    )
    safety = MODULE._ProductionResetSafetyOperations()

    safety.validate_staged_inputs(request)
    request.inputs[0].path.write_text("changed", encoding="utf-8")
    request.inputs[0].path.chmod(0o600)

    with pytest.raises(ValueError, match="digest changed"):
        safety.validate_staged_inputs(request)


def test_production_preparer_classifies_only_explicit_required_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    calls: list[dict[str, object]] = []

    def prepare_backend_attestor(**arguments: object) -> dict[str, object]:
        calls.append(arguments)
        return {
            "schemaVersion": MODULE.BACKEND_PREPARER.PREPARATION_RESULT_SCHEMA,
            "mode": "validate",
            "ready": False,
            "durablePrerequisiteRetained": False,
            "missingResources": ["namespace"],
            "changedResources": [],
        }

    monkeypatch.setattr(
        MODULE.BACKEND_PREPARER,
        "prepare_backend_attestor",
        prepare_backend_attestor,
    )

    result = MODULE._ProductionResetSafetyOperations().prepare_backend_attestor(
        request, apply=False
    )

    assert result is MODULE.ResetPrerequisiteDisposition.PREPARATION_REQUIRED
    assert calls == [
        {
            "kubeconfig": request.inputs[0].path,
            "harbor_dockerconfig": next(
                item.path
                for item in request.inputs
                if item.name == "harborDockerconfig"
            ),
            "execution_profile": next(
                item.path
                for item in request.inputs
                if item.name == "backendExecutionProfile"
            ),
            "context": "rke",
            "registry": "harbor.rke.soez.tw",
            "apply": False,
        }
    ]


def test_production_preparer_rejects_ambiguous_required_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        MODULE.BACKEND_PREPARER,
        "prepare_backend_attestor",
        lambda **_arguments: {
            "schemaVersion": MODULE.BACKEND_PREPARER.PREPARATION_RESULT_SCHEMA,
            "mode": "validate",
            "ready": False,
            "durablePrerequisiteRetained": True,
            "missingResources": ["namespace"],
            "changedResources": [],
        },
    )

    with pytest.raises(ValueError, match="result is invalid"):
        MODULE._ProductionResetSafetyOperations().prepare_backend_attestor(
            request, apply=False
        )


def test_production_namespace_convergence_is_always_existing_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    calls: list[dict[str, object]] = []

    def ensure_installation_namespaces(**arguments: object) -> dict[str, object]:
        calls.append(arguments)
        return {
            "schemaVersion": MODULE.NAMESPACES.NAMESPACE_RESULT_SCHEMA,
            "mode": "prepare",
            "ready": True,
        }

    monkeypatch.setattr(
        MODULE.NAMESPACES,
        "ensure_installation_namespaces",
        ensure_installation_namespaces,
    )
    safety = MODULE._ProductionResetSafetyOperations()

    safety.ensure_existing_namespaces(request, existing_only=True)

    assert calls[0]["existing_only"] is True
    assert calls[0]["identity_mode"] == "bundledKeycloak"
    with pytest.raises(ValueError, match="existing-only"):
        safety.ensure_existing_namespaces(request, existing_only=False)


def test_production_resume_rejects_epoch_or_state_without_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    epoch = evidence / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME
    epoch.write_text("orphan", encoding="utf-8")
    epoch.chmod(0o600)
    state = tmp_path / "reset/reset-execution-state.json"
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_evidence_directory",
        classmethod(lambda cls, _request: evidence),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: state),
    )

    with pytest.raises(ValueError, match="without its snapshot"):
        MODULE._ProductionResetSafetyOperations().resume_pre_reset_snapshot(request)


def test_production_snapshot_resume_repairs_only_the_missing_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    snapshot = evidence / MODULE.ACCEPTANCE_SNAPSHOT.SNAPSHOT_NAME
    snapshot.write_text("signed-snapshot", encoding="utf-8")
    snapshot.chmod(0o600)
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_evidence_directory",
        classmethod(lambda cls, _request: evidence),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: tmp_path / "state"),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_read_snapshot_digest",
        classmethod(lambda cls, _request: SNAPSHOT_DIGEST),
    )

    def load_snapshot_context(
        cls,
        _request: MODULE.ResetOperationRequest,
        *,
        expected_snapshot_digest: str,
        repair_epoch: bool,
    ) -> object:
        calls.append(("digest", expected_snapshot_digest))
        calls.append(("repairEpoch", repair_epoch))
        return object()

    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_load_snapshot_context",
        classmethod(load_snapshot_context),
    )

    result = MODULE._ProductionResetSafetyOperations().resume_pre_reset_snapshot(
        request
    )

    assert result == SNAPSHOT_DIGEST
    assert calls == [("digest", SNAPSHOT_DIGEST), ("repairEpoch", True)]


@pytest.mark.parametrize(
    ("section", "expected_digest"),
    [("suites", "e" * 64), ("offlineOidcConformance", "f" * 64)],
)
def test_production_causal_root_resume_validates_without_reproducing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str,
    expected_digest: str,
) -> None:
    request = _request(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    report = evidence / f"{section}.json"
    report.write_text("signed-report", encoding="utf-8")
    report.chmod(0o600)
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_evidence_directory",
        classmethod(lambda cls, _request: evidence),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: tmp_path / "missing-state"),
    )

    def validated_report_digest(
        _self: object,
        _request: MODULE.ResetOperationRequest,
        **arguments: object,
    ) -> str:
        assert arguments == {
            "section": section,
            "snapshot_digest": SNAPSHOT_DIGEST,
            "allow_stale_for_reset_resume": False,
        }
        return expected_digest

    def reject_produce(**_arguments: object) -> Path:
        raise AssertionError("existing signed report must not be reproduced")

    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_validated_report_digest",
        validated_report_digest,
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_PRODUCER,
        "produce",
        reject_produce,
    )

    result = MODULE._ProductionResetSafetyOperations().ensure_causal_root(
        request,
        section=section,
        snapshot_digest=SNAPSHOT_DIGEST,
    )

    assert result == expected_digest


def test_production_partial_reset_defers_freshness_to_durable_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, approval_digest=SNAPSHOT_DIGEST)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    report = evidence / "suites.json"
    report.write_text("signed-report", encoding="utf-8")
    report.chmod(0o600)
    state = tmp_path / "reset-execution-state.json"
    state.write_text("durable-state", encoding="utf-8")
    state.chmod(0o600)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_evidence_directory",
        classmethod(lambda cls, _request: evidence),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: state),
    )

    def validated_report_digest(
        _self: object,
        _request: MODULE.ResetOperationRequest,
        **arguments: object,
    ) -> str:
        calls.append(arguments)
        return "e" * 64

    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_validated_report_digest",
        validated_report_digest,
    )

    result = MODULE._ProductionResetSafetyOperations().ensure_causal_root(
        request,
        section="suites",
        snapshot_digest=SNAPSHOT_DIGEST,
    )

    assert result == "e" * 64
    assert calls == [
        {
            "section": "suites",
            "snapshot_digest": SNAPSHOT_DIGEST,
            "allow_stale_for_reset_resume": True,
        }
    ]


def test_production_partial_reset_never_recreates_missing_causal_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, approval_digest=SNAPSHOT_DIGEST)
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    state = tmp_path / "reset-execution-state.json"
    state.write_text("durable-state", encoding="utf-8")
    state.chmod(0o600)
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_evidence_directory",
        classmethod(lambda cls, _request: evidence),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: state),
    )

    with pytest.raises(ValueError, match="unavailable after reset start"):
        MODULE._ProductionResetSafetyOperations().ensure_causal_root(
            request,
            section="suites",
            snapshot_digest=SNAPSHOT_DIGEST,
        )


def test_production_snapshot_validation_rejects_live_target_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path)
    context = MODULE._SnapshotContext(
        directory=tmp_path / "evidence",
        kubeconfig=tmp_path / "kubeconfig",
        private_root=tmp_path,
        trust=object(),
        snapshot={"inventory": {"target": "approved"}},
        epoch={},
    )
    live_inventory = {"target": "approved"}
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_read_snapshot_digest",
        classmethod(lambda cls, _request: SNAPSHOT_DIGEST),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_load_snapshot_context",
        classmethod(lambda cls, _request, **_arguments: context),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: tmp_path / "missing-state"),
    )

    def collect_reset_inventory(**arguments: object) -> dict[str, str]:
        assert arguments == {
            "expected_context": "rke",
            "kubeconfig": context.kubeconfig,
            "runner": MODULE._run_inventory_command,
        }
        return live_inventory

    monkeypatch.setattr(
        MODULE.RESET_INVENTORY,
        "collect_reset_inventory",
        collect_reset_inventory,
    )
    monkeypatch.setattr(
        MODULE.RESET_PLAN,
        "build_reset_plan",
        lambda inventory, **_arguments: dict(inventory),
    )
    monkeypatch.setattr(
        MODULE.RESET_PLAN,
        "effective_reset_target_set",
        lambda plan: dict(plan),
    )
    safety = MODULE._ProductionResetSafetyOperations()

    safety.validate_pre_reset_snapshot(request, snapshot_digest=SNAPSHOT_DIGEST)
    live_inventory = {"target": "changed"}

    with pytest.raises(ValueError, match="target set changed"):
        safety.validate_pre_reset_snapshot(request, snapshot_digest=SNAPSHOT_DIGEST)


def test_production_reset_uses_canonical_snapshot_plan_and_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, approval_digest=SNAPSHOT_DIGEST)
    tmp_path.chmod(0o700)
    evidence_kubeconfig = tmp_path / "evidence-kubeconfig"
    reset_directory = tmp_path / "reset" / COMMIT / RUN_ID
    state_path = reset_directory / "reset-execution-state.json"
    flattened = reset_directory / f"reset-kubeconfig-{RUN_ID}.flattened.json"
    context = MODULE._SnapshotContext(
        directory=tmp_path / "evidence",
        kubeconfig=evidence_kubeconfig,
        private_root=tmp_path,
        trust=object(),
        snapshot={"inventory": {"context": "rke"}},
        epoch={},
    )
    snapshots: list[dict[str, object]] = []
    builds: list[tuple[object, Path, str]] = []
    executions: list[dict[str, object]] = []
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_load_snapshot_context",
        classmethod(lambda cls, _request, **_kwargs: context),
    )
    monkeypatch.setattr(
        MODULE._ProductionResetSafetyOperations,
        "_reset_state_path",
        classmethod(lambda cls, _request: state_path),
    )

    def snapshot_self_contained_kubeconfig(**arguments: object) -> Path:
        snapshots.append(arguments)
        return flattened

    def build_reset_plan(
        inventory: object, *, kubeconfig: Path, reset_run_id: str
    ) -> dict[str, object]:
        builds.append((inventory, kubeconfig, reset_run_id))
        return {"plan": "canonical"}

    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        snapshot_self_contained_kubeconfig,
    )
    monkeypatch.setattr(MODULE.RESET_PLAN, "build_reset_plan", build_reset_plan)
    monkeypatch.setattr(
        MODULE.RESET_PLAN,
        "execute_reset_plan",
        lambda plan, **arguments: executions.append({"plan": plan, **arguments}),
    )

    MODULE._ProductionResetSafetyOperations().execute_approved_reset(
        request, snapshot_digest=SNAPSHOT_DIGEST
    )

    assert snapshots[0]["source"] == evidence_kubeconfig
    assert snapshots[0]["allow_existing_exact"] is True
    assert snapshots[0]["flattened_destination"] == flattened
    assert builds == [({"context": "rke"}, flattened, RUN_ID)]
    assert executions[0]["plan"] == {"plan": "canonical"}
    assert executions[0]["kubeconfig"] == flattened
    assert executions[0]["execution_state_path"] == state_path
    assert executions[0]["reset_snapshot_sha256"] == SNAPSHOT_DIGEST
