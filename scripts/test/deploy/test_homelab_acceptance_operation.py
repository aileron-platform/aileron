"""Public HomeLab acceptance operation contract tests."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.deploy.rke2 import homelab_acceptance_operation as MODULE

COMMIT = "a" * 40
RUN_ID = "run-0123456789abcdef0123456789abcdef"
RESET_DIGEST = "b" * 64
CERTIFICATE = b"""-----BEGIN CERTIFICATE-----
MIICsDCCAZgCCQDA8G2CJLBwpTANBgkqhkiG9w0BAQsFADAaMRgwFgYDVQQDDA9h
Y2NlcHRhbmNlLXRlc3QwHhcNMjYwODEwMDMzNzEzWhcNMjcwODEwMDMzNzEzWjAa
MRgwFgYDVQQDDA9hY2NlcHRhbmNlLXRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQDRWpF0eTZlVG7c34IZyDxACK15CgW1RMn6dxOxDTp6n/rw90Ef
IjF5wckBQhAsqkM1sHxwZQY100Dy4z8LiDcRpvzoBn3esGTWOuE/KCtoXmFzmfln
mN4xHS8qiejqz5YZ8Z4YKBoshgmFPb+pJGmvRD+O6A/VGwYxrc3SlKz9HBzCSMPI
AG5GcH1claMgeEQyd4HxofFdU/25il2xSCgHWqigRZcgkoaOcW00WyJjC2Btj+dh
VKKj+T+e1Rrgf0qplylETVmCEYJwqSBvEDhLCcsmkJ+EmafXcpA3VvbAx+6T9aHq
p0PRg+QEPbES+n0XS7ofvCKvOb0Yrq9LQnsjAgMBAAEwDQYJKoZIhvcNAQELBQAD
ggEBAIZJOqgzNBaT6/0nAdbaolZcXXKzdM2pfFYBhYYd3qfz9JRT0B/DNjg6Htyl
Spr+Qu59vao7cyockXCESoMw2j4oAPn1DS0tVwIsaG4/fd2HT/cDZpFpsQeZR3tZ
kx68SpWpRtxTe+CvjQRDdGo2d1u8Z8Df88H5bYtCZvdV4Bt70cOJmz7ZDhJ2XHTW
4kuF3oO9MoVBdvwiz0NjJWfdtI9/hFM3Na8hwr2hr8uq6On1tqUWr25sYkxomj6H
nZzW7z6sfGFLqu9PXFoD0sVD9ZIyx6q1OQAKV5pcbAYEFzU8h1JKEmcebYycynds
VdWBkWz6DgvtWXBGLL861F5nAB4=
-----END CERTIFICATE-----
"""
OIDC_CERTIFICATE = b"""-----BEGIN CERTIFICATE-----
MIICujCCAaICCQDAYdYtfMpI6TANBgkqhkiG9w0BAQsFADAfMR0wGwYDVQQDDBRh
Y2NlcHRhbmNlLW9pZGMtdGVzdDAeFw0yNjA4MTAwMzUxMTdaFw0yNzA4MTAwMzUx
MTdaMB8xHTAbBgNVBAMMFGFjY2VwdGFuY2Utb2lkYy10ZXN0MIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7qrWTBE+7+fTL9uwEoqxACDfR+Tt2ix9wTJX
XfdY2bol3k1Y3JflWhhMxk/uoY3gRHFqWsEiuyaNwVnZRjE1IvNHKV9KtdslcjJy
6ydNEKnkqqjF4pDDlz9zLYz3NZBxNtAeTWbYNZAhOUveeXFR/wkUbB5ceH3dURAk
aEcMIJF1kp3Sy74NB4BC7WEROJFnkBeU6PvRAEiDrk/L89GY8rBsPfhnh669J9J8
BGaCZyOvta2q7EUS423DJnmZrKmL1G23WzUeZE0qpBqB2KLetkAOlKQlZHgFXZwG
6fTx36AzOA0s2cvbrkCNpnvsKafGtRBJEaYTlWK+BTRgUyBAGwIDAQABMA0GCSqG
SIb3DQEBCwUAA4IBAQCbAieygnBgBDf4wsfFPkT29kho/Arne68u/z0BMysHnH42
HfNpNN53Cf25KFVHYMGDIpN98CO7YHTw+JK7Wp65wmg3XjNQmcKNdEYSQqcGEMRF
L/JOzec2j2OJ8ZBhQQ3RzyKc3CmJL8z0NRTqRm1b6oLZjdSstGklXMCZ1Bb88czS
idUYru6mvzP8mYrfpzSs++ozZVsAwRkcHF5hXyRb8hLON+GZ2Jup9U5WQnd6i3M1
WSHZzWX5yOpMTQMudYY8Q5ZM5VZW8YDaNHpnV4sWraX//YvlHu+JQj0QW3BOi6x0
gWcfh9mb2/1NlNvwft27WmIZAZeMRLaP+ak7FVVP
-----END CERTIFICATE-----
"""


def _private_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


class RecordingSafety:
    def __init__(self, private_root: Path) -> None:
        self.private_root = private_root
        self.reports: dict[str, MODULE.ValidatedAcceptanceReport] = {}
        self.events: list[str] = []
        self.bundle_present = False
        self.bundle_error: Exception | None = None
        self.build_error: Exception | None = None
        self.producer_error: tuple[str, Exception] | None = None
        self.interrupt_once: str | None = None
        self.validation_error: tuple[str, Exception] | None = None
        self.browser_ca_contents: list[bytes] = []
        self.started_snapshots: dict[str, dict[str, object]] = {}

    def load_contract(self) -> dict[str, object]:
        return json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "deploy/rke2/deployment-acceptance-contract.json"
            ).read_text(encoding="utf-8")
        )

    def validate_report(
        self,
        request: MODULE.AcceptanceOperationRequest,
        section: str,
        workspace: MODULE.WorkspaceIdentity | None,
    ) -> MODULE.ValidatedAcceptanceReport | None:
        del request
        self.events.append(f"validate:{section}")
        if self.validation_error is not None and self.validation_error[0] == section:
            raise self.validation_error[1]
        return self.reports.get(section)

    def prepare_browser_input(self, request: MODULE.AcceptanceOperationRequest) -> Path:
        del request
        self.events.append("prepare:browser-input")
        return self.private_root / "browser-input.json"

    def produce_report(
        self,
        request: MODULE.AcceptanceOperationRequest,
        section: str,
        workspace: MODULE.WorkspaceIdentity | None,
        browser_ca: Path | None,
    ) -> None:
        del request
        self.events.append(f"produce:{section}")
        journal = json.loads(
            (
                self.private_root / "evidence" / COMMIT / RUN_ID / MODULE.JOURNAL_NAME
            ).read_text(encoding="utf-8")
        )
        self.started_snapshots[section] = journal
        if section in MODULE.BROWSER_SECTIONS:
            assert browser_ca is not None
            self.browser_ca_contents.append(browser_ca.read_bytes())
        if self.interrupt_once == section:
            self.interrupt_once = None
            raise KeyboardInterrupt(f"interrupted {section}")
        if self.producer_error is not None and self.producer_error[0] == section:
            raise self.producer_error[1]
        report_workspace = workspace
        if section == "oidcWorkspace":
            report_workspace = MODULE.WorkspaceIdentity("workspace-1", "subject-1")
        self.reports[section] = MODULE.ValidatedAcceptanceReport(
            section=section,
            path=self.private_root / f"{section}.json",
            sha256="c" * 64,
            workspace=report_workspace,
        )

    def bundle_exists(self, request: MODULE.AcceptanceOperationRequest) -> bool:
        del request
        self.events.append("bundle:exists")
        return self.bundle_present

    def build_bundle(self, request: MODULE.AcceptanceOperationRequest) -> Path:
        del request
        self.events.append("bundle:build")
        if self.build_error is not None:
            raise self.build_error
        self.bundle_present = True
        return self.private_root / "deployment-acceptance-bundle.json"

    def validate_bundle(
        self, request: MODULE.AcceptanceOperationRequest
    ) -> MODULE.ValidatedAcceptanceBundle:
        del request
        self.events.append("bundle:validate")
        if self.bundle_error is not None:
            raise self.bundle_error
        return MODULE.ValidatedAcceptanceBundle(
            path=self.private_root / "deployment-acceptance-bundle.json",
            sha256="d" * 64,
            workspace=MODULE.WorkspaceIdentity("workspace-1", "subject-1"),
        )


def _request(
    tmp_path: Path,
    *,
    authentication_mode: str,
    apps_certificate: bytes = CERTIFICATE,
    oidc_certificate: bytes = CERTIFICATE,
) -> MODULE.AcceptanceOperationRequest:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    kubeconfig = _private_file(private_root / "inputs/kubeconfig", b"kubeconfig\n")
    inventory = _private_file(private_root / "inputs/images.json", b"{}\n")
    apps_ca = _private_file(private_root / "inputs/apps-ca.pem", apps_certificate)
    oidc_ca = _private_file(private_root / "inputs/oidc-ca.pem", oidc_certificate)
    username = _private_file(private_root / "inputs/username", b"tester")
    password = _private_file(private_root / "inputs/password", b"secret")
    driver = (
        MODULE.BrowserLoginDriver(kind="keycloak")
        if authentication_mode == "bundledKeycloak"
        else MODULE.BrowserLoginDriver(
            kind="form",
            username_selector="#username",
            password_selector="#password",
            submit_selector="#submit",
            error_selector="#error",
        )
    )
    return MODULE.AcceptanceOperationRequest(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        authentication_mode=authentication_mode,
        context="rke",
        kubeconfig=kubeconfig,
        platform_url="https://aileron.example.test",
        issuer_url="https://identity.example.test/realms/aileron",
        admin_console_url=(
            "https://identity-admin.example.test/admin/master/console/"
            if authentication_mode == "bundledKeycloak"
            else None
        ),
        client_id="aileron-frontend",
        image_inventory=inventory,
        reset_snapshot_digest=RESET_DIGEST,
        apps_ca=apps_ca,
        oidc_ca=oidc_ca,
        identity_artifacts_directory=(
            private_root / "install-secrets/rke2/identity-artifacts"
            if authentication_mode == "bundledKeycloak"
            else None
        ),
        browser_login_mode=(
            "breakGlass" if authentication_mode == "bundledKeycloak" else "files"
        ),
        browser_login_driver=driver,
        browser_login_username=(
            username if authentication_mode == "externalOidc" else None
        ),
        browser_login_password=(
            password if authentication_mode == "externalOidc" else None
        ),
    )


def _prime_reports(safety: RecordingSafety, sections: tuple[str, ...]) -> None:
    workspace = MODULE.WorkspaceIdentity("workspace-1", "subject-1")
    workspace_sections = {
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "turn",
        "workspaceLifecycle",
        "restart",
        "soak",
        "adminDisableLogin",
    }
    for section in sections:
        safety.reports[section] = MODULE.ValidatedAcceptanceReport(
            section=section,
            path=safety.private_root / f"{section}.json",
            sha256="c" * 64,
            workspace=workspace if section in workspace_sections else None,
        )


def test_bundled_mode_executes_the_v11_dag_and_returns_server_identity(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")

    result = MODULE.execute_acceptance_operation(request, safety=safety)

    assert result.workspace == MODULE.WorkspaceIdentity("workspace-1", "subject-1")
    assert result.completed_sections == (
        "suites",
        "offlineOidcConformance",
        "cleanReset",
        "imageRelease",
        "identity",
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "turn",
        "workspaceLifecycle",
        "restart",
        "soak",
        "adminDisableLogin",
    )
    assert result.reused_sections == ()
    assert safety.events[-3:] == [
        "bundle:exists",
        "bundle:build",
        "bundle:validate",
    ]


def test_external_oidc_mode_omits_bundled_only_sections(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="externalOidc")
    safety = RecordingSafety(tmp_path / "private")

    result = MODULE.execute_acceptance_operation(request, safety=safety)

    assert result.completed_sections == (
        "suites",
        "offlineOidcConformance",
        "cleanReset",
        "imageRelease",
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "turn",
        "workspaceLifecycle",
        "restart",
        "soak",
    )
    assert "produce:identity" not in safety.events
    assert "produce:adminDisableLogin" not in safety.events


def test_existing_valid_reports_are_fully_validated_and_reused(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="externalOidc")
    safety = RecordingSafety(tmp_path / "private")
    sections = (
        "suites",
        "offlineOidcConformance",
        "cleanReset",
        "imageRelease",
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "turn",
        "workspaceLifecycle",
        "restart",
        "soak",
    )
    _prime_reports(safety, sections)

    result = MODULE.execute_acceptance_operation(request, safety=safety)

    assert result.reused_sections == sections
    assert not any(event.startswith("produce:") for event in safety.events)
    assert "prepare:browser-input" not in safety.events
    assert [event for event in safety.events if event.startswith("validate:")] == [
        f"validate:{section}" for section in sections
    ]


def test_existing_bundle_is_validated_before_reports_or_private_browser_input(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.bundle_present = True

    result = MODULE.execute_acceptance_operation(request, safety=safety)

    assert result.bundle_sha256 == "d" * 64
    assert safety.events == ["bundle:exists", "bundle:validate"]


def test_invalid_existing_bundle_is_preserved_and_reports_a_safe_code(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.bundle_present = True
    safety.bundle_error = RuntimeError(
        f"secret-value {request.apps_ca} raw stderr must remain private"
    )

    try:
        MODULE.execute_acceptance_operation(request, safety=safety)
    except MODULE.AcceptanceOperationError as error:
        assert error.code == "acceptanceExistingBundleInvalid"
        assert str(error) == "acceptanceExistingBundleInvalid"
        assert "secret-value" not in str(error)
        assert str(request.apps_ca) not in str(error)
    else:
        raise AssertionError("invalid existing bundle must fail closed")

    assert safety.events == ["bundle:exists", "bundle:validate"]
    assert "bundle:build" not in safety.events


def test_browser_ca_combines_role_order_and_deduplicates_by_der(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        authentication_mode="bundledKeycloak",
        apps_certificate=CERTIFICATE,
        oidc_certificate=OIDC_CERTIFICATE,
    )
    safety = RecordingSafety(tmp_path / "private")

    MODULE.execute_acceptance_operation(request, safety=safety)

    expected = CERTIFICATE + OIDC_CERTIFICATE
    assert safety.browser_ca_contents
    assert all(content == expected for content in safety.browser_ca_contents)
    bundle = tmp_path / "private/evidence" / COMMIT / RUN_ID / MODULE.BROWSER_CA_NAME
    assert bundle.read_bytes() == expected
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600


def test_identical_apps_and_oidc_ca_is_published_once(tmp_path: Path) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")

    MODULE.execute_acceptance_operation(request, safety=safety)

    assert safety.browser_ca_contents[0] == CERTIFICATE
    assert safety.browser_ca_contents[0].count(b"BEGIN CERTIFICATE") == 1


@pytest.mark.parametrize(
    "section",
    [
        "cleanReset",
        "imageRelease",
        "identity",
        "oidcWorkspace",
        "turn",
        "workspaceLifecycle",
        "restart",
    ],
)
def test_started_mutating_section_without_a_valid_report_is_ambiguous(
    tmp_path: Path,
    section: str,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.interrupt_once = section

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_acceptance_operation(request, safety=safety)

    started = safety.started_snapshots[section]
    item = next(
        candidate
        for candidate in started["sections"]
        if candidate["section"] == section
    )
    assert item["status"] == "started"
    assert item["attempts"] == 1
    assert safety.events.count(f"produce:{section}") == 1

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceReportResumeAmbiguous$",
    ) as failure:
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert failure.value.code == "acceptanceReportResumeAmbiguous"
    assert safety.events.count(f"produce:{section}") == 1


def test_admin_disable_records_point_of_no_return_before_the_producer(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.interrupt_once = "adminDisableLogin"

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_acceptance_operation(request, safety=safety)

    started = safety.started_snapshots["adminDisableLogin"]
    assert started["pointOfNoReturn"] is True
    assert safety.events.count("produce:adminDisableLogin") == 1

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceBreakGlassRestorationUncertain$",
    ) as failure:
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert failure.value.code == "acceptanceBreakGlassRestorationUncertain"
    assert safety.events.count("produce:adminDisableLogin") == 1


@pytest.mark.parametrize("section", ["terminal", "soak"])
def test_started_read_only_probe_can_retry_explicitly(
    tmp_path: Path, section: str
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.interrupt_once = section

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_acceptance_operation(request, safety=safety)

    result = MODULE.execute_acceptance_operation(request, safety=safety)

    assert result.bundle_sha256 == "d" * 64
    assert safety.events.count(f"produce:{section}") == 2
    journal = json.loads(
        (
            tmp_path / "private/evidence" / COMMIT / RUN_ID / MODULE.JOURNAL_NAME
        ).read_text(encoding="utf-8")
    )
    retried = next(item for item in journal["sections"] if item["section"] == section)
    assert retried["status"] == "completed"
    assert retried["attempts"] == 2


def test_workspace_identity_mismatch_fails_before_the_next_producer(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    sections = (
        "suites",
        "offlineOidcConformance",
        "cleanReset",
        "imageRelease",
        "identity",
        "oidcWorkspace",
        "terminal",
    )
    _prime_reports(safety, sections)
    safety.reports["terminal"] = MODULE.ValidatedAcceptanceReport(
        section="terminal",
        path=safety.private_root / "terminal.json",
        sha256="c" * 64,
        workspace=MODULE.WorkspaceIdentity("workspace-other", "subject-1"),
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceWorkspaceIdentityMismatch$",
    ):
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert "produce:http" not in safety.events


def test_operation_journal_is_owner_only_canonical_and_contains_no_secrets(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")

    MODULE.execute_acceptance_operation(request, safety=safety)

    journal_path = tmp_path / "private/evidence" / COMMIT / RUN_ID / MODULE.JOURNAL_NAME
    raw = journal_path.read_bytes()
    document = json.loads(raw)
    assert document["schemaVersion"] == "aileron-acceptance-operation-journal/v4"
    assert stat.S_IMODE(journal_path.stat().st_mode) == 0o600
    assert (
        raw
        == (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode()
    )
    assert document["pointOfNoReturn"] is True
    assert document["bundle"]["status"] == "completed"
    assert all(item["status"] == "completed" for item in document["sections"])
    for forbidden in (
        b"secret",
        b"emergency",
        b"realm-admin",
        str(request.apps_ca).encode(),
        str(request.browser_login_password).encode(),
    ):
        assert forbidden not in raw


def test_v3_operation_journal_is_rejected_clean_cut(tmp_path: Path) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    MODULE.execute_acceptance_operation(request, safety=safety)
    journal_path = tmp_path / "private/evidence" / COMMIT / RUN_ID / MODULE.JOURNAL_NAME
    document = json.loads(journal_path.read_text(encoding="utf-8"))
    document["schemaVersion"] = "aileron-acceptance-operation-journal/v3"
    journal_path.write_bytes(
        (json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n").encode()
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceOperationJournalInvalid$",
    ):
        MODULE.execute_acceptance_operation(request, safety=safety)


def test_production_adapter_passes_validated_canonical_kubeconfig_to_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    operations = MODULE._ProductionAcceptanceSafetyOperations()
    operations.private_root = tmp_path / "private"
    directory = operations.private_root / "evidence" / COMMIT / RUN_ID
    report_path = _private_file(directory / "soak.json", b"{}\n")
    canonical_kubeconfig = directory / "validated-kubeconfig"
    contract: dict[str, object] = {}
    epoch: dict[str, object] = {}

    class Trust:
        key = b"signing-key"

    monkeypatch.setattr(
        MODULE.PRIVATE_IO,
        "evidence_directory",
        lambda **_kwargs: directory,
    )
    monkeypatch.setattr(
        operations,
        "_validation_context",
        lambda _request: (
            directory,
            canonical_kubeconfig,
            contract,
            epoch,
            Trust(),
        ),
    )
    observed: dict[str, object] = {}

    def validate_report_bytes(**kwargs):
        observed.update(kwargs)
        return {
            "path": report_path,
            "sha256": "c" * 64,
            "report": {"workspace": {"id": "workspace-1", "userSubject": "subject-1"}},
        }

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_bytes",
        validate_report_bytes,
    )
    recovered: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_PRODUCER,
        "recover_atomic_report_publication",
        lambda path, *, private_root: recovered.append((path, private_root)),
    )

    result = operations.validate_report(
        request,
        "soak",
        MODULE.WorkspaceIdentity("workspace-1", "subject-1"),
    )

    assert result is not None
    assert recovered == [(report_path, operations.private_root)]
    assert observed["canonical_kubeconfig"] == canonical_kubeconfig
    assert observed["raw"] == b"{}\n"


def test_production_adapter_threads_admin_console_url_to_producer_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    operations = MODULE._ProductionAcceptanceSafetyOperations()
    captured: dict[str, object] = {}

    def produce(**arguments: object) -> None:
        captured.update(arguments)

    monkeypatch.setattr(MODULE.ACCEPTANCE_PRODUCER, "produce", produce)

    operations.produce_report(
        request,
        "adminDisableLogin",
        MODULE.WorkspaceIdentity("workspace-1", "subject-1"),
        request.apps_ca,
    )

    targets = captured["targets"]
    assert targets.admin_console_url == request.admin_console_url


def test_production_adapter_recovers_post_link_soak_before_public_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    operations = MODULE._ProductionAcceptanceSafetyOperations()
    operations.private_root = tmp_path / "private"
    directory = operations.private_root / "evidence" / COMMIT / RUN_ID
    temporary = _private_file(
        directory / f".soak.json.tmp-{'a' * 32}",
        b"{}\n",
    )
    for private_directory in (
        operations.private_root / "evidence",
        operations.private_root / "evidence" / COMMIT,
        directory,
    ):
        private_directory.chmod(0o700)
    report_path = directory / "soak.json"
    os.link(temporary, report_path, follow_symlinks=False)
    canonical_kubeconfig = directory / "validated-kubeconfig"

    class Trust:
        key = b"signing-key"

    monkeypatch.setattr(
        MODULE.PRIVATE_IO,
        "evidence_directory",
        lambda **_kwargs: directory,
    )
    monkeypatch.setattr(
        operations,
        "_validation_context",
        lambda _request: (
            directory,
            canonical_kubeconfig,
            {},
            {},
            Trust(),
        ),
    )

    def validate_report_bytes(**_kwargs):
        assert report_path.stat().st_nlink == 1
        assert not temporary.exists()
        return {
            "path": report_path,
            "sha256": "c" * 64,
            "report": {
                "workspace": {"id": "workspace-1", "userSubject": "subject-1"}
            },
        }

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_bytes",
        validate_report_bytes,
    )

    result = operations.validate_report(
        request,
        "soak",
        MODULE.WorkspaceIdentity("workspace-1", "subject-1"),
    )

    assert result is not None
    assert result.path == report_path


def test_production_adapter_rejects_post_link_inode_replacement_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    operations = MODULE._ProductionAcceptanceSafetyOperations()
    operations.private_root = tmp_path / "private"
    directory = operations.private_root / "evidence" / COMMIT / RUN_ID
    temporary = _private_file(
        directory / f".soak.json.tmp-{'b' * 32}",
        b"{}\n",
    )
    for private_directory in (
        operations.private_root / "evidence",
        operations.private_root / "evidence" / COMMIT,
        directory,
    ):
        private_directory.chmod(0o700)
    report_path = directory / "soak.json"
    os.link(temporary, report_path, follow_symlinks=False)
    monkeypatch.setattr(
        MODULE.PRIVATE_IO,
        "evidence_directory",
        lambda **_kwargs: directory,
    )

    class Trust:
        key = b"signing-key"

    monkeypatch.setattr(
        operations,
        "_validation_context",
        lambda _request: (
            directory,
            directory / "validated-kubeconfig",
            {},
            {},
            Trust(),
        ),
    )
    real_unlink = MODULE.ACCEPTANCE_PRODUCER._unlink_private_snapshot

    def replace_final_after_temp_unlink(path: Path, description: str) -> None:
        real_unlink(path, description)
        if path == temporary:
            report_path.unlink()
            report_path.write_bytes(b'{"replacement":true}\n')
            report_path.chmod(0o600)

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_PRODUCER,
        "_unlink_private_snapshot",
        replace_final_after_temp_unlink,
    )
    validator_called = False

    def validate_report_bytes(**_kwargs):
        nonlocal validator_called
        validator_called = True
        raise AssertionError("public validator must not observe a replacement inode")

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_bytes",
        validate_report_bytes,
    )

    with pytest.raises(
        MODULE.ACCEPTANCE_PRODUCER.AcceptanceProducerError,
        match="recovery",
    ):
        operations.validate_report(
            request,
            "soak",
            MODULE.WorkspaceIdentity("workspace-1", "subject-1"),
        )

    assert validator_called is False


def test_invalid_existing_report_fails_without_producer_or_diagnostics_leak(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.validation_error = (
        "suites",
        RuntimeError(f"private-token raw-stderr {request.kubeconfig}"),
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceReportInvalid$",
    ) as failure:
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert failure.value.code == "acceptanceReportInvalid"
    assert "private-token" not in str(failure.value)
    assert str(request.kubeconfig) not in str(failure.value)
    assert not any(event.startswith("produce:") for event in safety.events)


def test_producer_failure_is_safe_and_leaves_started_checkpoint(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.producer_error = (
        "suites",
        RuntimeError(f"credential-value raw-stderr {request.image_inventory}"),
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceReportProductionFailed$",
    ) as failure:
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert "credential-value" not in str(failure.value)
    assert str(request.image_inventory) not in str(failure.value)
    journal = safety.started_snapshots["suites"]
    suites = next(item for item in journal["sections"] if item["section"] == "suites")
    assert suites["status"] == "started"


def test_final_validation_failure_is_distinct_and_safe(tmp_path: Path) -> None:
    request = _request(tmp_path, authentication_mode="bundledKeycloak")
    safety = RecordingSafety(tmp_path / "private")
    safety.bundle_error = RuntimeError(
        f"private-token invalid bundle {request.browser_login_password}"
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceFinalValidationFailed$",
    ) as failure:
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert failure.value.code == "acceptanceFinalValidationFailed"
    assert "private-token" not in str(failure.value)
    assert safety.events[-2:] == ["bundle:build", "bundle:validate"]


def test_invalid_ca_fails_before_the_first_browser_producer(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        authentication_mode="bundledKeycloak",
        oidc_certificate=b"not-a-certificate\n",
    )
    safety = RecordingSafety(tmp_path / "private")

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceBrowserTrustInvalid$",
    ):
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert "produce:oidcWorkspace" not in safety.events


def test_request_has_no_registry_ca_browser_trust_surface() -> None:
    assert "registry_ca" not in MODULE.AcceptanceOperationRequest.__dataclass_fields__


@pytest.mark.parametrize(
    "change",
    [
        {"deployment_run_id": "run-readable-name"},
        {"platform_url": "https://aileron.example.test/path"},
        {"platform_url": "https://aileron.example.test?query=1"},
        {"issuer_url": "https://user@identity.example.test/realms/aileron"},
        {"issuer_url": "https://identity.example.test/realms/aileron?query=1"},
        {"admin_console_url": None},
        {"admin_console_url": "http://identity-admin.example.test/admin/"},
        {"admin_console_url": "https://user@identity-admin.example.test/admin/"},
    ],
)
def test_request_identity_and_url_contract_fail_closed(
    tmp_path: Path,
    change: dict[str, str],
) -> None:
    request = replace(
        _request(tmp_path, authentication_mode="bundledKeycloak"),
        **change,
    )
    safety = RecordingSafety(tmp_path / "private")

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceInputInvalid$",
    ):
        MODULE.execute_acceptance_operation(request, safety=safety)

    assert safety.events == []


def test_external_oidc_rejects_an_admin_console_url(tmp_path: Path) -> None:
    request = replace(
        _request(tmp_path, authentication_mode="externalOidc"),
        admin_console_url="https://identity-admin.example.test/admin/master/console/",
    )

    with pytest.raises(
        MODULE.AcceptanceOperationError,
        match="^acceptanceInputInvalid$",
    ):
        MODULE.execute_acceptance_operation(
            request,
            safety=RecordingSafety(tmp_path / "private"),
        )
