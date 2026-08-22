"""Execute the complete HomeLab acceptance contract behind one typed seam."""

from __future__ import annotations

import base64
import binascii
import copy
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

try:
    from scripts.deploy.rke2 import acceptance_bundle as ACCEPTANCE_BUNDLE
    from scripts.deploy.rke2 import acceptance_cluster as ACCEPTANCE_CLUSTER
    from scripts.deploy.rke2 import acceptance_epoch as ACCEPTANCE_EPOCH
    from scripts.deploy.rke2 import acceptance_evidence as ACCEPTANCE_EVIDENCE
    from scripts.deploy.rke2 import acceptance_private_io as PRIVATE_IO
    from scripts.deploy.rke2 import acceptance_producer as ACCEPTANCE_PRODUCER
    from scripts.deploy.rke2 import prepare_browser_input as BROWSER_INPUT
except (
    ModuleNotFoundError
) as exc:  # Direct import from the deployment script directory.
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import acceptance_bundle as ACCEPTANCE_BUNDLE  # type: ignore[no-redef]
    import acceptance_cluster as ACCEPTANCE_CLUSTER  # type: ignore[no-redef]
    import acceptance_epoch as ACCEPTANCE_EPOCH  # type: ignore[no-redef]
    import acceptance_evidence as ACCEPTANCE_EVIDENCE  # type: ignore[no-redef]
    import acceptance_private_io as PRIVATE_IO  # type: ignore[no-redef]
    import acceptance_producer as ACCEPTANCE_PRODUCER  # type: ignore[no-redef]
    import prepare_browser_input as BROWSER_INPUT  # type: ignore[no-redef]


BrowserLoginDriver = BROWSER_INPUT.BrowserLoginDriver

__all__ = [
    "AcceptanceOperationError",
    "AcceptanceOperationRequest",
    "AcceptanceOperationResult",
    "AcceptanceSafetyOperations",
    "BrowserLoginDriver",
    "ValidatedAcceptanceBundle",
    "ValidatedAcceptanceReport",
    "WorkspaceIdentity",
    "execute_acceptance_operation",
]

CONTRACT_PATH = (
    Path(__file__).resolve().with_name("deployment-acceptance-contract.json")
)
CONTRACT_VERSION = "aileron-homelab-acceptance/v11"
JOURNAL_SCHEMA = "aileron-acceptance-operation-journal/v4"
JOURNAL_NAME = "acceptance-operation-journal.json"
BROWSER_CA_NAME = "browser-ca-bundle.pem"
BUNDLE_NAME = "deployment-acceptance-bundle.json"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_ID = re.compile(r"^run-[0-9a-f]{32}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
SAFE_CODE = re.compile(r"^[a-z][A-Za-z0-9]{0,63}$")
PEM_CERTIFICATE = re.compile(
    rb"-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\r\n]+?)\s*"
    rb"-----END CERTIFICATE-----"
)
AUTHENTICATION_MODES = frozenset({"bundledKeycloak", "externalOidc"})
BROWSER_SECTIONS = frozenset(
    {
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "workspaceLifecycle",
        "adminDisableLogin",
    }
)
MUTATING_SECTIONS = frozenset(
    {
        "cleanReset",
        "imageRelease",
        "identity",
        "oidcWorkspace",
        "turn",
        "workspaceLifecycle",
        "restart",
        "adminDisableLogin",
    }
)


class AcceptanceOperationError(RuntimeError):
    """Expose one stable failure code without adapter diagnostics."""

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or SAFE_CODE.fullmatch(code) is None:
            code = "acceptanceOperationFailed"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class WorkspaceIdentity:
    """The sole Workspace identity established by the OIDC probe."""

    id: str
    user_subject: str


@dataclass(frozen=True)
class AcceptanceOperationRequest:
    """Complete, mode-neutral input for one acceptance run."""

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
    browser_login_driver: BrowserLoginDriver
    browser_login_username: Path | None = None
    browser_login_password: Path | None = None


@dataclass(frozen=True)
class ValidatedAcceptanceReport:
    """A fully validated canonical producer report."""

    section: str
    path: Path
    sha256: str
    workspace: WorkspaceIdentity | None


@dataclass(frozen=True)
class ValidatedAcceptanceBundle:
    """A fully validated canonical deployment acceptance bundle."""

    path: Path
    sha256: str
    workspace: WorkspaceIdentity


@dataclass(frozen=True)
class AcceptanceOperationResult:
    """The final acceptance result returned to the lifecycle caller."""

    bundle_path: Path
    bundle_sha256: str
    workspace: WorkspaceIdentity
    completed_sections: tuple[str, ...]
    reused_sections: tuple[str, ...]


class AcceptanceSafetyOperations(Protocol):
    """Internal production/test adapter seam for acceptance safety modules."""

    private_root: Path

    def load_contract(self) -> dict[str, Any]:
        """Load the canonical acceptance contract."""

    def validate_report(
        self,
        request: AcceptanceOperationRequest,
        section: str,
        workspace: WorkspaceIdentity | None,
    ) -> ValidatedAcceptanceReport | None:
        """Return a fully validated report, or None only when it is absent."""

    def prepare_browser_input(self, request: AcceptanceOperationRequest) -> Path:
        """Prepare or exactly resume canonical private browser input."""

    def produce_report(
        self,
        request: AcceptanceOperationRequest,
        section: str,
        workspace: WorkspaceIdentity | None,
        browser_ca: Path | None,
    ) -> None:
        """Run one existing report producer."""

    def bundle_exists(self, request: AcceptanceOperationRequest) -> bool:
        """Return whether any canonical bundle directory entry exists."""

    def build_bundle(self, request: AcceptanceOperationRequest) -> Path:
        """Build and atomically publish the canonical bundle."""

    def validate_bundle(
        self, request: AcceptanceOperationRequest
    ) -> ValidatedAcceptanceBundle:
        """Fully validate and return the canonical bundle."""


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _valid_text(value: Any, *, maximum: int = 4096) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum
        and value == value.strip()
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _https_url(value: str, *, allow_path: bool) -> bool:
    if not isinstance(value, str) or any(
        character.isspace() or character == "\\" for character in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.netloc == parsed.netloc.strip()
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and (allow_path or parsed.path == "")
        and (port is None or 1 <= port <= 65535)
    )


def _validate_request(request: AcceptanceOperationRequest) -> None:
    if not isinstance(request, AcceptanceOperationRequest):
        raise AcceptanceOperationError("acceptanceInputInvalid")
    pair_complete = (request.browser_login_username is None) == (
        request.browser_login_password is None
    )
    if (
        FULL_SHA.fullmatch(request.expected_commit) is None
        or RUN_ID.fullmatch(request.deployment_run_id) is None
        or request.authentication_mode not in AUTHENTICATION_MODES
        or not _valid_text(request.context, maximum=253)
        or not _https_url(request.platform_url, allow_path=False)
        or not _https_url(request.issuer_url, allow_path=True)
        or (
            request.authentication_mode == "bundledKeycloak"
            and not _https_url(request.admin_console_url, allow_path=True)
        )
        or (
            request.authentication_mode == "externalOidc"
            and request.admin_console_url is not None
        )
        or not _valid_text(request.client_id, maximum=512)
        or DIGEST.fullmatch(request.reset_snapshot_digest) is None
        or not pair_complete
        or (
            request.authentication_mode == "bundledKeycloak"
            and request.identity_artifacts_directory is None
        )
        or (
            request.authentication_mode == "externalOidc"
            and request.identity_artifacts_directory is not None
        )
    ):
        raise AcceptanceOperationError("acceptanceInputInvalid")
    try:
        driver = request.browser_login_driver.to_document()
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceInputInvalid") from exc
    files_selected = request.browser_login_username is not None
    if request.authentication_mode == "bundledKeycloak":
        valid_login = (
            request.browser_login_mode == "breakGlass"
            and not files_selected
            or request.browser_login_mode == "files"
            and files_selected
        )
        driver_valid = driver == {"kind": "keycloak"}
    else:
        valid_login = request.browser_login_mode == "files" and files_selected
        driver_valid = driver.get("kind") == "form"
    if not valid_login or not driver_valid:
        raise AcceptanceOperationError("acceptanceInputInvalid")
    for path in (
        request.kubeconfig,
        request.image_inventory,
        request.apps_ca,
        request.oidc_ca,
        request.identity_artifacts_directory,
        request.browser_login_username,
        request.browser_login_password,
    ):
        if path is not None and (not isinstance(path, Path) or not path.is_absolute()):
            raise AcceptanceOperationError("acceptanceInputInvalid")


def _active_sections(
    contract: dict[str, Any], authentication_mode: str
) -> tuple[str, ...]:
    try:
        if (
            contract.get("contractVersion") != CONTRACT_VERSION
            or authentication_mode not in AUTHENTICATION_MODES
        ):
            raise ValueError
        common = contract["commonRequiredReports"]
        mode_reports = contract["modeRequiredReports"][authentication_mode]
        edges = contract["causalEdges"]
        roots = contract["causalRoots"]
        active = set(common) | set(mode_reports)
        declared = set(common)
        for declared_mode_reports in contract["modeRequiredReports"].values():
            declared.update(declared_mode_reports)
        if (
            not isinstance(common, list)
            or not isinstance(mode_reports, list)
            or not isinstance(edges, list)
            or not isinstance(roots, list)
            or len(active) != len(common) + len(mode_reports)
            or any(not _valid_text(section, maximum=64) for section in active)
        ):
            raise ValueError
        ordered_nodes: list[str] = []
        for section in roots:
            if section in active and section not in ordered_nodes:
                ordered_nodes.append(section)
        parsed_edges: list[tuple[str, str]] = []
        for edge in edges:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError
            if edge[0] not in declared or edge[1] not in declared:
                raise ValueError
            if edge[0] not in active or edge[1] not in active:
                continue
            predecessor, successor = edge
            if predecessor in active and successor in active:
                parsed_edges.append((predecessor, successor))
                for section in (predecessor, successor):
                    if section not in ordered_nodes:
                        ordered_nodes.append(section)
        if set(ordered_nodes) != active or set(roots) - active:
            raise ValueError
        predecessors = {
            section: {
                predecessor
                for predecessor, successor in parsed_edges
                if successor == section
            }
            for section in active
        }
        remaining = set(active)
        completed: set[str] = set()
        result: list[str] = []
        while remaining:
            layer = [
                section
                for section in ordered_nodes
                if section in remaining and predecessors[section] <= completed
            ]
            if not layer:
                raise ValueError
            result.extend(layer)
            completed.update(layer)
            remaining.difference_update(layer)
        terminals = set(contract["modeTerminalReports"][authentication_mode])
        if terminals != {
            section
            for section in active
            if not any(predecessor == section for predecessor, _ in parsed_edges)
        }:
            raise ValueError
        return tuple(result)
    except (KeyError, TypeError, ValueError) as exc:
        raise AcceptanceOperationError("acceptanceContractInvalid") from exc


def _evidence_directory(
    request: AcceptanceOperationRequest, *, private_root: Path
) -> Path:
    try:
        return PRIVATE_IO.ensure_evidence_directory(
            private_root=private_root,
            commit=request.expected_commit,
            deployment_run_id=request.deployment_run_id,
            error_type=AcceptanceOperationError,
        )
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceOperationStateInvalid") from exc


def _held_report_metadata(
    descriptor: int,
    path: Path,
    *,
    expected_link_counts: frozenset[int],
) -> os.stat_result:
    try:
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(path)
    except OSError as exc:
        raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
            "acceptance report recovery snapshot changed"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
        or path_metadata.st_uid != os.geteuid()
        or metadata.st_nlink not in expected_link_counts
        or metadata.st_dev != path_metadata.st_dev
        or metadata.st_ino != path_metadata.st_ino
    ):
        raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
            "acceptance report recovery snapshot metadata is invalid"
        )
    return metadata


@contextmanager
def _recovered_soak_report_snapshot(
    path: Path, *, private_root: Path
) -> Iterator[bytes | None]:
    """Pin and read the exact soak inode across recovery and validation."""

    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                "acceptance report recovery snapshot is unreadable"
            ) from exc
        if descriptor is not None:
            _held_report_metadata(
                descriptor,
                path,
                expected_link_counts=frozenset({1, 2}),
            )

        ACCEPTANCE_PRODUCER.recover_atomic_report_publication(
            path,
            private_root=private_root,
        )
        if descriptor is None:
            try:
                os.lstat(path)
            except FileNotFoundError:
                yield None
                return
            except OSError as exc:
                raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                    "acceptance report recovery final state is unreadable"
                ) from exc
            raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                "acceptance report recovery final state appeared concurrently"
            )

        before = _held_report_metadata(
            descriptor,
            path,
            expected_link_counts=frozenset({1}),
        )
        maximum_size = 4 * 1024 * 1024
        if before.st_size == 0 or before.st_size > maximum_size:
            raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                "acceptance report recovery snapshot size is invalid"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_size + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_size:
                raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                    "acceptance report recovery snapshot is too large"
                )
        after = _held_report_metadata(
            descriptor,
            path,
            expected_link_counts=frozenset({1}),
        )
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(
                getattr(before, field) != getattr(after, field)
                for field in stable_fields
            )
            or total != after.st_size
        ):
            raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                "acceptance report recovery snapshot changed while it was read"
            )
        yield b"".join(chunks)
        final_metadata = _held_report_metadata(
            descriptor,
            path,
            expected_link_counts=frozenset({1}),
        )
        if any(
            getattr(after, field) != getattr(final_metadata, field)
            for field in stable_fields
        ):
            raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
                "acceptance report recovery snapshot changed during validation"
            )
    except OSError as exc:
        raise ACCEPTANCE_PRODUCER.AcceptanceProducerError(
            "acceptance report recovery snapshot is unreadable"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


@contextmanager
def _operation_lock(directory: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(directory)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()
            or metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise OSError("invalid operation directory")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    except BlockingIOError as exc:
        raise AcceptanceOperationError("acceptanceOperationBusy") from exc
    except AcceptanceOperationError:
        raise
    except OSError as exc:
        raise AcceptanceOperationError("acceptanceOperationStateInvalid") from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _initial_journal(
    request: AcceptanceOperationRequest, sections: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "schemaVersion": JOURNAL_SCHEMA,
        "contractVersion": CONTRACT_VERSION,
        "commit": request.expected_commit,
        "deploymentRunId": request.deployment_run_id,
        "authenticationMode": request.authentication_mode,
        "pointOfNoReturn": False,
        "sections": [
            {
                "section": section,
                "status": "pending",
                "attempts": 0,
                "reportSha256": None,
                "lastErrorCode": None,
            }
            for section in sections
        ],
        "bundle": {
            "status": "pending",
            "attempts": 0,
            "sha256": None,
            "lastErrorCode": None,
        },
    }


def _validate_journal(
    document: dict[str, Any],
    *,
    request: AcceptanceOperationRequest,
    sections: tuple[str, ...],
) -> None:
    expected_keys = {
        "schemaVersion",
        "contractVersion",
        "commit",
        "deploymentRunId",
        "authenticationMode",
        "pointOfNoReturn",
        "sections",
        "bundle",
    }
    if (
        set(document) != expected_keys
        or document.get("schemaVersion") != JOURNAL_SCHEMA
        or document.get("contractVersion") != CONTRACT_VERSION
        or document.get("commit") != request.expected_commit
        or document.get("deploymentRunId") != request.deployment_run_id
        or document.get("authenticationMode") != request.authentication_mode
        or not isinstance(document.get("pointOfNoReturn"), bool)
        or not isinstance(document.get("sections"), list)
        or len(document["sections"]) != len(sections)
    ):
        raise AcceptanceOperationError("acceptanceOperationJournalInvalid")
    for expected, item in zip(sections, document["sections"]):
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "section",
                "status",
                "attempts",
                "reportSha256",
                "lastErrorCode",
            }
            or item.get("section") != expected
            or item.get("status") not in {"pending", "started", "completed"}
            or isinstance(item.get("attempts"), bool)
            or not isinstance(item.get("attempts"), int)
            or item["attempts"] < 0
            or (item["status"] == "pending" and item["attempts"] != 0)
            or (
                item.get("reportSha256") is not None
                and DIGEST.fullmatch(item["reportSha256"]) is None
            )
            or (
                item.get("lastErrorCode") is not None
                and SAFE_CODE.fullmatch(item["lastErrorCode"]) is None
            )
            or (item["status"] == "completed" and item.get("reportSha256") is None)
        ):
            raise AcceptanceOperationError("acceptanceOperationJournalInvalid")
    bundle = document.get("bundle")
    if (
        not isinstance(bundle, dict)
        or set(bundle) != {"status", "attempts", "sha256", "lastErrorCode"}
        or bundle.get("status") not in {"pending", "started", "completed"}
        or isinstance(bundle.get("attempts"), bool)
        or not isinstance(bundle.get("attempts"), int)
        or bundle["attempts"] < 0
        or (bundle["status"] == "pending" and bundle["attempts"] != 0)
        or (
            bundle.get("sha256") is not None
            and DIGEST.fullmatch(bundle["sha256"]) is None
        )
        or (
            bundle.get("lastErrorCode") is not None
            and SAFE_CODE.fullmatch(bundle["lastErrorCode"]) is None
        )
        or (bundle["status"] == "completed" and bundle.get("sha256") is None)
    ):
        raise AcceptanceOperationError("acceptanceOperationJournalInvalid")


def _replace_journal(
    path: Path, document: dict[str, Any], *, private_root: Path
) -> None:
    content = _canonical(document)
    temporary = path.parent / f".{JOURNAL_NAME}.{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    replaced = False
    try:
        PRIVATE_IO.PRIVATE_INPUT.validate_private_file(
            path,
            "acceptance operation journal",
            private_root=private_root,
        )
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("journal write made no progress")
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        replaced = True
        directory_descriptor = os.open(
            path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceOperationJournalWriteFailed") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not replaced:
            try:
                temporary.unlink()
            except OSError:
                pass


def _load_or_create_journal(
    directory: Path,
    *,
    request: AcceptanceOperationRequest,
    sections: tuple[str, ...],
    private_root: Path,
) -> tuple[Path, dict[str, Any]]:
    path = directory / JOURNAL_NAME
    try:
        os.lstat(path)
    except FileNotFoundError:
        document = _initial_journal(request, sections)
        try:
            PRIVATE_IO.write_private_snapshot(
                destination=path,
                content=_canonical(document),
                description="acceptance operation journal",
                private_root=private_root,
                error_type=AcceptanceOperationError,
            )
        except Exception as exc:
            raise AcceptanceOperationError(
                "acceptanceOperationJournalWriteFailed"
            ) from exc
        return path, document
    except OSError as exc:
        raise AcceptanceOperationError("acceptanceOperationJournalInvalid") from exc
    try:
        raw = PRIVATE_IO.read_private_bytes(
            path,
            "acceptance operation journal",
            private_root=private_root,
            error_type=AcceptanceOperationError,
            maximum_size=256 * 1024,
        )
        document = PRIVATE_IO.load_json_object(
            raw,
            "acceptance operation journal",
            error_type=AcceptanceOperationError,
            require_canonical=True,
        )
        _validate_journal(document, request=request, sections=sections)
        return path, document
    except AcceptanceOperationError as exc:
        if exc.code == "acceptanceOperationJournalInvalid":
            raise
        raise AcceptanceOperationError("acceptanceOperationJournalInvalid") from exc
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceOperationJournalInvalid") from exc


def _journal_item(journal: dict[str, Any], section: str) -> dict[str, Any]:
    return next(item for item in journal["sections"] if item["section"] == section)


def _store_journal(
    path: Path, journal: dict[str, Any], *, private_root: Path
) -> dict[str, Any]:
    _replace_journal(path, journal, private_root=private_root)
    return journal


def _start_section(
    path: Path,
    journal: dict[str, Any],
    *,
    section: str,
    private_root: Path,
) -> dict[str, Any]:
    updated = copy.deepcopy(journal)
    item = _journal_item(updated, section)
    item.update(
        {
            "status": "started",
            "attempts": item["attempts"] + 1,
            "reportSha256": None,
            "lastErrorCode": None,
        }
    )
    if section == "adminDisableLogin":
        updated["pointOfNoReturn"] = True
    return _store_journal(path, updated, private_root=private_root)


def _complete_section(
    path: Path,
    journal: dict[str, Any],
    *,
    report: ValidatedAcceptanceReport,
    private_root: Path,
) -> dict[str, Any]:
    updated = copy.deepcopy(journal)
    item = _journal_item(updated, report.section)
    item.update(
        {
            "status": "completed",
            "reportSha256": report.sha256,
            "lastErrorCode": None,
        }
    )
    return _store_journal(path, updated, private_root=private_root)


def _record_section_error(
    path: Path,
    journal: dict[str, Any],
    *,
    section: str,
    code: str,
    private_root: Path,
) -> dict[str, Any]:
    updated = copy.deepcopy(journal)
    _journal_item(updated, section)["lastErrorCode"] = code
    return _store_journal(path, updated, private_root=private_root)


def _start_bundle(
    path: Path, journal: dict[str, Any], *, private_root: Path
) -> dict[str, Any]:
    updated = copy.deepcopy(journal)
    updated["bundle"] = {
        "status": "started",
        "attempts": updated["bundle"]["attempts"] + 1,
        "sha256": None,
        "lastErrorCode": None,
    }
    return _store_journal(path, updated, private_root=private_root)


def _complete_bundle(
    path: Path,
    journal: dict[str, Any],
    *,
    bundle: ValidatedAcceptanceBundle,
    private_root: Path,
) -> dict[str, Any]:
    updated = copy.deepcopy(journal)
    updated["bundle"] = {
        "status": "completed",
        "attempts": max(1, updated["bundle"]["attempts"]),
        "sha256": bundle.sha256,
        "lastErrorCode": None,
    }
    return _store_journal(path, updated, private_root=private_root)


def _der_length_is_exact(content: bytes) -> bool:
    if len(content) < 4 or content[0] != 0x30:
        return False
    first = content[1]
    if first < 0x80:
        header = 2
        length = first
    else:
        length_bytes = first & 0x7F
        if length_bytes == 0 or length_bytes > 4 or len(content) < 2 + length_bytes:
            return False
        header = 2 + length_bytes
        length = int.from_bytes(content[2:header], "big")
        if length < 0x80:
            return False
    return header + length == len(content)


def _parse_certificate_bundle(content: bytes) -> list[bytes]:
    certificates: list[bytes] = []
    cursor = 0
    for match in PEM_CERTIFICATE.finditer(content):
        if content[cursor : match.start()].strip():
            raise AcceptanceOperationError("acceptanceBrowserTrustInvalid")
        encoded = re.sub(rb"\s+", b"", match.group(1))
        try:
            der = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise AcceptanceOperationError("acceptanceBrowserTrustInvalid") from exc
        if not _der_length_is_exact(der):
            raise AcceptanceOperationError("acceptanceBrowserTrustInvalid")
        certificates.append(der)
        cursor = match.end()
    if not certificates or content[cursor:].strip():
        raise AcceptanceOperationError("acceptanceBrowserTrustInvalid")
    return certificates


def _canonical_pem(certificate: bytes) -> bytes:
    encoded = base64.b64encode(certificate)
    lines = [encoded[index : index + 64] for index in range(0, len(encoded), 64)]
    return (
        b"-----BEGIN CERTIFICATE-----\n"
        + b"\n".join(lines)
        + b"\n-----END CERTIFICATE-----\n"
    )


def _browser_ca_bundle(
    request: AcceptanceOperationRequest,
    *,
    directory: Path,
    private_root: Path,
) -> Path:
    def read_sources() -> tuple[bytes, bytes]:
        return tuple(  # type: ignore[return-value]
            PRIVATE_IO.read_private_bytes(
                source,
                description,
                private_root=private_root,
                error_type=AcceptanceOperationError,
                maximum_size=1024 * 1024,
                require_nonempty=True,
            )
            for source, description in (
                (request.apps_ca, "Apps ingress CA"),
                (request.oidc_ca, "OIDC CA"),
            )
        )

    try:
        first = read_sources()
        ordered: list[bytes] = []
        seen: set[str] = set()
        for source in first:
            for certificate in _parse_certificate_bundle(source):
                digest = hashlib.sha256(certificate).hexdigest()
                if digest not in seen:
                    seen.add(digest)
                    ordered.append(certificate)
        content = b"".join(_canonical_pem(certificate) for certificate in ordered)
        if read_sources() != first:
            raise AcceptanceOperationError("acceptanceBrowserTrustChanged")
        return PRIVATE_IO.write_private_snapshot(
            destination=directory / BROWSER_CA_NAME,
            content=content,
            description="browser acceptance CA bundle",
            private_root=private_root,
            error_type=AcceptanceOperationError,
            allow_existing_exact=True,
        )
    except AcceptanceOperationError:
        raise
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceBrowserTrustInvalid") from exc


def _report_identity(
    report: ValidatedAcceptanceReport,
    *,
    section: str,
    workspace: WorkspaceIdentity | None,
    workspace_scoped: bool,
) -> WorkspaceIdentity | None:
    if (
        not isinstance(report, ValidatedAcceptanceReport)
        or report.section != section
        or DIGEST.fullmatch(report.sha256) is None
        or not isinstance(report.path, Path)
    ):
        raise AcceptanceOperationError("acceptanceReportInvalid")
    if not workspace_scoped:
        if report.workspace is not None:
            raise AcceptanceOperationError("acceptanceReportInvalid")
        return workspace
    if section == "oidcWorkspace":
        candidate = report.workspace
        if (
            not isinstance(candidate, WorkspaceIdentity)
            or not _valid_text(candidate.id, maximum=253)
            or not _valid_text(candidate.user_subject, maximum=2048)
        ):
            raise AcceptanceOperationError("acceptanceWorkspaceIdentityInvalid")
        if workspace is not None and candidate != workspace:
            raise AcceptanceOperationError("acceptanceWorkspaceIdentityMismatch")
        return candidate
    if workspace is None or report.workspace != workspace:
        raise AcceptanceOperationError("acceptanceWorkspaceIdentityMismatch")
    return workspace


def _result(
    bundle: ValidatedAcceptanceBundle,
    *,
    sections: tuple[str, ...],
    reused: tuple[str, ...],
) -> AcceptanceOperationResult:
    if (
        not isinstance(bundle, ValidatedAcceptanceBundle)
        or not isinstance(bundle.path, Path)
        or DIGEST.fullmatch(bundle.sha256) is None
        or not isinstance(bundle.workspace, WorkspaceIdentity)
    ):
        raise AcceptanceOperationError("acceptanceFinalValidationFailed")
    return AcceptanceOperationResult(
        bundle_path=bundle.path,
        bundle_sha256=bundle.sha256,
        workspace=bundle.workspace,
        completed_sections=sections,
        reused_sections=reused,
    )


def _validated_existing_bundle(
    request: AcceptanceOperationRequest,
    *,
    safety: AcceptanceSafetyOperations,
) -> ValidatedAcceptanceBundle:
    try:
        return safety.validate_bundle(request)
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceExistingBundleInvalid") from exc


def execute_acceptance_operation(
    request: AcceptanceOperationRequest,
    *,
    safety: AcceptanceSafetyOperations | None = None,
) -> AcceptanceOperationResult:
    """Execute or safely resume every active v11 acceptance report and bundle."""

    _validate_request(request)
    operations = safety or _ProductionAcceptanceSafetyOperations()
    try:
        private_root = PRIVATE_IO.PRIVATE_INPUT.private_root_path(
            operations.private_root
        )
        contract = operations.load_contract()
    except Exception as exc:
        raise AcceptanceOperationError("acceptanceOperationStateInvalid") from exc
    sections = _active_sections(contract, request.authentication_mode)
    workspace_scoped = set(contract.get("workspaceScopedReports", []))
    directory = _evidence_directory(request, private_root=private_root)

    with _operation_lock(directory):
        journal_path, journal = _load_or_create_journal(
            directory,
            request=request,
            sections=sections,
            private_root=private_root,
        )
        try:
            existing_bundle = operations.bundle_exists(request)
        except Exception as exc:
            raise AcceptanceOperationError("acceptanceOperationStateInvalid") from exc
        if existing_bundle:
            bundle = _validated_existing_bundle(request, safety=operations)
            journal = _complete_bundle(
                journal_path,
                journal,
                bundle=bundle,
                private_root=private_root,
            )
            return _result(bundle, sections=sections, reused=sections)

        workspace: WorkspaceIdentity | None = None
        reused: list[str] = []
        browser_ready = False
        browser_ca: Path | None = None
        for section in sections:
            item = _journal_item(journal, section)
            try:
                report = operations.validate_report(request, section, workspace)
            except Exception as exc:
                if section == "adminDisableLogin" and item["status"] == "started":
                    raise AcceptanceOperationError(
                        "acceptanceBreakGlassRestorationUncertain"
                    ) from exc
                if section in MUTATING_SECTIONS and item["status"] == "started":
                    raise AcceptanceOperationError(
                        "acceptanceReportResumeAmbiguous"
                    ) from exc
                raise AcceptanceOperationError("acceptanceReportInvalid") from exc
            if report is not None:
                workspace = _report_identity(
                    report,
                    section=section,
                    workspace=workspace,
                    workspace_scoped=section in workspace_scoped,
                )
                journal = _complete_section(
                    journal_path,
                    journal,
                    report=report,
                    private_root=private_root,
                )
                reused.append(section)
                continue
            if section == "adminDisableLogin" and item["status"] == "started":
                raise AcceptanceOperationError(
                    "acceptanceBreakGlassRestorationUncertain"
                )
            if section in MUTATING_SECTIONS and item["status"] == "started":
                raise AcceptanceOperationError("acceptanceReportResumeAmbiguous")
            if item["status"] == "completed":
                raise AcceptanceOperationError("acceptanceOperationJournalInvalid")
            if section in BROWSER_SECTIONS and not browser_ready:
                try:
                    operations.prepare_browser_input(request)
                    browser_ca = _browser_ca_bundle(
                        request,
                        directory=directory,
                        private_root=private_root,
                    )
                except Exception as exc:
                    if isinstance(exc, AcceptanceOperationError):
                        raise
                    raise AcceptanceOperationError("acceptanceInputInvalid") from exc
                browser_ready = True
            journal = _start_section(
                journal_path,
                journal,
                section=section,
                private_root=private_root,
            )
            try:
                operations.produce_report(
                    request,
                    section,
                    workspace,
                    browser_ca if section in BROWSER_SECTIONS else None,
                )
                produced = operations.validate_report(request, section, workspace)
                if produced is None:
                    raise RuntimeError("producer returned without a report")
                workspace = _report_identity(
                    produced,
                    section=section,
                    workspace=workspace,
                    workspace_scoped=section in workspace_scoped,
                )
            except Exception as exc:
                code = (
                    "acceptanceBreakGlassRestorationUncertain"
                    if section == "adminDisableLogin"
                    else "acceptanceReportProductionFailed"
                )
                journal = _record_section_error(
                    journal_path,
                    journal,
                    section=section,
                    code=code,
                    private_root=private_root,
                )
                raise AcceptanceOperationError(code) from exc
            journal = _complete_section(
                journal_path,
                journal,
                report=produced,
                private_root=private_root,
            )

        if workspace is None:
            raise AcceptanceOperationError("acceptanceWorkspaceIdentityInvalid")
        try:
            raced_bundle = operations.bundle_exists(request)
        except Exception as exc:
            raise AcceptanceOperationError("acceptanceOperationStateInvalid") from exc
        if raced_bundle:
            bundle = _validated_existing_bundle(request, safety=operations)
        else:
            journal = _start_bundle(journal_path, journal, private_root=private_root)
            try:
                operations.build_bundle(request)
            except Exception as exc:  # noqa: BLE001 - normalize the adapter boundary.
                try:
                    if operations.bundle_exists(request):
                        bundle = _validated_existing_bundle(request, safety=operations)
                    else:
                        raise AcceptanceOperationError(
                            "acceptanceBundlePublicationFailed"
                        ) from exc
                except AcceptanceOperationError:
                    raise
                except Exception as inspection_error:
                    raise AcceptanceOperationError(
                        "acceptanceBundlePublicationFailed"
                    ) from inspection_error
            else:
                try:
                    bundle = operations.validate_bundle(request)
                except Exception as exc:
                    raise AcceptanceOperationError(
                        "acceptanceFinalValidationFailed"
                    ) from exc
        if bundle.workspace != workspace:
            raise AcceptanceOperationError("acceptanceWorkspaceIdentityMismatch")
        journal = _complete_bundle(
            journal_path,
            journal,
            bundle=bundle,
            private_root=private_root,
        )
        return _result(bundle, sections=sections, reused=tuple(reused))


class _ProductionAcceptanceSafetyOperations:
    """Adapt the existing acceptance safety modules to the internal seam."""

    def __init__(self) -> None:
        self.private_root = ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT

    def load_contract(self) -> dict[str, Any]:
        return ACCEPTANCE_EVIDENCE.load_canonical_contract(CONTRACT_PATH)

    def _validation_context(
        self, request: AcceptanceOperationRequest
    ) -> tuple[Path, Path, dict[str, Any], dict[str, Any], Any]:
        directory = PRIVATE_IO.evidence_directory(
            private_root=self.private_root,
            commit=request.expected_commit,
            deployment_run_id=request.deployment_run_id,
            error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
        )
        canonical = PRIVATE_IO.validate_canonical_kubeconfig(
            directory=directory,
            private_root=self.private_root,
            commit=request.expected_commit,
            deployment_run_id=request.deployment_run_id,
            context=request.context,
            error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
        )
        trust = ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
            context=request.context,
            kubeconfig=canonical.path,
        )
        epoch = ACCEPTANCE_EPOCH.load_deployment_epoch(
            directory=directory,
            private_root=self.private_root,
            key=trust.key,
            commit=request.expected_commit,
            cluster_uid=trust.cluster_uid,
            context=request.context,
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=request.deployment_run_id,
        )
        if (
            epoch.get("authenticationMode") != request.authentication_mode
            or epoch.get("resetSnapshotSha256") != request.reset_snapshot_digest
        ):
            raise ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError(
                "acceptance operation epoch identity does not match"
            )
        return directory, canonical.path, self.load_contract(), epoch, trust

    def validate_report(
        self,
        request: AcceptanceOperationRequest,
        section: str,
        workspace: WorkspaceIdentity | None,
    ) -> ValidatedAcceptanceReport | None:
        directory = PRIVATE_IO.evidence_directory(
            private_root=self.private_root,
            commit=request.expected_commit,
            deployment_run_id=request.deployment_run_id,
            error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
        )
        path = directory / f"{section}.json"
        with ExitStack() as snapshots:
            soak_raw: bytes | None = None
            if section == "soak":
                soak_raw = snapshots.enter_context(
                    _recovered_soak_report_snapshot(
                        path,
                        private_root=self.private_root,
                    )
                )
                if soak_raw is None:
                    return None
            else:
                try:
                    os.lstat(path)
                except FileNotFoundError:
                    return None
            directory, canonical_kubeconfig, contract, epoch, trust = (
                self._validation_context(request)
            )
            expected_workspace = (
                {"id": workspace.id, "userSubject": workspace.user_subject}
                if workspace is not None
                else None
            )
            if section == "oidcWorkspace" and workspace is None:
                raw = PRIVATE_IO.read_private_bytes(
                    path,
                    "oidcWorkspace report",
                    private_root=self.private_root,
                    error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
                    maximum_size=4 * 1024 * 1024,
                )
                candidate = PRIVATE_IO.load_json_object(
                    raw,
                    "oidcWorkspace report",
                    error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
                    require_canonical=True,
                ).get("workspace")
                if isinstance(candidate, dict):
                    expected_workspace = candidate
            validation_arguments = {
                "directory": directory,
                "section": section,
                "contract": contract,
                "expected_commit": request.expected_commit,
                "epoch": epoch,
                "signing_key": trust.key,
                "private_root": self.private_root,
                "canonical_kubeconfig": canonical_kubeconfig,
                "workspace": expected_workspace,
            }
            validated = (
                ACCEPTANCE_EVIDENCE.validate_report_bytes(
                    raw=soak_raw,
                    **validation_arguments,
                )
                if soak_raw is not None
                else ACCEPTANCE_EVIDENCE.validate_report_file(
                    **validation_arguments,
                )
            )
            report_workspace = validated["report"].get("workspace")
            identity = (
                WorkspaceIdentity(
                    id=report_workspace["id"],
                    user_subject=report_workspace["userSubject"],
                )
                if isinstance(report_workspace, dict)
                else None
            )
            return ValidatedAcceptanceReport(
                section=section,
                path=validated["path"],
                sha256=validated["sha256"],
                workspace=identity,
            )

    def prepare_browser_input(self, request: AcceptanceOperationRequest) -> Path:
        return BROWSER_INPUT.prepare_browser_input(
            BROWSER_INPUT.BrowserInputRequest(
                expected_commit=request.expected_commit,
                deployment_run_id=request.deployment_run_id,
                authentication_mode=request.authentication_mode,
                login_mode=request.browser_login_mode,
                login_driver=request.browser_login_driver,
                identity_artifacts_directory=request.identity_artifacts_directory,
                login_username_file=request.browser_login_username,
                login_password_file=request.browser_login_password,
            ),
            private_root=self.private_root,
        )

    def produce_report(
        self,
        request: AcceptanceOperationRequest,
        section: str,
        workspace: WorkspaceIdentity | None,
        browser_ca: Path | None,
    ) -> None:
        targets = ACCEPTANCE_PRODUCER.ProducerTargets(
            request.context,
            request.kubeconfig,
            workspace.id if workspace is not None else None,
            workspace.user_subject if workspace is not None else None,
            request.platform_url,
            request.issuer_url,
            request.admin_console_url,
            request.client_id,
            request.expected_commit,
        )
        arguments: dict[str, Any] = {
            "section": section,
            "targets": targets,
            "deployment_run_id": request.deployment_run_id,
            "image_inventory": request.image_inventory,
            "browser_ca": browser_ca,
            "soak_seconds": 1800,
        }
        if section == "cleanReset":
            arguments.update(
                {
                    "reset_phase": "post-reset",
                    "expected_reset_snapshot_digest": request.reset_snapshot_digest,
                }
            )
        ACCEPTANCE_PRODUCER.produce(**arguments)

    def _bundle_path(self, request: AcceptanceOperationRequest) -> Path:
        return (
            PRIVATE_IO.evidence_directory(
                private_root=self.private_root,
                commit=request.expected_commit,
                deployment_run_id=request.deployment_run_id,
                error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
            )
            / BUNDLE_NAME
        )

    def bundle_exists(self, request: AcceptanceOperationRequest) -> bool:
        try:
            os.lstat(self._bundle_path(request))
            return True
        except FileNotFoundError:
            return False

    def build_bundle(self, request: AcceptanceOperationRequest) -> Path:
        return ACCEPTANCE_BUNDLE.build_bundle(
            expected_commit=request.expected_commit,
            deployment_run_id=request.deployment_run_id,
            contract_path=CONTRACT_PATH,
            context=request.context,
        )

    def validate_bundle(
        self, request: AcceptanceOperationRequest
    ) -> ValidatedAcceptanceBundle:
        ACCEPTANCE_EVIDENCE.validate_evidence(
            request.expected_commit,
            request.deployment_run_id,
            CONTRACT_PATH,
            context=request.context,
        )
        path = self._bundle_path(request)
        raw = PRIVATE_IO.read_private_bytes(
            path,
            "acceptance bundle",
            private_root=self.private_root,
            error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
            maximum_size=4 * 1024 * 1024,
        )
        document = PRIVATE_IO.load_json_object(
            raw,
            "acceptance bundle",
            error_type=ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError,
            require_canonical=True,
        )
        workspace = document.get("workspace")
        if (
            not isinstance(workspace, dict)
            or set(workspace) != {"id", "userSubject"}
            or not all(isinstance(value, str) and value for value in workspace.values())
        ):
            raise ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError(
                "acceptance bundle workspace identity is invalid"
            )
        return ValidatedAcceptanceBundle(
            path=path,
            sha256=hashlib.sha256(raw).hexdigest(),
            workspace=WorkspaceIdentity(
                id=workspace["id"], user_subject=workspace["userSubject"]
            ),
        )
