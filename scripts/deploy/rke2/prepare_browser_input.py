"""Publish one mode-specific private browser acceptance input."""

from __future__ import annotations

import argparse
import errno
import fcntl
import importlib.util
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_PATTERN = re.compile(r"^run-[a-z0-9][a-z0-9-]{6,57}[a-z0-9]$")
SECRET_STORE_RELATIVE_PATH = Path("install-secrets/rke2")


def _load_private_input() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_browser_input_private_input",
        SCRIPT_DIRECTORY / "private_input.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("browser-input private dependency is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input()


class BrowserInputError(ValueError):
    """Raised when browser acceptance credentials violate the contract."""


class BrowserLoginDriver(NamedTuple):
    """Typed browser login form contract for one OIDC adapter."""

    kind: str
    username_selector: str | None = None
    password_selector: str | None = None
    submit_selector: str | None = None
    error_selector: str | None = None

    def to_document(self) -> dict[str, str]:
        if self.kind == "keycloak" and all(
            value is None
            for value in (
                self.username_selector,
                self.password_selector,
                self.submit_selector,
                self.error_selector,
            )
        ):
            return {"kind": "keycloak"}
        fields = {
            "usernameSelector": self.username_selector,
            "passwordSelector": self.password_selector,
            "submitSelector": self.submit_selector,
            "errorSelector": self.error_selector,
        }
        if self.kind != "form" or any(
            not isinstance(value, str)
            or not 1 <= len(value) <= 256
            or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            for value in fields.values()
        ):
            raise BrowserInputError("browser login driver is invalid")
        return {"kind": "form", **fields}  # type: ignore[dict-item]


class BrowserInputRequest(NamedTuple):
    """Mode-neutral sources for one canonical browser input."""

    expected_commit: str
    deployment_run_id: str
    authentication_mode: str
    login_mode: str
    login_driver: BrowserLoginDriver
    identity_artifacts_directory: Path | None
    login_username_file: Path | None = None
    login_password_file: Path | None = None


class BrowserInputPaths(NamedTuple):
    directory: Path
    output: Path
    break_glass_username: Path
    break_glass_password: Path
    admin_username: Path
    admin_password: Path
    platform_admin_username: Path
    platform_admin_password: Path


class CredentialSource(NamedTuple):
    key: str
    path: Path
    description: str
    username: bool


def canonical_paths(
    *,
    expected_commit: str,
    deployment_run_id: str,
    identity_artifacts_directory: Path | None,
    private_root: Path | None = None,
) -> BrowserInputPaths:
    if FULL_SHA_PATTERN.fullmatch(expected_commit) is None:
        raise BrowserInputError("expected browser-input commit is invalid")
    if RUN_ID_PATTERN.fullmatch(deployment_run_id) is None:
        raise BrowserInputError("deployment run ID is invalid")
    try:
        root = PRIVATE_INPUT.private_root_path(private_root)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise BrowserInputError(str(exc)) from exc
    identity_artifacts = (
        identity_artifacts_directory
        if identity_artifacts_directory is not None
        else root / SECRET_STORE_RELATIVE_PATH / "identity-artifacts"
    )
    directory = root / "acceptance-inputs" / expected_commit / deployment_run_id
    return BrowserInputPaths(
        directory=directory,
        output=directory / "browser-input.json",
        break_glass_username=(identity_artifacts / "keycloak-break-glass" / "username"),
        break_glass_password=(identity_artifacts / "keycloak-break-glass" / "password"),
        admin_username=(identity_artifacts / "keycloak-bootstrap-admin" / "username"),
        admin_password=(identity_artifacts / "keycloak-bootstrap-admin" / "password"),
        platform_admin_username=(
            identity_artifacts / "keycloak-platform-admin" / "username"
        ),
        platform_admin_password=(
            identity_artifacts / "keycloak-platform-admin" / "password"
        ),
    )


def _ensure_private_child(*, parent: Path, name: str, private_root: Path) -> Path:
    destination = parent / name
    try:
        parent_descriptor = os.open(
            parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise BrowserInputError(
            "browser-input parent directory is unavailable"
        ) from exc
    created = False
    try:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
            created = True
        except FileExistsError:
            pass
        PRIVATE_INPUT.validate_private_directory(
            destination,
            "browser-input directory",
            private_root=private_root,
        )
        if created:
            os.fsync(parent_descriptor)
    except (OSError, PRIVATE_INPUT.PrivateInputError) as exc:
        if created:
            try:
                os.rmdir(name, dir_fd=parent_descriptor)
            except OSError:
                pass
        raise BrowserInputError("browser-input directory cannot be created") from exc
    finally:
        os.close(parent_descriptor)
    return destination


def _ensure_output_directory(*, paths: BrowserInputPaths, private_root: Path) -> None:
    current = private_root
    for component in (
        "acceptance-inputs",
        paths.directory.parent.name,
        paths.directory.name,
    ):
        current = _ensure_private_child(
            parent=current,
            name=component,
            private_root=private_root,
        )
    if current != paths.directory:
        raise BrowserInputError("browser-input directory identity changed")


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
            raise BrowserInputError("browser-input private root lock is invalid")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise BrowserInputError(
                    "another browser-input preparation is already running"
                ) from exc
            raise BrowserInputError(
                "browser-input private root lock is unavailable"
            ) from exc
        locked = True
        locked_path_metadata = os.lstat(private_root)
        if (
            not stat.S_ISDIR(locked_path_metadata.st_mode)
            or stat.S_IMODE(locked_path_metadata.st_mode) != 0o700
            or locked_path_metadata.st_uid != os.geteuid()
            or metadata.st_dev != locked_path_metadata.st_dev
            or metadata.st_ino != locked_path_metadata.st_ino
        ):
            raise BrowserInputError("browser-input private root changed while locking")
        yield
    except BrowserInputError:
        raise
    except OSError as exc:
        raise BrowserInputError(
            "browser-input private root lock is unavailable"
        ) from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _credential_bytes(
    source: CredentialSource,
    *,
    private_root: Path,
) -> bytes:
    try:
        content = PRIVATE_INPUT.read_private_bytes(
            source.path,
            source.description,
            private_root=private_root,
            require_nonempty=True,
            maximum_size=4096,
        )
        value = content.decode("utf-8")
    except (PRIVATE_INPUT.PrivateInputError, UnicodeDecodeError) as exc:
        raise BrowserInputError(f"{source.description} is invalid") from exc
    limit = 256 if source.username else 4096
    if (
        not 1 <= len(value) <= limit
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or source.username
        and value != value.strip()
    ):
        raise BrowserInputError(f"{source.description} is invalid")
    return content


def _read_source_set(
    sources: tuple[CredentialSource, ...],
    *,
    private_root: Path,
) -> dict[str, bytes]:
    return {
        source.key: _credential_bytes(source, private_root=private_root)
        for source in sources
    }


def _credential_value(source_set: dict[str, bytes], key: str) -> str:
    return source_set[key].decode("utf-8")


def prepare_browser_input(
    request: BrowserInputRequest,
    *,
    private_root: Path | None = None,
) -> Path:
    """Create or exactly resume one run-bound browser input."""

    if request.authentication_mode not in {"bundledKeycloak", "externalOidc"}:
        raise BrowserInputError("browser input authentication mode is invalid")
    if request.login_mode not in {"breakGlass", "files"}:
        raise BrowserInputError("browser input login mode is invalid")
    if (request.login_username_file is None) != (request.login_password_file is None):
        raise BrowserInputError("explicit login credentials must be a complete pair")
    explicit_login = request.login_username_file is not None
    if (request.login_mode == "files") != explicit_login:
        raise BrowserInputError("browser input login source selection is invalid")
    if request.authentication_mode == "externalOidc" and request.login_mode != "files":
        raise BrowserInputError("external OIDC browser input requires login files")
    root = PRIVATE_INPUT.private_root_path(private_root)
    base_identity_artifacts = root / SECRET_STORE_RELATIVE_PATH / "identity-artifacts"
    allowed_identity_artifacts = {
        base_identity_artifacts,
        base_identity_artifacts / "postgres-disabled",
    }
    if (
        request.authentication_mode == "bundledKeycloak"
        and request.identity_artifacts_directory not in allowed_identity_artifacts
    ) or (
        request.authentication_mode == "externalOidc"
        and request.identity_artifacts_directory is not None
    ):
        raise BrowserInputError("browser input Identity artifact source is invalid")
    driver = request.login_driver.to_document()
    if (
        request.authentication_mode == "bundledKeycloak"
        and driver != {"kind": "keycloak"}
    ) or (
        request.authentication_mode == "externalOidc" and driver.get("kind") != "form"
    ):
        raise BrowserInputError(
            "browser login driver does not match the authentication mode"
        )
    paths = canonical_paths(
        expected_commit=request.expected_commit,
        deployment_run_id=request.deployment_run_id,
        identity_artifacts_directory=request.identity_artifacts_directory,
        private_root=private_root,
    )
    sources: list[CredentialSource] = []
    if request.authentication_mode == "bundledKeycloak":
        sources.extend(
            [
                CredentialSource(
                    "breakGlassUser.username",
                    paths.break_glass_username,
                    "Keycloak break-glass username",
                    True,
                ),
                CredentialSource(
                    "breakGlassUser.password",
                    paths.break_glass_password,
                    "Keycloak break-glass password",
                    False,
                ),
                CredentialSource(
                    "adminUser.username",
                    paths.admin_username,
                    "Keycloak bootstrap administrator username",
                    True,
                ),
                CredentialSource(
                    "adminUser.password",
                    paths.admin_password,
                    "Keycloak bootstrap administrator password",
                    False,
                ),
                CredentialSource(
                    "platformAdminUser.username",
                    paths.platform_admin_username,
                    "Aileron platform administrator username",
                    True,
                ),
                CredentialSource(
                    "platformAdminUser.password",
                    paths.platform_admin_password,
                    "Aileron platform administrator password",
                    False,
                ),
            ]
        )
    if explicit_login:
        assert request.login_username_file is not None
        assert request.login_password_file is not None
        sources.extend(
            [
                CredentialSource(
                    "loginUser.username",
                    request.login_username_file,
                    "OIDC acceptance login username",
                    True,
                ),
                CredentialSource(
                    "loginUser.password",
                    request.login_password_file,
                    "OIDC acceptance login password",
                    False,
                ),
            ]
        )
    source_contract = tuple(sources)
    with _installation_lock(root):
        source_set = _read_source_set(source_contract, private_root=root)
        document: dict[str, Any] = {
            "loginDriver": driver,
            "schemaVersion": "aileron-browser-input/v2",
        }
        if request.authentication_mode == "bundledKeycloak":
            break_glass = {
                "username": _credential_value(source_set, "breakGlassUser.username"),
                "password": _credential_value(source_set, "breakGlassUser.password"),
            }
            administrator = {
                "username": _credential_value(source_set, "adminUser.username"),
                "password": _credential_value(source_set, "adminUser.password"),
            }
            platform_administrator = {
                "username": _credential_value(
                    source_set, "platformAdminUser.username"
                ),
                "password": _credential_value(
                    source_set, "platformAdminUser.password"
                ),
            }
            document.update(
                {
                    "adminUser": administrator,
                    "breakGlassUser": break_glass,
                    "platformAdminUser": platform_administrator,
                }
            )
        if request.login_mode == "breakGlass":
            login = dict(break_glass)
        else:
            login = {
                "username": _credential_value(source_set, "loginUser.username"),
                "password": _credential_value(source_set, "loginUser.password"),
            }
        document["loginUser"] = login
        content = (
            json.dumps(
                document,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        _ensure_output_directory(paths=paths, private_root=root)
        if _read_source_set(source_contract, private_root=root) != source_set:
            raise BrowserInputError(
                "browser-input credential source set changed before publication"
            )
        try:
            return PRIVATE_INPUT.write_private_snapshot(
                destination=paths.output,
                content=content,
                description="browser acceptance input",
                private_root=root,
                allow_existing_exact=True,
            )
        except PRIVATE_INPUT.PrivateInputError as exc:
            raise BrowserInputError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--deployment-run-id", required=True)
    parser.add_argument(
        "--authentication-mode",
        choices=("bundledKeycloak", "externalOidc"),
        required=True,
    )
    parser.add_argument("--login-mode", choices=("breakGlass", "files"), required=True)
    parser.add_argument("--login-username-file", type=Path)
    parser.add_argument("--login-password-file", type=Path)
    parser.add_argument("--identity-artifacts-directory", type=Path)
    parser.add_argument("--username-selector")
    parser.add_argument("--password-selector")
    parser.add_argument("--submit-selector")
    parser.add_argument("--error-selector")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        output = prepare_browser_input(
            BrowserInputRequest(
                expected_commit=arguments.expected_commit,
                deployment_run_id=arguments.deployment_run_id,
                authentication_mode=arguments.authentication_mode,
                login_mode=arguments.login_mode,
                login_driver=BrowserLoginDriver(
                    kind=(
                        "keycloak"
                        if arguments.authentication_mode == "bundledKeycloak"
                        else "form"
                    ),
                    username_selector=arguments.username_selector,
                    password_selector=arguments.password_selector,
                    submit_selector=arguments.submit_selector,
                    error_selector=arguments.error_selector,
                ),
                identity_artifacts_directory=arguments.identity_artifacts_directory,
                login_username_file=arguments.login_username_file,
                login_password_file=arguments.login_password_file,
            )
        )
    except BrowserInputError as exc:
        raise SystemExit(f"browser-input preparation failed: {exc}") from exc
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
