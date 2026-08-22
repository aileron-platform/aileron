#!/usr/bin/env python3
"""Bootstrap the fixed HomeLab acceptance trust root before destructive reset."""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from uuid import UUID, uuid4


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class BootstrapError(RuntimeError):
    """Raised when pre-reset trust bootstrap cannot proceed safely."""


class CommandNotFoundError(BootstrapError):
    """Raised when the queried acceptance Secret does not exist."""


Runner = Callable[..., bytes]
KeyFactory = Callable[[], bytes]
InstallationIdFactory = Callable[[], str]


def _load_installation_state() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_installation_state", SCRIPT_DIRECTORY / "installation_state.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-state contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_private_input() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_bootstrap_private_input", SCRIPT_DIRECTORY / "private_input.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-input contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_namespace_contract() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_bootstrap_namespace_contract",
        SCRIPT_DIRECTORY / "namespace_contract.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("acceptance Namespace contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_installation_state()
PRIVATE_INPUT = _load_private_input()
NAMESPACE_CONTRACT = _load_namespace_contract()
SECRET_NAMESPACE = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAMESPACE
SECRET_NAME = INSTALLATION_STATE.ACCEPTANCE_SECRET_NAME
ANCHOR_FILE = INSTALLATION_STATE.ACCEPTANCE_ANCHOR_FILE
INSTALLER_OWNER = INSTALLATION_STATE.INSTALLER_OWNER
BOOTSTRAP_DIRECTORY_NAME = "acceptance-bootstrap"
RAW_KUBECONFIG_NAME = "kubeconfig.raw"
FLATTENED_KUBECONFIG_NAME = "kubeconfig.flattened.json"


def run_command(
    command: list[str],
    stdin: bytes | None = None,
    *,
    environment: Optional[dict[str, str]] = None,
) -> bytes:
    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    result = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        cwd=REPOSITORY_ROOT,
        check=False,
        env=process_environment,
    )
    if result.returncode == 0:
        return result.stdout
    normalized_error = result.stderr.lower()
    if (
        "get" in command
        and ("secret" in command or "namespace" in command)
        and (b"(notfound)" in normalized_error or b" not found" in normalized_error)
    ):
        raise CommandNotFoundError("acceptance trust resource does not exist")
    raise BootstrapError(f"bootstrap command failed: {Path(command[0]).name}")


def _reject_symlink_components(path: Path, description: str) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise BootstrapError(f"{description} is unreadable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise BootstrapError(f"{description} must not contain a symbolic link")


def _prepare_private_root(path: Path) -> Path:
    if not path.is_absolute():
        raise BootstrapError("installation private root must use an absolute path")
    _reject_symlink_components(path, "installation private root")
    try:
        path.resolve(strict=False).relative_to(REPOSITORY_ROOT.resolve(strict=True))
    except ValueError:
        pass
    except OSError as exc:
        raise BootstrapError("installation private root is unreadable") from exc
    else:
        raise BootstrapError("installation private root must be outside the Git checkout")

    created = False
    parent_descriptor: int | None = None
    try:
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent_descriptor)
            created = True
            os.fsync(parent_descriptor)
        except FileExistsError:
            pass
        return PRIVATE_INPUT.private_root_path(path)
    except PRIVATE_INPUT.PrivateInputError as exc:
        if created:
            try:
                os.rmdir(path.name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except OSError:
                pass
        raise BootstrapError(str(exc)) from exc
    except OSError as exc:
        raise BootstrapError("installation private root could not be prepared") from exc
    finally:
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def _ensure_private_directory(
    path: Path,
    description: str,
    *,
    private_root: Path,
) -> Path:
    try:
        return PRIVATE_INPUT.ensure_private_directory(
            path,
            description,
            private_root=private_root,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BootstrapError(str(exc)) from exc


@contextmanager
def _installation_lock(private_root: Path) -> Iterator[None]:
    descriptor: int | None = None
    locked = False
    try:
        descriptor = os.open(
            private_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(private_root)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()
            or not stat.S_ISDIR(path_metadata.st_mode)
            or stat.S_IMODE(path_metadata.st_mode) != 0o700
            or path_metadata.st_uid != os.geteuid()
            or metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise BootstrapError("installation private root lock is invalid")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise BootstrapError(
                    "another installation operation is already running"
                ) from exc
            raise BootstrapError("installation private root lock is unavailable") from exc
        locked = True
        locked_path_metadata = os.lstat(private_root)
        if (
            not stat.S_ISDIR(locked_path_metadata.st_mode)
            or stat.S_IMODE(locked_path_metadata.st_mode) != 0o700
            or locked_path_metadata.st_uid != os.geteuid()
            or metadata.st_dev != locked_path_metadata.st_dev
            or metadata.st_ino != locked_path_metadata.st_ino
        ):
            raise BootstrapError("installation private root changed while locking")
        yield
    except BootstrapError:
        raise
    except OSError as exc:
        raise BootstrapError("installation private root lock is unavailable") from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _private_file(path: Path, description: str, private_root: Path) -> bytes:
    try:
        return PRIVATE_INPUT.read_private_bytes(
            path,
            description,
            private_root=private_root,
            require_nonempty=True,
            maximum_size=1024 * 1024,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BootstrapError(str(exc)) from exc


def _write_new_private_file(
    path: Path,
    value: bytes,
    description: str,
    *,
    private_root: Path,
    allow_existing_exact: bool = False,
) -> None:
    try:
        PRIVATE_INPUT.write_private_snapshot(
            destination=path,
            content=value,
            description=description,
            private_root=private_root,
            allow_existing_exact=allow_existing_exact,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BootstrapError(str(exc)) from exc


def _kubectl(kubeconfig: Path, context: str, *arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        *arguments,
    ]


def _bootstrap_transaction_directory(private_root: Path, commit: str) -> Path:
    root = private_root / BOOTSTRAP_DIRECTORY_NAME
    transaction = root / commit
    _ensure_private_directory(
        root,
        "acceptance bootstrap root",
        private_root=private_root,
    )
    try:
        PRIVATE_INPUT.validate_private_directory(
            root,
            "acceptance bootstrap root",
            private_root=private_root,
        )
        if transaction.exists() or transaction.is_symlink():
            PRIVATE_INPUT.validate_private_directory(
                transaction,
                "acceptance bootstrap transaction",
                private_root=private_root,
            )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BootstrapError(str(exc)) from exc
    return transaction


def _snapshot_kubeconfig(
    *,
    source: Path,
    private_root: Path,
    commit: str,
    context: str,
    runner: Runner,
) -> Path:
    transaction = _bootstrap_transaction_directory(private_root, commit)

    def snapshot_runner(
        command: list[str], *, environment: dict[str, str]
    ) -> str:
        try:
            return runner(command, None, environment=environment).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BootstrapError("flattened kubeconfig output is invalid") from exc

    try:
        return PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
            source=source,
            raw_destination=transaction / RAW_KUBECONFIG_NAME,
            flattened_destination=transaction / FLATTENED_KUBECONFIG_NAME,
            context=context,
            runner=snapshot_runner,
            private_root=private_root,
            allow_existing_exact=True,
        )
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BootstrapError(str(exc)) from exc


def _read_anchor(path: Path, private_root: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = _private_file(path, "acceptance trust anchor", private_root)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_nonstandard_constant(_value: str) -> None:
        raise ValueError("non-standard JSON constant")

    try:
        document = json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_nonstandard_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BootstrapError("acceptance trust anchor is invalid") from exc
    canonical = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    if not isinstance(document, dict) or raw != canonical:
        raise BootstrapError("acceptance trust anchor is invalid")
    return document


def _replace_anchor(
    path: Path,
    document: dict[str, Any],
    *,
    private_root: Path,
) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    content = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    _write_new_private_file(
        temporary,
        content,
        "acceptance trust anchor replacement",
        private_root=private_root,
        allow_existing_exact=True,
    )
    try:
        os.replace(temporary, path)
        directory_descriptor = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        if _private_file(path, "acceptance trust anchor", private_root) != content:
            raise BootstrapError("acceptance trust anchor replacement is invalid")
    except BootstrapError:
        raise
    except OSError as exc:
        raise BootstrapError("acceptance trust anchor could not be bound") from exc


def _acceptance_namespace_manifest() -> bytes:
    document = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": SECRET_NAMESPACE,
            "labels": NAMESPACE_CONTRACT.profile_labels(SECRET_NAMESPACE),
        },
    }
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


def _validate_acceptance_namespace(
    document: Any,
) -> NAMESPACE_CONTRACT.NamespaceRecord:
    try:
        return NAMESPACE_CONTRACT.validate_namespace_document(
            document,
            namespace=SECRET_NAMESPACE,
            require_canonical_uid=True,
        )
    except NAMESPACE_CONTRACT.NamespaceContractError as exc:
        raise BootstrapError("acceptance namespace ownership is invalid") from exc


def _read_acceptance_namespace(
    *,
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> NAMESPACE_CONTRACT.NamespaceRecord:
    raw = runner(
        _kubectl(
            kubeconfig,
            context,
            "get",
            "namespace",
            SECRET_NAMESPACE,
            "--output=json",
        ),
        None,
    )
    try:
        document = NAMESPACE_CONTRACT.load_json_document(
            raw, "acceptance Namespace"
        )
    except NAMESPACE_CONTRACT.NamespaceContractError as exc:
        raise BootstrapError("acceptance namespace is invalid") from exc
    return _validate_acceptance_namespace(document)


def _require_same_acceptance_namespace(
    expected: NAMESPACE_CONTRACT.NamespaceRecord,
    actual: NAMESPACE_CONTRACT.NamespaceRecord,
    *,
    require_exact_resource_version: bool,
) -> None:
    if actual.uid != expected.uid:
        raise BootstrapError("acceptance namespace identity changed")
    if require_exact_resource_version and actual != expected:
        raise BootstrapError("acceptance namespace changed during trust bootstrap")


def _read_acceptance_secret_uid(
    *,
    kubeconfig: Path,
    context: str,
    runner: Runner,
    expected_secret: dict[str, Any],
) -> str:
    raw = runner(
        _kubectl(
            kubeconfig,
            context,
            "get",
            "secret",
            SECRET_NAME,
            "--namespace",
            SECRET_NAMESPACE,
            "--output=json",
        ),
        None,
    )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapError("acceptance signing Secret is invalid") from exc
    if not isinstance(document, dict):
        raise BootstrapError("acceptance signing Secret is invalid")
    try:
        return INSTALLATION_STATE.acceptance_secret_uid(document, expected_secret)
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise BootstrapError(str(exc)) from exc


def _require_live_anchor_resources(
    *,
    kubeconfig: Path,
    context: str,
    runner: Runner,
    expected_namespace: NAMESPACE_CONTRACT.NamespaceRecord,
    expected_secret: dict[str, Any],
    expected_secret_uid: str,
) -> None:
    live_namespace = _read_acceptance_namespace(
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    _require_same_acceptance_namespace(
        expected_namespace,
        live_namespace,
        require_exact_resource_version=True,
    )
    try:
        live_secret_uid = _read_acceptance_secret_uid(
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
            expected_secret=expected_secret,
        )
    except CommandNotFoundError as exc:
        raise BootstrapError(
            "acceptance signing Secret disappeared before anchor binding"
        ) from exc
    if live_secret_uid != expected_secret_uid:
        raise BootstrapError(
            "acceptance signing Secret identity changed before anchor binding"
        )


def _bootstrap_acceptance_trust_locked(
    *,
    commit: str,
    kubeconfig: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    apply: bool,
    private_root: Path,
    secret_store: Path,
    runner: Runner,
    key_factory: KeyFactory,
    installation_id_factory: InstallationIdFactory,
) -> None:
    """Run one trust bootstrap while the private-root descriptor is locked."""

    expected_secret_store = private_root / "install-secrets" / "homelab"
    if secret_store != expected_secret_store:
        raise BootstrapError("installation Secret store path is not canonical")
    _ensure_private_directory(
        secret_store,
        "installation Secret store",
        private_root=private_root,
    )
    try:
        secret_store.resolve(strict=True).relative_to(private_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise BootstrapError(
            "installation Secret store must be inside the private root"
        ) from exc
    kubeconfig = _snapshot_kubeconfig(
        source=kubeconfig,
        private_root=private_root,
        commit=commit,
        context=context,
        runner=runner,
    )

    current_context = runner(
        _kubectl(kubeconfig, context, "config", "current-context"), None
    ).decode().strip()
    if current_context != context:
        raise BootstrapError("kubeconfig current context does not match")
    cluster_uid = runner(
        _kubectl(
            kubeconfig,
            context,
            "get",
            "namespace",
            "kube-system",
            "--output=jsonpath={.metadata.uid}",
        ),
        None,
    ).decode().strip()
    try:
        parsed_uid = UUID(cluster_uid)
    except ValueError as exc:
        raise BootstrapError("Kubernetes cluster identity is invalid") from exc
    if str(parsed_uid) != cluster_uid:
        raise BootstrapError("Kubernetes cluster identity is invalid")

    identity_path = secret_store / "installation-identity.json"
    if identity_path.exists():
        identity = _private_file(
            identity_path, "installation identity", private_root
        )
        try:
            existing_identity = json.loads(identity)
            validated_identity = (
                INSTALLATION_STATE.validate_installation_identity_document(
                    existing_identity,
                    cluster_uid=cluster_uid,
                )
            )
            expected_identity = INSTALLATION_STATE.installation_identity_document(
                installation_id=validated_identity["installationId"],
                identity_mode=identity_mode,
                issuer_url=issuer_url,
                client_id=client_id,
                cluster_uid=cluster_uid,
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            INSTALLATION_STATE.InstallationStateContractError,
        ) as exc:
            raise BootstrapError("installation identity is invalid") from exc
        expected_identity_bytes = (
            json.dumps(expected_identity, indent=2, sort_keys=True) + "\n"
        ).encode()
        if identity != expected_identity_bytes:
            raise BootstrapError("installation identity does not match exact bytes")
    else:
        try:
            expected_identity = INSTALLATION_STATE.installation_identity_document(
                installation_id=installation_id_factory(),
                identity_mode=identity_mode,
                issuer_url=issuer_url,
                client_id=client_id,
                cluster_uid=cluster_uid,
            )
        except INSTALLATION_STATE.InstallationStateContractError as exc:
            raise BootstrapError(str(exc)) from exc
        expected_identity_bytes = (
            json.dumps(expected_identity, indent=2, sort_keys=True) + "\n"
        ).encode()
        _write_new_private_file(
            identity_path,
            expected_identity_bytes,
            "installation identity",
            private_root=private_root,
        )
        identity = expected_identity_bytes

    key_path = secret_store / "acceptance-hmac.key"
    if key_path.exists():
        key = _private_file(key_path, "acceptance signing key", private_root)
        if len(key) != 32:
            raise BootstrapError("acceptance signing key must contain 32 bytes")
    else:
        key = key_factory()
        if not isinstance(key, bytes) or len(key) != 32:
            raise BootstrapError("acceptance signing key factory must return 32 bytes")
        _write_new_private_file(
            key_path,
            key,
            "acceptance signing key",
            private_root=private_root,
        )

    try:
        manifest = INSTALLATION_STATE.acceptance_secret_bytes(
            key=key, identity=identity, cluster_uid=cluster_uid
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise BootstrapError(str(exc)) from exc
    expected_secret = json.loads(manifest)

    namespace_manifest = _acceptance_namespace_manifest()
    try:
        namespace_record = _read_acceptance_namespace(
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
        )
    except CommandNotFoundError:
        namespace_record = None

    if namespace_record is None:
        runner(
            _kubectl(
                kubeconfig,
                context,
                "create",
                "--dry-run=server",
                "--output=name",
                "--filename=-",
            ),
            namespace_manifest,
        )
        if not apply:
            return
        created_namespace_raw = runner(
            _kubectl(
                kubeconfig,
                context,
                "create",
                "--output=json",
                "--filename=-",
            ),
            namespace_manifest,
        )
        try:
            created_namespace = json.loads(created_namespace_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootstrapError("created acceptance namespace is invalid") from exc
        namespace_record = _validate_acceptance_namespace(created_namespace)

    verified_namespace = _read_acceptance_namespace(
        kubeconfig=kubeconfig,
        context=context,
        runner=runner,
    )
    _require_same_acceptance_namespace(
        namespace_record,
        verified_namespace,
        require_exact_resource_version=False,
    )
    namespace_record = verified_namespace

    existing_secret: dict[str, Any] | None
    try:
        existing_raw = runner(
            _kubectl(
                kubeconfig,
                context,
                "get",
                "secret",
                SECRET_NAME,
                "--namespace",
                SECRET_NAMESPACE,
                "--output=json",
            ),
            None,
        )
    except CommandNotFoundError:
        existing_secret = None
    else:
        try:
            parsed_secret = json.loads(existing_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootstrapError("existing acceptance signing Secret is invalid") from exc
        if not isinstance(parsed_secret, dict):
            raise BootstrapError("existing acceptance signing Secret is invalid")
        existing_secret = parsed_secret

    identity_digest = hashlib.sha256(identity).hexdigest()
    key_digest = hashlib.sha256(key).hexdigest()
    pending_anchor = INSTALLATION_STATE.acceptance_anchor_document(
        cluster_uid=cluster_uid,
        identity_digest=identity_digest,
        key_digest=key_digest,
        secret_uid=None,
    )
    anchor_path = secret_store / ANCHOR_FILE
    anchor = _read_anchor(anchor_path, private_root)

    if existing_secret is None:
        if anchor not in (None, pending_anchor):
            raise BootstrapError(
                "acceptance trust anchor requires the original immutable Secret"
            )
        runner(
            _kubectl(
                kubeconfig,
                context,
                "create",
                "--namespace",
                SECRET_NAMESPACE,
                "--dry-run=server",
                "--output=name",
                "--filename=-",
            ),
            manifest,
        )
        if not apply:
            return
        final_namespace = _read_acceptance_namespace(
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
        )
        _require_same_acceptance_namespace(
            namespace_record,
            final_namespace,
            require_exact_resource_version=True,
        )
        if anchor is None:
            _write_new_private_file(
                anchor_path,
                (json.dumps(pending_anchor, indent=2, sort_keys=True) + "\n").encode(),
                "acceptance trust anchor",
                private_root=private_root,
            )
        created_raw = runner(
            _kubectl(
                kubeconfig,
                context,
                "create",
                "--namespace",
                SECRET_NAMESPACE,
                "--output=json",
                "--filename=-",
            ),
            manifest,
        )
        try:
            created = json.loads(created_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootstrapError("created acceptance signing Secret is invalid") from exc
        try:
            created_uid = INSTALLATION_STATE.acceptance_secret_uid(
                created, expected_secret
            )
        except INSTALLATION_STATE.InstallationStateContractError as exc:
            raise BootstrapError(str(exc)) from exc
        _require_live_anchor_resources(
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
            expected_namespace=namespace_record,
            expected_secret=expected_secret,
            expected_secret_uid=created_uid,
        )
        _replace_anchor(
            anchor_path,
            {**pending_anchor, "secretUid": created_uid},
            private_root=private_root,
        )
        return

    try:
        existing_uid = INSTALLATION_STATE.acceptance_secret_uid(
            existing_secret, expected_secret
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise BootstrapError(str(exc)) from exc
    bound_anchor = {**pending_anchor, "secretUid": existing_uid}
    if anchor not in (pending_anchor, bound_anchor):
        raise BootstrapError(
            "existing acceptance signing Secret does not match its trust anchor"
        )
    if apply and anchor == pending_anchor:
        _require_live_anchor_resources(
            kubeconfig=kubeconfig,
            context=context,
            runner=runner,
            expected_namespace=namespace_record,
            expected_secret=expected_secret,
            expected_secret_uid=existing_uid,
        )
        _replace_anchor(
            anchor_path,
            bound_anchor,
            private_root=private_root,
        )


class LockedBootstrapPort:
    """Execute trust bootstrap inside one already-held installation lock."""

    def __init__(
        self,
        *,
        commit: str,
        context: str,
        private_root: Path,
        secret_store: Path,
        kubeconfig: Path,
        runner: Runner,
    ) -> None:
        self.commit = commit
        self.context = context
        self.private_root = private_root
        self.secret_store = secret_store
        self.kubeconfig = kubeconfig
        self._runner = runner

    def bootstrap(
        self,
        *,
        identity_mode: str,
        issuer_url: str,
        client_id: str,
        key_factory: KeyFactory,
        installation_id_factory: InstallationIdFactory,
    ) -> None:
        _bootstrap_acceptance_trust_locked(
            commit=self.commit,
            kubeconfig=self.kubeconfig,
            context=self.context,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            apply=True,
            private_root=self.private_root,
            secret_store=self.secret_store,
            runner=self._runner,
            key_factory=key_factory,
            installation_id_factory=installation_id_factory,
        )


@contextmanager
def locked_bootstrap_port(
    *,
    commit: str,
    kubeconfig: Path,
    context: str,
    runner: Runner,
) -> Iterator[LockedBootstrapPort]:
    """Hold the canonical installation lock and expose one bootstrap execution port."""

    private_root = _prepare_private_root(INSTALLATION_STATE.PRIVATE_ROOT)
    with _installation_lock(private_root):
        context_digest = hashlib.sha256(context.encode("utf-8")).hexdigest()
        flattened_kubeconfig = _snapshot_kubeconfig(
            source=kubeconfig,
            private_root=private_root,
            commit=f"{commit}-new-installation-{context_digest}",
            context=context,
            runner=runner,
        )
        yield LockedBootstrapPort(
            commit=commit,
            context=context,
            private_root=private_root,
            secret_store=INSTALLATION_STATE.SECRET_STORE,
            kubeconfig=flattened_kubeconfig,
            runner=runner,
        )


def bootstrap_acceptance_trust(
    *,
    commit: str,
    kubeconfig: Path,
    context: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    apply: bool,
    runner: Runner = run_command,
    key_factory: KeyFactory = lambda: secrets.token_bytes(32),
    installation_id_factory: InstallationIdFactory = lambda: str(uuid4()),
) -> None:
    """Prepare and verify only the installation-owned acceptance trust root."""

    if FULL_SHA_PATTERN.fullmatch(commit) is None:
        raise BootstrapError("commit must be a full lowercase Git SHA")
    if not context or context != context.strip():
        raise BootstrapError("Kubernetes context must be exact and non-empty")
    if identity_mode not in {"bundledKeycloak", "externalOidc"}:
        raise BootstrapError("identity mode is unsupported")
    if runner(["git", "status", "--porcelain", "--untracked-files=all"], None):
        raise BootstrapError("source checkout must be clean")
    try:
        head = runner(["git", "rev-parse", "HEAD"], None).decode().strip()
    except UnicodeDecodeError as exc:
        raise BootstrapError("source HEAD is invalid") from exc
    if head != commit:
        raise BootstrapError("source HEAD does not match commit")
    try:
        INSTALLATION_STATE.validate_identity_selection(
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
        )
    except INSTALLATION_STATE.InstallationStateContractError as exc:
        raise BootstrapError(str(exc)) from exc

    private_root = _prepare_private_root(INSTALLATION_STATE.PRIVATE_ROOT)
    secret_store = INSTALLATION_STATE.SECRET_STORE
    with _installation_lock(private_root):
        _bootstrap_acceptance_trust_locked(
            commit=commit,
            kubeconfig=kubeconfig,
            context=context,
            identity_mode=identity_mode,
            issuer_url=issuer_url,
            client_id=client_id,
            apply=apply,
            private_root=private_root,
            secret_store=secret_store,
            runner=runner,
            key_factory=key_factory,
            installation_id_factory=installation_id_factory,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument(
        "--identity-mode",
        choices=("bundledKeycloak", "externalOidc"),
        required=True,
    )
    parser.add_argument("--issuer-url", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    runner: Runner = run_command,
    key_factory: KeyFactory = lambda: secrets.token_bytes(32),
    installation_id_factory: InstallationIdFactory = lambda: str(uuid4()),
) -> int:
    arguments = build_parser().parse_args(argv)
    bootstrap_acceptance_trust(
        commit=arguments.commit,
        kubeconfig=arguments.kubeconfig,
        context=arguments.context,
        identity_mode=arguments.identity_mode,
        issuer_url=arguments.issuer_url,
        client_id=arguments.client_id,
        apply=arguments.apply,
        runner=runner,
        key_factory=key_factory,
        installation_id_factory=installation_id_factory,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"acceptance trust bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
