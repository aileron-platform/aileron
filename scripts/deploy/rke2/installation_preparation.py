"""Prepare immutable inputs for one fail-closed RKE2 installation phase."""

from __future__ import annotations

import importlib.util
import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NamedTuple
from urllib.parse import urlsplit

try:
    from jsonschema import Draft7Validator
except ModuleNotFoundError:  # Deployment host prerequisite, reported at the seam.
    Draft7Validator = None  # type: ignore[assignment,misc]

try:
    from scripts.deploy.rke2 import acceptance_cluster as ACCEPTANCE_CLUSTER
    from scripts.deploy.rke2 import acceptance_release as ACCEPTANCE_RELEASE
    from scripts.deploy.rke2 import backend_attestor as BACKEND_ATTESTOR
    from scripts.deploy.rke2 import installation_state as INSTALLATION_STATE
    from scripts.deploy.rke2 import private_input as PRIVATE_INPUT
    from scripts.deploy.rke2 import render_release_values as RELEASE_VALUES
except ModuleNotFoundError as exc:
    if exc.name not in {"scripts", "scripts.deploy", "scripts.deploy.rke2"}:
        raise
    import acceptance_cluster as ACCEPTANCE_CLUSTER
    import acceptance_release as ACCEPTANCE_RELEASE
    import backend_attestor as BACKEND_ATTESTOR
    import installation_state as INSTALLATION_STATE
    import private_input as PRIVATE_INPUT
    import render_release_values as RELEASE_VALUES

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
RUNTIME_REQUIREMENTS = (
    ("jsonschema", "jsonschema==4.25.1"),
    ("yaml", "PyYAML==6.0.2"),
)
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PLATFORM_HOST_LABEL_PATTERN = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
TURN_URL_PATTERN = re.compile(
    r"^(?:turn|turns):"
    r"(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)"
    r"(?::([0-9]{1,5}))?(?:\?transport=(?:udp|tcp))?$"
)
PLATFORM_URL_PATTERN = re.compile(
    r"^https://(?:\[[0-9A-Fa-f:]+\]|"
    rf"{PLATFORM_HOST_LABEL_PATTERN}"
    rf"(?:\.{PLATFORM_HOST_LABEL_PATTERN})*)"
    r"(?::([0-9]{1,5}))?$"
)
CORE_POSTGRES_EXTERNAL_INPUTS = {"database-url", "platform-database-ca"}
CORE_REDIS_EXTERNAL_INPUTS = {
    "redis-general-url",
    "redis-job-queue-url",
    "redis-job-result-url",
    "redis-general-ca",
    "redis-job-queue-ca",
    "redis-job-result-ca",
}

CommandRunner = Callable[..., str]
InstallationIdentityValidator = Callable[..., None]


class InstallationPreparationError(RuntimeError):
    """Raised when installation inputs cannot be prepared safely."""


class InstallationRunnerError(RuntimeError):
    """Marker for runner failures that live-trust loading must conceal."""


class InstallationSources(NamedTuple):
    inventory: Path
    execution_profile: Path
    kubeconfig: Path
    harbor_dockerconfig: Path
    apps_tls_cert: Path
    apps_tls_key: Path
    apps_tls_ca: Path
    oidc_ca: Path
    core_data_service_values: Path | None = None
    identity_data_service_values: Path | None = None
    core_data_service_inputs: tuple[tuple[str, Path], ...] = ()
    identity_database_username: Path | None = None
    identity_database_password: Path | None = None
    identity_database_ca: Path | None = None


class IdentitySelection(NamedTuple):
    mode: str
    tls_cert: Path | None
    tls_key: Path | None
    external_client_secret: Path | None
    external_issuer_url: str | None
    external_client_id: str | None


class InstallationPreparationRequest(NamedTuple):
    expected_commit: str
    context: str
    registry: str
    project: str
    platform_url: str
    turn_url: str
    phase: str
    work_directory: Path
    identity_profile_schema: Path
    sources: InstallationSources
    identity: IdentitySelection


class PreparedAcceptanceTrust(NamedTuple):
    key: bytes
    cluster_uid: str
    installation_identity_sha256: str
    secret_uid: str


class PreparedSnapshots(NamedTuple):
    directory: Path
    kubeconfig: Path
    harbor_dockerconfig: Path
    apps_tls_cert: Path
    apps_tls_key: Path
    apps_tls_ca: Path
    oidc_ca: Path
    identity_tls_cert: Path | None
    identity_tls_key: Path | None
    external_oidc_client_secret: Path | None
    core_values: Path
    identity_values: Path | None
    core_data_service_inputs: tuple[tuple[str, Path], ...] = ()
    identity_database_username: Path | None = None
    identity_database_password: Path | None = None
    identity_database_ca: Path | None = None


class PreparedInstallation(NamedTuple):
    expected_commit: str
    context: str
    registry: str
    project: str
    platform_url: str
    turn_url: str
    phase: str
    private_root: Path
    secret_store: Path
    work_directory: Path
    identity_mode: str
    external_oidc_issuer_url: str | None
    snapshots: PreparedSnapshots
    acceptance_trust: PreparedAcceptanceTrust
    workspace_manager_image: str


def _validate_runtime_dependencies() -> None:
    missing = []
    for module_name, requirement in RUNTIME_REQUIREMENTS:
        try:
            available = importlib.util.find_spec(module_name) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            missing.append(requirement)
    if missing:
        raise InstallationPreparationError(
            "deployment Python runtime is missing pinned dependencies: "
            + ", ".join(missing)
        )


def _validate_private_root(private_root: Path) -> None:
    try:
        PRIVATE_INPUT.validate_installation_private_root(
            private_root,
            repository_root=REPOSITORY_ROOT,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc


def _require_private_directory(
    path: Path,
    description: str,
    private_root: Path,
) -> None:
    try:
        PRIVATE_INPUT.validate_private_directory(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc


def _within_private_root(
    path: Path,
    private_root: Path,
    description: str,
) -> None:
    try:
        path.resolve(strict=True).relative_to(private_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise InstallationPreparationError(
            f"{description} must be within the private root"
        ) from exc


def _prepare_work_directory(
    path: Path,
    private_root: Path,
    expected_commit: str,
    *,
    create: bool = True,
) -> None:
    if not path.is_absolute():
        raise InstallationPreparationError(
            "installation work directory must use an absolute path"
        )
    try:
        PRIVATE_INPUT.reject_symlink_components(
            path,
            "installation work directory",
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc
    install_root = private_root / "install"
    if install_root.exists() or install_root.is_symlink():
        _require_private_directory(
            install_root,
            "installation root directory",
            private_root,
        )
    elif create:
        install_root.mkdir(mode=0o700)
        _require_private_directory(
            install_root,
            "installation root directory",
            private_root,
        )
    expected = install_root / expected_commit
    try:
        exact_path = path.resolve(strict=False) == expected.resolve(strict=False)
    except OSError as exc:
        raise InstallationPreparationError(
            "installation work directory is invalid"
        ) from exc
    if not exact_path:
        raise InstallationPreparationError(
            "installation work directory must be the canonical commit directory"
        )
    if path.exists():
        _require_private_directory(
            path,
            "installation work directory",
            private_root,
        )
    elif create:
        path.mkdir(mode=0o700)
        _require_private_directory(
            path,
            "installation work directory",
            private_root,
        )


def _prepare_secret_store(
    path: Path,
    work_directory: Path,
    private_root: Path,
    *,
    create: bool = True,
) -> None:
    if not path.is_absolute():
        raise InstallationPreparationError(
            "installation Secret store must use an absolute path"
        )
    try:
        PRIVATE_INPUT.reject_symlink_components(
            path,
            "installation Secret store",
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc
    if path.exists():
        _within_private_root(path, private_root, "installation Secret store")
    else:
        try:
            path.resolve(strict=False).relative_to(private_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise InstallationPreparationError(
                "installation Secret store must be within the private root"
            ) from exc
    resolved = path.resolve()
    resolved_work = work_directory.resolve()
    if (
        resolved == resolved_work
        or resolved.is_relative_to(resolved_work)
        or resolved_work.is_relative_to(resolved)
    ):
        raise InstallationPreparationError(
            "installation Secret store must be separate from commit evidence"
        )
    relative = resolved.relative_to(private_root.resolve(strict=True))
    current = private_root
    for component in relative.parts:
        current /= component
        if current.exists() or current.is_symlink():
            _require_private_directory(
                current,
                "installation Secret store directory",
                private_root,
            )
            continue
        if not create:
            break
        try:
            current.mkdir(mode=0o700)
        except OSError as exc:
            raise InstallationPreparationError(
                "installation Secret store directory cannot be created"
            ) from exc
        _require_private_directory(
            current,
            "installation Secret store directory",
            private_root,
        )


def _snapshot_private_file(
    *,
    source: Path,
    destination: Path,
    description: str,
    private_root: Path,
) -> Path:
    try:
        return PRIVATE_INPUT.snapshot_private_file(
            source=source,
            destination=destination,
            description=description,
            private_root=private_root,
            allow_existing_exact=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc


def _snapshot_kubeconfig(
    *,
    source: Path,
    raw_destination: Path,
    flattened_destination: Path,
    context: str,
    private_root: Path,
    runner: CommandRunner,
) -> Path:
    try:
        return PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=source,
            raw_destination=raw_destination,
            flattened_destination=flattened_destination,
            context=context,
            private_root=private_root,
            runner=runner,
            allow_existing_exact=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc


def _validate_backend_execution_profile(
    *,
    source: Path,
    snapshot_directory: Path,
    private_root: Path,
    phase: str,
) -> Path:
    snapshot = _snapshot_private_file(
        source=source,
        destination=snapshot_directory / "backend-execution-profile.json",
        description="backend execution profile",
        private_root=private_root,
    )
    expected_fixed = private_root / "backend-attestor/execution-profile.json"
    if INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE != expected_fixed:
        raise InstallationPreparationError(
            "backend execution profile destination is not canonical"
        )
    try:
        source_binding = BACKEND_ATTESTOR.inspect_execution_profile(
            snapshot,
            private_root=private_root,
        )
        source_raw = PRIVATE_INPUT.read_private_bytes(
            snapshot,
            "backend execution profile snapshot",
            private_root=private_root,
        )
        fixed_exists = expected_fixed.exists() or expected_fixed.is_symlink()
        if fixed_exists:
            fixed_binding = BACKEND_ATTESTOR.inspect_execution_profile(
                expected_fixed,
                private_root=private_root,
            )
            fixed_raw = PRIVATE_INPUT.read_private_bytes(
                expected_fixed,
                "installed backend execution profile",
                private_root=private_root,
            )
            if fixed_binding != source_binding or fixed_raw != source_raw:
                raise InstallationPreparationError(
                    "installed backend execution profile changed"
                )
        elif phase == "apply":
            PRIVATE_INPUT.write_private_snapshot(
                destination=expected_fixed,
                content=source_raw,
                description="installed backend execution profile",
                private_root=private_root,
                allow_existing_exact=True,
            )
            installed_binding = BACKEND_ATTESTOR.inspect_execution_profile(
                expected_fixed,
                private_root=private_root,
            )
            if installed_binding != source_binding:
                raise InstallationPreparationError(
                    "installed backend execution profile changed"
                )
    except InstallationPreparationError:
        raise
    except (
        BACKEND_ATTESTOR.BackendAttestorError,
        PRIVATE_INPUT.PrivateInputError,
        ValueError,
    ) as exc:
        raise InstallationPreparationError(
            "backend execution profile is invalid"
        ) from exc
    return snapshot


def _validate_identity_profile(
    profile: dict[str, Any],
    schema_path: Path,
) -> None:
    if Draft7Validator is None:
        raise InstallationPreparationError(
            "jsonschema is required to validate Identity profile"
        )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationPreparationError(
            "Identity installation profile schema is unavailable"
        ) from exc
    errors = sorted(
        Draft7Validator(schema).iter_errors(profile),
        key=lambda error: list(error.path),
    )
    if errors:
        raise InstallationPreparationError(
            "Identity installation profile violates its schema"
        )


def _validate_parameters(request: InstallationPreparationRequest) -> None:
    if FULL_SHA_PATTERN.fullmatch(request.expected_commit) is None:
        raise InstallationPreparationError(
            "expected commit must be a full lowercase Git SHA"
        )
    if not request.context or request.context != request.context.strip():
        raise InstallationPreparationError("an exact Kubernetes context is required")
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]*(?::[0-9]{1,5})?",
        request.registry,
    ):
        raise InstallationPreparationError("registry is invalid")
    if not re.fullmatch(
        r"[a-z0-9]+(?:[._-][a-z0-9]+)*",
        request.project,
    ):
        raise InstallationPreparationError("registry project is invalid")
    try:
        platform = urlsplit(request.platform_url)
        platform_port = platform.port
    except (AttributeError, ValueError) as exc:
        raise InstallationPreparationError("platform URL is invalid") from exc
    if (
        PLATFORM_URL_PATTERN.fullmatch(request.platform_url) is None
        or platform.scheme != "https"
        or not platform.hostname
        or platform.username is not None
        or platform.password is not None
        or platform.path
        or platform.query
        or platform.fragment
        or platform.netloc.endswith(":")
        or (platform_port is not None and not 1 <= platform_port <= 65535)
    ):
        raise InstallationPreparationError("platform URL is invalid")
    turn_match = TURN_URL_PATTERN.fullmatch(request.turn_url)
    if turn_match is None:
        raise InstallationPreparationError(
            "TURN URL must be a valid turn: or turns: URI"
        )
    turn_port = turn_match.group(1)
    if turn_port is not None and not 1 <= int(turn_port) <= 65535:
        raise InstallationPreparationError("TURN URL port is invalid")


def _identity_profile(
    selection: IdentitySelection,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    external_oidc = None
    if selection.mode == "bundledKeycloak":
        if selection.tls_cert is None or selection.tls_key is None:
            raise InstallationPreparationError(
                "bundledKeycloak mode requires Identity TLS inputs"
            )
        if any(
            value is not None
            for value in (
                selection.external_client_secret,
                selection.external_issuer_url,
                selection.external_client_id,
            )
        ):
            raise InstallationPreparationError(
                "bundledKeycloak mode must not provide external OIDC inputs"
            )
        profile = {
            "mode": "bundledKeycloak",
            "bundledKeycloak": {
                "chartPath": "helm/aileron-identity",
                "releaseName": "aileron-identity",
                "namespace": "aileron-identity-system",
                "issuerUrl": INSTALLATION_STATE.BUNDLED_ISSUER_URL,
                "clientId": INSTALLATION_STATE.BUNDLED_CLIENT_ID,
                "clientSecretRef": {
                    "name": "aileron-oidc-client",
                    "key": "client-secret",
                },
                "caSecretRef": {"name": "aileron-oidc-ca", "key": "ca.crt"},
            },
        }
    elif selection.mode == "externalOidc":
        if selection.tls_cert is not None or selection.tls_key is not None:
            raise InstallationPreparationError(
                "externalOidc mode must not provide Identity TLS inputs"
            )
        if (
            selection.external_client_secret is None
            or not selection.external_issuer_url
            or not selection.external_client_id
        ):
            raise InstallationPreparationError(
                "external OIDC client Secret, issuer URL and client ID are required"
            )
        try:
            INSTALLATION_STATE.validate_identity_selection(
                identity_mode="externalOidc",
                issuer_url=selection.external_issuer_url,
                client_id=selection.external_client_id,
            )
        except INSTALLATION_STATE.InstallationStateContractError as exc:
            raise InstallationPreparationError(str(exc)) from exc
        external_oidc = {
            "issuerUrl": selection.external_issuer_url,
            "clientId": selection.external_client_id,
        }
        profile = {
            "mode": "externalOidc",
            "externalOidc": {
                **external_oidc,
                "clientSecretRef": {
                    "name": "aileron-oidc-client",
                    "key": "client-secret",
                },
                "caSecretRef": {"name": "aileron-oidc-ca", "key": "ca.crt"},
            },
        }
    else:
        raise InstallationPreparationError(
            "identity mode must be bundledKeycloak or externalOidc"
        )
    return profile, external_oidc


def _validate_git_source(
    expected_commit: str,
    runner: CommandRunner,
) -> None:
    status = runner(["git", "status", "--porcelain"], environment={})
    if status:
        raise InstallationPreparationError("installation requires a clean Git checkout")
    actual_commit = runner(
        ["git", "rev-parse", "--verify", "HEAD"],
        environment={},
    ).strip()
    if actual_commit != expected_commit:
        raise InstallationPreparationError(
            "Git HEAD does not match the expected commit"
        )


def _load_live_acceptance_trust(
    *,
    context: str,
    kubeconfig: Path,
    environment: dict[str, str],
    runner: CommandRunner,
) -> PreparedAcceptanceTrust:
    def acceptance_runner(command: list[str]) -> bytes:
        try:
            return runner(command, environment=environment).encode("utf-8")
        except InstallationRunnerError as exc:
            raise ACCEPTANCE_CLUSTER.AcceptanceClusterError(
                "live acceptance trust query failed"
            ) from exc

    try:
        trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
            context=context,
            kubeconfig=kubeconfig,
            runner=acceptance_runner,
        )
    except ACCEPTANCE_CLUSTER.AcceptanceClusterError as exc:
        raise InstallationPreparationError("live acceptance trust is invalid") from exc
    return PreparedAcceptanceTrust(
        key=trust.key,
        cluster_uid=trust.cluster_uid,
        installation_identity_sha256=trust.installation_identity_sha256,
        secret_uid=trust.secret_uid,
    )


def _prepare_locked_inputs(
    *,
    request: InstallationPreparationRequest,
    work_directory: Path,
    state_paths_prepared: bool,
    runner: CommandRunner,
    validate_installation_identity: InstallationIdentityValidator,
) -> PreparedInstallation:
    _validate_runtime_dependencies()
    _validate_parameters(request)
    private_root = INSTALLATION_STATE.PRIVATE_ROOT
    secret_store = INSTALLATION_STATE.SECRET_STORE
    if not state_paths_prepared:
        _prepare_work_directory(
            work_directory,
            private_root,
            request.expected_commit,
        )
        _prepare_secret_store(
            secret_store,
            work_directory,
            private_root,
        )

    profile, external_oidc = _identity_profile(request.identity)
    _validate_identity_profile(profile, request.identity_profile_schema)
    _validate_git_source(request.expected_commit, runner)

    snapshot_directory = work_directory / "snapshots"
    kubeconfig = _snapshot_kubeconfig(
        source=request.sources.kubeconfig,
        raw_destination=snapshot_directory / "kubeconfig.raw",
        flattened_destination=snapshot_directory / "kubeconfig",
        context=request.context,
        private_root=private_root,
        runner=runner,
    )
    inventory = _snapshot_private_file(
        source=request.sources.inventory,
        destination=snapshot_directory / "published-image-inventory.tsv",
        description="published image inventory",
        private_root=private_root,
    )
    _validate_backend_execution_profile(
        source=request.sources.execution_profile,
        snapshot_directory=snapshot_directory,
        private_root=private_root,
        phase=request.phase,
    )
    harbor_dockerconfig = _snapshot_private_file(
        source=request.sources.harbor_dockerconfig,
        destination=snapshot_directory / "harbor-dockerconfig.json",
        description="Harbor dockerconfig",
        private_root=private_root,
    )
    apps_tls_cert = _snapshot_private_file(
        source=request.sources.apps_tls_cert,
        destination=snapshot_directory / "apps-tls.crt",
        description="Apps TLS certificate",
        private_root=private_root,
    )
    apps_tls_key = _snapshot_private_file(
        source=request.sources.apps_tls_key,
        destination=snapshot_directory / "apps-tls.key",
        description="Apps TLS private key",
        private_root=private_root,
    )
    apps_tls_ca = _snapshot_private_file(
        source=request.sources.apps_tls_ca,
        destination=snapshot_directory / "apps-tls-ca.crt",
        description="Apps TLS CA",
        private_root=private_root,
    )
    oidc_ca = _snapshot_private_file(
        source=request.sources.oidc_ca,
        destination=snapshot_directory / "oidc-ca.crt",
        description="OIDC CA",
        private_root=private_root,
    )
    identity_tls_cert: Path | None = None
    identity_tls_key: Path | None = None
    external_oidc_client_secret: Path | None = None
    if request.identity.mode == "bundledKeycloak":
        assert request.identity.tls_cert is not None
        assert request.identity.tls_key is not None
        identity_tls_cert = _snapshot_private_file(
            source=request.identity.tls_cert,
            destination=snapshot_directory / "identity-tls.crt",
            description="Identity TLS certificate",
            private_root=private_root,
        )
        identity_tls_key = _snapshot_private_file(
            source=request.identity.tls_key,
            destination=snapshot_directory / "identity-tls.key",
            description="Identity TLS private key",
            private_root=private_root,
        )
    else:
        assert request.identity.external_client_secret is not None
        external_oidc_client_secret = _snapshot_private_file(
            source=request.identity.external_client_secret,
            destination=snapshot_directory / "external-oidc-client-secret",
            description="external OIDC client Secret",
            private_root=private_root,
        )

    core_data_service_values: Path | None = None
    if request.sources.core_data_service_values is not None:
        core_data_service_values = _snapshot_private_file(
            source=request.sources.core_data_service_values,
            destination=snapshot_directory / "core-data-service-values.yaml",
            description="Core data-service values",
            private_root=private_root,
        )
    identity_data_service_values: Path | None = None
    if request.sources.identity_data_service_values is not None:
        if request.identity.mode != "bundledKeycloak":
            raise InstallationPreparationError(
                "Identity data-service values require bundledKeycloak mode"
            )
        identity_data_service_values = _snapshot_private_file(
            source=request.sources.identity_data_service_values,
            destination=snapshot_directory / "identity-data-service-values.yaml",
            description="Identity data-service values",
            private_root=private_root,
        )
    core_data_service_inputs: list[tuple[str, Path]] = []
    seen_data_service_inputs: set[str] = set()
    for artifact_id, source in request.sources.core_data_service_inputs:
        if (
            re.fullmatch(r"[a-z0-9][a-z0-9-]*", artifact_id) is None
            or artifact_id in seen_data_service_inputs
        ):
            raise InstallationPreparationError(
                "Core data-service input identity is invalid"
            )
        seen_data_service_inputs.add(artifact_id)
        core_data_service_inputs.append(
            (
                artifact_id,
                _snapshot_private_file(
                    source=source,
                    destination=(
                        snapshot_directory / "core-data-service-inputs" / artifact_id
                    ),
                    description=f"Core data-service input {artifact_id}",
                    private_root=private_root,
                ),
            )
        )
    identity_database_sources = (
        request.sources.identity_database_username,
        request.sources.identity_database_password,
        request.sources.identity_database_ca,
    )
    if any(source is not None for source in identity_database_sources) and not all(
        source is not None for source in identity_database_sources
    ):
        raise InstallationPreparationError(
            "External Identity database inputs must be provided as a complete set"
        )
    identity_database_username: Path | None = None
    identity_database_password: Path | None = None
    identity_database_ca: Path | None = None
    if all(source is not None for source in identity_database_sources):
        identity_database_username = _snapshot_private_file(
            source=request.sources.identity_database_username,
            destination=snapshot_directory / "identity-database/username",
            description="Identity database username",
            private_root=private_root,
        )
        identity_database_password = _snapshot_private_file(
            source=request.sources.identity_database_password,
            destination=snapshot_directory / "identity-database/password",
            description="Identity database password",
            private_root=private_root,
        )
        identity_database_ca = _snapshot_private_file(
            source=request.sources.identity_database_ca,
            destination=snapshot_directory / "identity-database/ca.crt",
            description="Identity database CA",
            private_root=private_root,
        )

    environment = {"KUBECONFIG": str(kubeconfig)}
    if (
        ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT != private_root
        or ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE
        != private_root / "install-secrets/homelab"
    ):
        raise InstallationPreparationError(
            "live acceptance trust private-state identity is inconsistent"
        )
    acceptance_trust = _load_live_acceptance_trust(
        context=request.context,
        kubeconfig=kubeconfig,
        environment=environment,
        runner=runner,
    )
    validate_installation_identity(
        secret_store=secret_store,
        private_root=private_root,
        context=request.context,
        cluster_uid=acceptance_trust.cluster_uid,
        identity_profile=profile,
    )

    image_contract = RELEASE_VALUES.RELEASE_INVENTORY.load_contract(
        SCRIPT_DIRECTORY / "image-release-contract.json"
    )
    try:
        inventory_text = PRIVATE_INPUT.read_private_text(
            inventory,
            "published image inventory snapshot",
            private_root=private_root,
            maximum_size=1024 * 1024,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise InstallationPreparationError(str(exc)) from exc
    images = RELEASE_VALUES.RELEASE_INVENTORY.validate_published_inventory(
        inventory_text.splitlines(keepends=True),
        contract=image_contract,
        expected_commit=request.expected_commit,
        expected_registry=request.registry,
        expected_project=request.project,
        omitted_components=RELEASE_VALUES.omitted_published_components(
            core_data_service_values
        ),
    )

    rendered = RELEASE_VALUES.render_release_values(
        inventory_path=inventory,
        expected_commit=request.expected_commit,
        expected_registry=request.registry,
        expected_project=request.project,
        identity_mode=request.identity.mode,
        output_directory=work_directory / "release-values",
        external_oidc=external_oidc,
        core_data_service_values_path=core_data_service_values,
        identity_data_service_values_path=identity_data_service_values,
    )
    try:
        core_release_values = json.loads(rendered.core_path.read_text(encoding="utf-8"))
        core_postgres_enabled = core_release_values["postgres"]["enabled"]
        core_redis_enabled = core_release_values["redis"]["enabled"]
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        raise InstallationPreparationError(
            "rendered Core data-service switches are invalid"
        ) from exc
    if not isinstance(core_postgres_enabled, bool) or not isinstance(
        core_redis_enabled, bool
    ):
        raise InstallationPreparationError(
            "rendered Core data-service switches are invalid"
        )
    expected_core_inputs = set()
    if not core_postgres_enabled:
        expected_core_inputs.update(CORE_POSTGRES_EXTERNAL_INPUTS)
    if not core_redis_enabled:
        expected_core_inputs.update(CORE_REDIS_EXTERNAL_INPUTS)
    if seen_data_service_inputs != expected_core_inputs:
        raise InstallationPreparationError(
            "Core data-service inputs do not match the rendered values"
        )

    identity_database_inputs_present = identity_database_username is not None
    if rendered.identity_path is not None:
        try:
            identity_release_values = json.loads(
                rendered.identity_path.read_text(encoding="utf-8")
            )
            identity_postgres_enabled = identity_release_values["postgres"]["enabled"]
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
        ) as exc:
            raise InstallationPreparationError(
                "rendered Identity data-service switch is invalid"
            ) from exc
        if not isinstance(identity_postgres_enabled, bool):
            raise InstallationPreparationError(
                "rendered Identity data-service switch is invalid"
            )
        if identity_database_inputs_present is identity_postgres_enabled:
            raise InstallationPreparationError(
                "Identity database inputs do not match the rendered values"
            )
    elif identity_database_inputs_present:
        raise InstallationPreparationError(
            "externalOidc mode forbids Identity database inputs"
        )
    expected_images = {image["component"]: image["immutableImage"] for image in images}
    if rendered.published_images != expected_images:
        raise InstallationPreparationError(
            "published image inventory changed during release values rendering"
        )
    core_values = _snapshot_private_file(
        source=rendered.core_path,
        destination=snapshot_directory / "core-values.json",
        description="core release values",
        private_root=private_root,
    )
    identity_values: Path | None = None
    if rendered.identity_path is not None:
        identity_values = _snapshot_private_file(
            source=rendered.identity_path,
            destination=snapshot_directory / "identity-values.json",
            description="Identity release values",
            private_root=private_root,
        )

    signed_inventory = (
        private_root
        / "install"
        / request.expected_commit
        / "signed-image-inventory.json"
    )
    try:
        ACCEPTANCE_RELEASE.load_matching_signed_image_inventory(
            path=signed_inventory,
            private_root=private_root,
            expected_images=images,
            key=acceptance_trust.key,
            context=request.context,
            commit=request.expected_commit,
            cluster_uid=acceptance_trust.cluster_uid,
            installation_identity_sha256=(
                acceptance_trust.installation_identity_sha256
            ),
        )
    except ACCEPTANCE_RELEASE.AcceptanceReleaseError as exc:
        raise InstallationPreparationError(
            "canonical signed image inventory is invalid"
        ) from exc

    return PreparedInstallation(
        expected_commit=request.expected_commit,
        context=request.context,
        registry=request.registry,
        project=request.project,
        platform_url=request.platform_url,
        turn_url=request.turn_url,
        phase=request.phase,
        private_root=private_root,
        secret_store=secret_store,
        work_directory=work_directory,
        identity_mode=request.identity.mode,
        external_oidc_issuer_url=request.identity.external_issuer_url,
        snapshots=PreparedSnapshots(
            directory=snapshot_directory,
            kubeconfig=kubeconfig,
            harbor_dockerconfig=harbor_dockerconfig,
            apps_tls_cert=apps_tls_cert,
            apps_tls_key=apps_tls_key,
            apps_tls_ca=apps_tls_ca,
            oidc_ca=oidc_ca,
            identity_tls_cert=identity_tls_cert,
            identity_tls_key=identity_tls_key,
            external_oidc_client_secret=external_oidc_client_secret,
            core_values=core_values,
            identity_values=identity_values,
            core_data_service_inputs=tuple(core_data_service_inputs),
            identity_database_username=identity_database_username,
            identity_database_password=identity_database_password,
            identity_database_ca=identity_database_ca,
        ),
        acceptance_trust=acceptance_trust,
        workspace_manager_image=rendered.published_images["workspace-manager"],
    )


@contextmanager
def _phase_state(
    request: InstallationPreparationRequest,
) -> Iterator[tuple[Path, bool]]:
    private_root = INSTALLATION_STATE.PRIVATE_ROOT
    persistent_secret_store = INSTALLATION_STATE.SECRET_STORE
    if request.phase == "apply":
        yield request.work_directory, False
        return

    _prepare_work_directory(
        request.work_directory,
        private_root,
        request.expected_commit,
        create=False,
    )
    _prepare_secret_store(
        persistent_secret_store,
        request.work_directory,
        private_root,
        create=False,
    )
    with TemporaryDirectory(
        prefix=".installation-phase-",
        dir=private_root,
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        temporary_root.chmod(0o700)
        phase_work_directory = temporary_root / "work"
        phase_secret_store = temporary_root / "secrets"
        phase_work_directory.mkdir(mode=0o700)
        phase_secret_store.mkdir(mode=0o700)
        source = persistent_secret_store / "installation-identity.json"
        if source.exists() or source.is_symlink():
            _snapshot_private_file(
                source=source,
                destination=phase_secret_store / "installation-identity.json",
                description="installation identity manifest",
                private_root=private_root,
            )
        INSTALLATION_STATE.SECRET_STORE = phase_secret_store
        try:
            yield phase_work_directory, True
        finally:
            INSTALLATION_STATE.SECRET_STORE = persistent_secret_store


@contextmanager
def prepare_installation(
    request: InstallationPreparationRequest,
    runner: CommandRunner,
    validate_installation_identity: InstallationIdentityValidator,
) -> Iterator[PreparedInstallation]:
    """Prepare and hold immutable installation inputs for downstream execution."""

    _validate_private_root(INSTALLATION_STATE.PRIVATE_ROOT)
    with _phase_state(request) as (work_directory, state_paths_prepared):
        prepared = _prepare_locked_inputs(
            request=request,
            work_directory=work_directory,
            state_paths_prepared=state_paths_prepared,
            runner=runner,
            validate_installation_identity=validate_installation_identity,
        )
        yield prepared
