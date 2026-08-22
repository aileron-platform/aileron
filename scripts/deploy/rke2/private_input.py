#!/usr/bin/env python3
"""Validate and snapshot installer-owned private deployment inputs."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ModuleNotFoundError:  # Deployment host prerequisite, reported by the caller.
    yaml = None  # type: ignore[assignment]

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
MAX_PRIVATE_INPUT_BYTES = 16 * 1024 * 1024
KUBECONFIG_EXTERNAL_REFERENCE_KEYS = {
    "auth-provider",
    "certificate-authority",
    "client-certificate",
    "client-key",
    "exec",
    "token-file",
    "tokenFile",
}
KUBERNETES_NAMESPACE_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
CommandRunner = Callable[..., str]


def _load_installation_state() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_private_input_installation_state",
        SCRIPT_DIRECTORY / "installation_state.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("installation private-state contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_installation_state()


class PrivateInputError(ValueError):
    """Raised when a private deployment input violates its contract."""


def _require_canonical_path(
    path: Path,
    description: str,
    *,
    require_existing: bool,
) -> None:
    try:
        canonical = path.resolve(strict=require_existing)
    except OSError as exc:
        raise PrivateInputError(f"{description} is unavailable") from exc
    if path != canonical:
        raise PrivateInputError(f"{description} must use its canonical path")


def reject_symlink_components(path: Path, description: str) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PrivateInputError(f"{description} is unreadable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise PrivateInputError(f"{description} must not contain a symbolic link")


def private_root_path(private_root: Path | None = None) -> Path:
    root = private_root or INSTALLATION_STATE.PRIVATE_ROOT
    if not root.is_absolute():
        raise PrivateInputError("installation private root must be absolute")
    reject_symlink_components(root, "installation private root")
    _require_canonical_path(
        root,
        "installation private root",
        require_existing=True,
    )
    try:
        metadata = os.lstat(root)
    except OSError as exc:
        raise PrivateInputError("installation private root is unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise PrivateInputError(
            "installation private root must be an owner-controlled mode-0700 directory"
        )
    return root


def validate_installation_private_root(
    path: Path,
    *,
    repository_root: Path,
) -> Path:
    """Validate the canonical private root outside the Git checkout."""

    if not path.is_absolute():
        raise PrivateInputError(
            "installation private root must use an absolute path"
        )
    reject_symlink_components(path, "installation private root")
    try:
        path.resolve(strict=True).relative_to(repository_root.resolve())
    except ValueError:
        pass
    except OSError as exc:
        raise PrivateInputError(
            "installation private root is missing or unreadable"
        ) from exc
    else:
        raise PrivateInputError(
            "installation private root must be outside the Git checkout"
        )
    return private_root_path(path)


def _validate_private_parent_directories(
    path: Path,
    description: str,
    *,
    private_root: Path | None = None,
) -> None:
    root = private_root_path(private_root)
    try:
        resolved_root = root.resolve(strict=True)
        if path.resolve(strict=True) == resolved_root:
            return
        relative_parent = path.parent.resolve(strict=True).relative_to(
            resolved_root
        )
    except (OSError, ValueError) as exc:
        raise PrivateInputError(
            f"{description} parent must be within the installation private root"
        ) from exc

    current = root
    for component in relative_parent.parts:
        current /= component
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise PrivateInputError(f"{description} parent is unavailable") from exc
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or metadata.st_uid != os.geteuid()
        ):
            raise PrivateInputError(
                f"{description} parent must be an owner-controlled mode-0700 directory"
            )


def _within_private_root(
    path: Path,
    description: str,
    *,
    private_root: Path | None = None,
    require_existing: bool = True,
) -> None:
    root = private_root_path(private_root)
    try:
        path.resolve(strict=require_existing).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise PrivateInputError(
            f"{description} must be within the installation private root"
        ) from exc


def _open_private_file(
    path: Path,
    description: str,
    *,
    require_nonempty: bool,
    private_root: Path | None = None,
) -> tuple[int, os.stat_result]:
    if not path.is_absolute():
        raise PrivateInputError(f"{description} must use an absolute path")
    reject_symlink_components(path, description)
    _require_canonical_path(path, description, require_existing=True)
    _within_private_root(path, description, private_root=private_root)
    _validate_private_parent_directories(
        path,
        description,
        private_root=private_root,
    )
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise PrivateInputError(f"{description} is missing or unreadable") from exc
    try:
        metadata = os.fstat(descriptor)
        path_metadata = os.lstat(path)
    except OSError as exc:
        os.close(descriptor)
        raise PrivateInputError(f"{description} is unreadable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
        or path_metadata.st_uid != os.geteuid()
        or metadata.st_nlink != 1
        or metadata.st_dev != path_metadata.st_dev
        or metadata.st_ino != path_metadata.st_ino
        or require_nonempty
        and metadata.st_size == 0
    ):
        os.close(descriptor)
        raise PrivateInputError(
            f"{description} must be an owner-controlled mode-0600 regular file"
        )
    return descriptor, metadata


def validate_private_file(
    path: Path,
    description: str,
    *,
    require_nonempty: bool = True,
    private_root: Path | None = None,
) -> Path:
    descriptor, _ = _open_private_file(
        path,
        description,
        require_nonempty=require_nonempty,
        private_root=private_root,
    )
    os.close(descriptor)
    return path


def validate_private_directory(
    path: Path,
    description: str,
    *,
    expected_relative_path: Path | None = None,
    private_root: Path | None = None,
) -> Path:
    if not path.is_absolute():
        raise PrivateInputError(f"{description} must use an absolute path")
    reject_symlink_components(path, description)
    _require_canonical_path(path, description, require_existing=True)
    _within_private_root(path, description, private_root=private_root)
    _validate_private_parent_directories(
        path,
        description,
        private_root=private_root,
    )
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise PrivateInputError(f"{description} is unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise PrivateInputError(
            f"{description} must be an owner-controlled mode-0700 directory"
        )
    if expected_relative_path is not None:
        expected = private_root_path(private_root) / expected_relative_path
        if path.resolve(strict=True) != expected.resolve(strict=True):
            raise PrivateInputError(
                f"{description} is not the installer-owned directory"
            )
    return path


def ensure_private_directory(
    path: Path,
    description: str,
    *,
    private_root: Path | None = None,
) -> Path:
    """Create and fsync one canonical owner-only directory chain."""

    root = private_root_path(private_root)
    if not path.is_absolute():
        raise PrivateInputError(f"{description} must use an absolute path")
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PrivateInputError(f"{description} must be inside the private root") from exc
    current = root
    for component in relative.parts:
        parent_descriptor: int | None = None
        try:
            validate_private_directory(
                current,
                description,
                private_root=root,
            )
            parent_descriptor = os.open(
                current,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            try:
                os.mkdir(component, mode=0o700, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except FileExistsError:
                pass
            current /= component
            validate_private_directory(
                current,
                description,
                private_root=root,
            )
        except (OSError, PrivateInputError) as exc:
            raise PrivateInputError(f"{description} could not be prepared") from exc
        finally:
            if parent_descriptor is not None:
                os.close(parent_descriptor)
    return current


def _validate_installer_snapshot(
    path: Path,
    *,
    commit: str,
    snapshot_name: str,
    description: str,
    private_root: Path | None = None,
) -> None:
    if FULL_SHA_PATTERN.fullmatch(commit) is None:
        raise PrivateInputError("installation snapshot commit is invalid")
    expected = (
        private_root_path(private_root)
        / "install"
        / commit
        / "snapshots"
        / snapshot_name
    )
    try:
        is_exact_snapshot = path.resolve(strict=True) == expected.resolve(strict=True)
    except OSError as exc:
        raise PrivateInputError(f"{description} is not an installer snapshot") from exc
    if not is_exact_snapshot:
        raise PrivateInputError(f"{description} is not an installer snapshot")


def read_private_bytes(
    path: Path,
    description: str,
    *,
    private_root: Path | None = None,
    require_nonempty: bool = True,
    maximum_size: int = MAX_PRIVATE_INPUT_BYTES,
) -> bytes:
    """Read one private file from a single stable descriptor."""

    descriptor, before = _open_private_file(
        path,
        description,
        require_nonempty=require_nonempty,
        private_root=private_root,
    )
    try:
        if before.st_size > maximum_size:
            raise PrivateInputError(f"{description} is too large")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_size + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_size:
                raise PrivateInputError(f"{description} is too large")
        after = os.fstat(descriptor)
        path_after = os.lstat(path)
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
            any(getattr(before, field) != getattr(after, field) for field in stable_fields)
            or after.st_dev != path_after.st_dev
            or after.st_ino != path_after.st_ino
            or path_after.st_uid != os.geteuid()
            or total != after.st_size
        ):
            raise PrivateInputError(f"{description} changed while it was read")
        reject_symlink_components(path, description)
        _within_private_root(path, description, private_root=private_root)
        return b"".join(chunks)
    except OSError as exc:
        raise PrivateInputError(f"{description} is unreadable") from exc
    finally:
        os.close(descriptor)


def read_private_text(
    path: Path,
    description: str,
    *,
    private_root: Path | None = None,
    require_nonempty: bool = True,
    maximum_size: int = MAX_PRIVATE_INPUT_BYTES,
) -> str:
    """Read one stable private UTF-8 text file."""

    try:
        return read_private_bytes(
            path,
            description,
            private_root=private_root,
            require_nonempty=require_nonempty,
            maximum_size=maximum_size,
        ).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PrivateInputError(f"{description} is unreadable") from exc


def write_private_snapshot(
    *,
    destination: Path,
    content: bytes,
    description: str,
    private_root: Path | None = None,
    allow_existing_exact: bool = False,
) -> Path:
    """Publish exact bytes as one mode-0600, fsynced, write-once snapshot."""

    if not destination.is_absolute():
        raise PrivateInputError(f"{description} snapshot must use an absolute path")
    root = private_root_path(private_root)
    reject_symlink_components(destination, f"{description} snapshot")
    _require_canonical_path(
        destination,
        f"{description} snapshot",
        require_existing=False,
    )
    _within_private_root(
        destination,
        f"{description} snapshot",
        private_root=root,
        require_existing=False,
    )
    snapshot_directory = destination.parent
    if not snapshot_directory.exists():
        snapshot_parent = validate_private_directory(
            snapshot_directory.parent,
            "deployment snapshot parent directory",
            private_root=root,
        )
        try:
            snapshot_directory.mkdir(mode=0o700)
        except OSError as exc:
            raise PrivateInputError(
                f"{description} snapshot directory cannot be created"
            ) from exc
        try:
            parent_descriptor = os.open(
                snapshot_parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            try:
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
        except OSError as exc:
            try:
                snapshot_directory.rmdir()
            except OSError:
                pass
            raise PrivateInputError(
                f"{description} snapshot directory cannot be synchronized"
            ) from exc
    validate_private_directory(
        snapshot_directory,
        "deployment snapshot directory",
        private_root=root,
    )

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        if allow_existing_exact and read_private_bytes(
            destination,
            f"{description} snapshot",
            private_root=root,
            require_nonempty=bool(content),
        ) == content:
            return destination
        if allow_existing_exact:
            raise PrivateInputError(f"{description} snapshot content changed") from exc
        raise PrivateInputError(f"{description} snapshot already exists") from exc
    except OSError as exc:
        raise PrivateInputError(f"{description} snapshot cannot be created") from exc

    write_error: Exception | None = None
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PrivateInputError(f"{description} snapshot cannot be written")
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
    except Exception as exc:
        write_error = exc
    finally:
        os.close(descriptor)
    if write_error is not None:
        try:
            destination.unlink()
        except OSError:
            pass
        if isinstance(write_error, PrivateInputError):
            raise write_error
        raise PrivateInputError(
            f"{description} snapshot cannot be written"
        ) from write_error
    try:
        directory_descriptor = os.open(
            snapshot_directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        try:
            destination.unlink()
        except OSError:
            pass
        raise PrivateInputError(
            f"{description} snapshot cannot be synchronized"
        ) from exc
    return destination


def snapshot_private_file(
    *,
    source: Path,
    destination: Path,
    description: str,
    commit: str | None = None,
    snapshot_name: str | None = None,
    require_nonempty: bool = True,
    private_root: Path | None = None,
    allow_existing_exact: bool = False,
) -> Path:
    if (commit is None) != (snapshot_name is None):
        raise PrivateInputError(
            "snapshot commit and snapshot name must be provided together"
        )
    if commit is not None and snapshot_name is not None:
        _validate_installer_snapshot(
            source,
            commit=commit,
            snapshot_name=snapshot_name,
            description=description,
            private_root=private_root,
        )
    content = read_private_bytes(
        source,
        description,
        private_root=private_root,
        require_nonempty=require_nonempty,
    )
    return write_private_snapshot(
        destination=destination,
        content=content,
        description=description,
        private_root=private_root,
        allow_existing_exact=allow_existing_exact,
    )


def _load_kubeconfig(content: bytes, description: str) -> dict[str, Any]:
    if yaml is None:
        raise PrivateInputError("PyYAML is required to validate kubeconfig")
    try:
        document = yaml.safe_load(content)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise PrivateInputError(f"{description} is invalid") from exc
    if not isinstance(document, dict):
        raise PrivateInputError(f"{description} must be a Kubernetes config object")

    def reject_external_references(value: Any) -> None:
        if isinstance(value, dict):
            forbidden = KUBECONFIG_EXTERNAL_REFERENCE_KEYS.intersection(value)
            if forbidden:
                raise PrivateInputError(
                    f"{description} contains an external or dynamic reference"
                )
            for nested in value.values():
                reject_external_references(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_external_references(nested)

    reject_external_references(document)
    return document


def _named_kubeconfig_entries(
    document: dict[str, Any], key: str, description: str
) -> dict[str, dict[str, Any]]:
    entries = document.get(key)
    if not isinstance(entries, list):
        raise PrivateInputError(f"{description} {key} must be an array")
    result: dict[str, dict[str, Any]] = {}
    singular = {"clusters": "cluster", "contexts": "context", "users": "user"}[key]
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"name", singular}
            or not isinstance(entry.get("name"), str)
            or not entry["name"]
            or not isinstance(entry.get(singular), dict)
            or entry["name"] in result
        ):
            raise PrivateInputError(f"{description} {key} are invalid")
        result[entry["name"]] = entry[singular]
    return result


def _decode_kubeconfig_data(value: Any, description: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PrivateInputError(f"{description} is missing")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PrivateInputError(f"{description} is invalid") from exc
    if not decoded:
        raise PrivateInputError(f"{description} is empty")
    return decoded


def validate_self_contained_kubeconfig(
    content: bytes,
    *,
    expected_context: str,
    description: str,
    require_minified: bool,
) -> str:
    """Return a non-secret digest of one selected inline-only kubeconfig identity."""

    document = _load_kubeconfig(content, description)
    if (
        document.get("apiVersion") != "v1"
        or document.get("kind") != "Config"
        or document.get("current-context") != expected_context
    ):
        raise PrivateInputError(f"{description} context does not match")
    contexts = _named_kubeconfig_entries(document, "contexts", description)
    clusters = _named_kubeconfig_entries(document, "clusters", description)
    users = _named_kubeconfig_entries(document, "users", description)
    if require_minified and not (
        len(contexts) == len(clusters) == len(users) == 1
    ):
        raise PrivateInputError(f"{description} is not exactly minified")
    selected_context = contexts.get(expected_context)
    if selected_context is None:
        raise PrivateInputError(f"{description} context does not match")
    cluster_name = selected_context.get("cluster")
    user_name = selected_context.get("user")
    if not isinstance(cluster_name, str) or not isinstance(user_name, str):
        raise PrivateInputError(f"{description} context is invalid")
    cluster = clusters.get(cluster_name)
    user = users.get(user_name)
    if cluster is None or user is None:
        raise PrivateInputError(f"{description} context references are invalid")
    allowed_context_keys = {"cluster", "user"}
    if "namespace" in selected_context:
        namespace = selected_context["namespace"]
        if (
            not isinstance(namespace, str)
            or KUBERNETES_NAMESPACE_PATTERN.fullmatch(namespace) is None
        ):
            raise PrivateInputError(f"{description} context namespace is invalid")
        allowed_context_keys.add("namespace")
    else:
        namespace = None
    if set(selected_context) != allowed_context_keys:
        raise PrivateInputError(
            f"{description} selected context contains unsupported fields"
        )
    if set(cluster) != {"server", "certificate-authority-data"}:
        raise PrivateInputError(
            f"{description} selected cluster contains unsupported fields"
        )
    server = cluster.get("server")
    if not isinstance(server, str) or server != server.strip():
        raise PrivateInputError(f"{description} cluster server is invalid")
    parsed_server = urlparse(server)
    try:
        server_port = parsed_server.port
    except ValueError as exc:
        raise PrivateInputError(f"{description} cluster server is invalid") from exc
    if (
        parsed_server.scheme != "https"
        or not parsed_server.netloc
        or parsed_server.hostname is None
        or parsed_server.username is not None
        or parsed_server.password is not None
        or parsed_server.query
        or parsed_server.fragment
        or server_port is not None
        and not 1 <= server_port <= 65535
    ):
        raise PrivateInputError(f"{description} cluster server is invalid")
    ca_data = _decode_kubeconfig_data(
        cluster.get("certificate-authority-data"),
        f"{description} certificate authority data",
    )
    token = user.get("token")
    certificate = user.get("client-certificate-data")
    private_key = user.get("client-key-data")
    if set(user) == {"token"}:
        if not isinstance(token, str) or not token or token != token.strip():
            raise PrivateInputError(f"{description} inline token is invalid")
        authentication_identity = {
            "method": "token",
            "tokenSha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        }
    elif set(user) == {"client-certificate-data", "client-key-data"}:
        certificate_data = _decode_kubeconfig_data(
            certificate,
            f"{description} client certificate data",
        )
        private_key_data = _decode_kubeconfig_data(
            private_key,
            f"{description} client key data",
        )
        authentication_identity = {
            "method": "clientCertificate",
            "certificateSha256": hashlib.sha256(certificate_data).hexdigest(),
            "privateKeySha256": hashlib.sha256(private_key_data).hexdigest(),
        }
    else:
        raise PrivateInputError(
            f"{description} must contain exactly one inline authentication method"
        )
    selected_identity = {
        "contextName": expected_context,
        "context": {
            "cluster": cluster_name,
            "user": user_name,
            "namespace": namespace,
        },
        "clusterName": cluster_name,
        "cluster": {
            "server": server,
            "certificateAuthoritySha256": hashlib.sha256(ca_data).hexdigest(),
        },
        "userName": user_name,
        "authentication": authentication_identity,
    }
    return hashlib.sha256(
        json.dumps(
            selected_identity,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def snapshot_self_contained_kubeconfig(
    *,
    source: Path,
    raw_destination: Path,
    flattened_destination: Path,
    context: str,
    runner: CommandRunner,
    private_root: Path | None = None,
    allow_existing_exact: bool = False,
) -> Path:
    """Snapshot and flatten one inline-only kubeconfig without rereading its source."""

    raw_content = read_private_bytes(
        source,
        "kubeconfig",
        private_root=private_root,
    )
    raw_identity = validate_self_contained_kubeconfig(
        raw_content,
        expected_context=context,
        description="raw kubeconfig snapshot",
        require_minified=False,
    )
    raw_snapshot = write_private_snapshot(
        destination=raw_destination,
        content=raw_content,
        description="kubeconfig",
        private_root=private_root,
        allow_existing_exact=allow_existing_exact,
    )
    flattened = runner(
        [
            "kubectl",
            "--kubeconfig",
            str(raw_snapshot),
            "--context",
            context,
            "config",
            "view",
            "--raw",
            "--flatten",
            "--minify",
            "--output=json",
        ],
        environment={"KUBECONFIG": str(raw_snapshot)},
    ).encode("utf-8")
    flattened_identity = validate_self_contained_kubeconfig(
        flattened,
        expected_context=context,
        description="flattened kubeconfig",
        require_minified=True,
    )
    if flattened_identity != raw_identity:
        raise PrivateInputError(
            "flattened kubeconfig selected identity changed"
        )
    return write_private_snapshot(
        destination=flattened_destination,
        content=flattened,
        description="flattened kubeconfig",
        private_root=private_root,
        allow_existing_exact=allow_existing_exact,
    )


def _path(value: str) -> Path:
    return Path(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("private-root", "snapshot-file", "validate-directory"),
    )
    parser.add_argument("--source", type=_path)
    parser.add_argument("--destination", type=_path)
    parser.add_argument("--path", type=_path)
    parser.add_argument("--description")
    parser.add_argument("--commit")
    parser.add_argument("--snapshot-name")
    parser.add_argument("--expected-relative-path", type=_path)
    parser.add_argument("--allow-empty", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.action == "private-root":
            print(private_root_path())
        elif arguments.action == "validate-directory":
            if arguments.path is None or arguments.description is None:
                raise PrivateInputError(
                    "validate-directory requires --path and --description"
                )
            validate_private_directory(
                arguments.path,
                arguments.description,
                expected_relative_path=arguments.expected_relative_path,
            )
        else:
            if (
                arguments.source is None
                or arguments.destination is None
                or arguments.description is None
            ):
                raise PrivateInputError(
                    "snapshot-file requires --source, --destination, and --description"
                )
            snapshot_private_file(
                source=arguments.source,
                destination=arguments.destination,
                description=arguments.description,
                commit=arguments.commit,
                snapshot_name=arguments.snapshot_name,
                require_nonempty=not arguments.allow_empty,
            )
    except PrivateInputError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
