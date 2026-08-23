from __future__ import annotations

import fcntl
import importlib.util
import json
import os
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "prepare_browser_input.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_browser_input", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMIT = "b" * 40
RUN_ID = "run-20260809-browser"


def _private_directory(path: Path) -> Path:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _private_file(path: Path, value: str) -> Path:
    _private_directory(path.parent)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _private_root(tmp_path: Path) -> Path:
    root = _private_directory(tmp_path / "private")
    identity = root / "install-secrets/rke2/identity-artifacts"
    _private_file(identity / "keycloak-break-glass/username", "emergency-user")
    _private_file(identity / "keycloak-break-glass/password", "emergency-secret")
    _private_file(identity / "keycloak-bootstrap-admin/username", "realm-admin")
    _private_file(identity / "keycloak-bootstrap-admin/password", "realm-secret")
    _private_file(identity / "keycloak-platform-admin/username", "platform-admin")
    _private_file(identity / "keycloak-platform-admin/password", "platform-secret")
    return root


def _request(
    root: Path,
    *,
    authentication_mode: str = "bundledKeycloak",
    login_mode: str = "breakGlass",
    username: Path | None = None,
    password: Path | None = None,
    driver: object | None = None,
) -> object:
    selected_driver = driver
    if selected_driver is None:
        selected_driver = (
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
    return MODULE.BrowserInputRequest(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        authentication_mode=authentication_mode,
        login_mode=login_mode,
        login_driver=selected_driver,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
            if authentication_mode == "bundledKeycloak"
            else None
        ),
        login_username_file=username,
        login_password_file=password,
    )


def test_canonical_paths_bind_output_and_installation_credentials(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)

    paths = MODULE.canonical_paths(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
        ),
        private_root=root,
    )

    assert paths.output == (
        root / "acceptance-inputs" / COMMIT / RUN_ID / "browser-input.json"
    )
    assert paths.break_glass_username == (
        root
        / "install-secrets/rke2/identity-artifacts"
        / "keycloak-break-glass/username"
    )
    assert paths.admin_password == (
        root
        / "install-secrets/rke2/identity-artifacts"
        / "keycloak-bootstrap-admin/password"
    )
    assert paths.platform_admin_username == (
        root
        / "install-secrets/rke2/identity-artifacts"
        / "keycloak-platform-admin/username"
    )


def test_current_homelab_explicitly_uses_break_glass_for_native_login(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)

    output = MODULE.prepare_browser_input(
        _request(root),
        private_root=root,
    )
    document = json.loads(output.read_bytes())

    assert document == {
        "adminUser": {"username": "realm-admin", "password": "realm-secret"},
        "breakGlassUser": {
            "username": "emergency-user",
            "password": "emergency-secret",
        },
        "loginDriver": {"kind": "keycloak"},
        "loginUser": {
            "username": "emergency-user",
            "password": "emergency-secret",
        },
        "platformAdminUser": {
            "username": "platform-admin",
            "password": "platform-secret",
        },
        "schemaVersion": "aileron-browser-input/v2",
    }
    assert output.read_bytes().endswith(b"\n")
    assert output.stat().st_mode & 0o777 == 0o600
    assert output.parent.stat().st_mode & 0o777 == 0o700


def test_external_identity_postgres_uses_the_installed_identity_artifacts(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    external = (
        root
        / "install-secrets/rke2/identity-artifacts/postgres-disabled"
    )
    _private_file(external / "keycloak-break-glass/username", "external-emergency")
    _private_file(external / "keycloak-break-glass/password", "external-secret")
    _private_file(external / "keycloak-bootstrap-admin/username", "external-admin")
    _private_file(external / "keycloak-bootstrap-admin/password", "external-admin-secret")
    _private_file(external / "keycloak-platform-admin/username", "external-platform")
    _private_file(external / "keycloak-platform-admin/password", "external-platform-secret")
    request = MODULE.BrowserInputRequest(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        authentication_mode="bundledKeycloak",
        login_mode="breakGlass",
        login_driver=MODULE.BrowserLoginDriver(kind="keycloak"),
        identity_artifacts_directory=external,
    )

    output = MODULE.prepare_browser_input(request, private_root=root)

    document = json.loads(output.read_bytes())
    assert document["loginUser"] == {
        "username": "external-emergency",
        "password": "external-secret",
    }
    assert document["adminUser"]["username"] == "external-admin"
    assert document["platformAdminUser"]["username"] == "external-platform"


def test_future_keycloak_federation_can_use_a_distinct_private_login_pair(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    username = _private_file(root / "directory-login/username", "directory-user")
    password = _private_file(root / "directory-login/password", "directory-secret")

    output = MODULE.prepare_browser_input(
        _request(root, login_mode="files", username=username, password=password),
        private_root=root,
    )
    document = json.loads(output.read_bytes())

    assert document["loginUser"] == {
        "username": "directory-user",
        "password": "directory-secret",
    }
    assert document["breakGlassUser"]["username"] == "emergency-user"
    assert document["adminUser"]["username"] == "realm-admin"
    assert document["platformAdminUser"]["username"] == "platform-admin"


def test_external_oidc_files_publish_only_form_login_contract(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    username = _private_file(root / "external-login/username", "external-user")
    password = _private_file(root / "external-login/password", "external-secret")

    output = MODULE.prepare_browser_input(
        _request(
            root,
            authentication_mode="externalOidc",
            login_mode="files",
            username=username,
            password=password,
        ),
        private_root=root,
    )

    assert json.loads(output.read_bytes()) == {
        "loginDriver": {
            "kind": "form",
            "usernameSelector": "#username",
            "passwordSelector": "#password",
            "submitSelector": "#submit",
            "errorSelector": "#error",
        },
        "loginUser": {
            "username": "external-user",
            "password": "external-secret",
        },
        "schemaVersion": "aileron-browser-input/v2",
    }


@pytest.mark.parametrize(
    ("field", "selector"),
    [
        (field, selector)
        for field in (
            "username_selector",
            "password_selector",
            "submit_selector",
            "error_selector",
        )
        for selector in ("", " #selector", "#selector ", "#select\nor", "x" * 257)
    ],
)
def test_form_selectors_require_canonical_text(
    tmp_path: Path,
    field: str,
    selector: str,
) -> None:
    root = _private_root(tmp_path)
    username = _private_file(root / "external-login/username", "external-user")
    password = _private_file(root / "external-login/password", "external-secret")
    driver = MODULE.BrowserLoginDriver(
        kind="form",
        username_selector="#username",
        password_selector="#password",
        submit_selector="#submit",
        error_selector="#error",
    )._replace(**{field: selector})

    with pytest.raises(MODULE.BrowserInputError, match="login driver is invalid"):
        MODULE.prepare_browser_input(
            _request(
                root,
                authentication_mode="externalOidc",
                login_mode="files",
                username=username,
                password=password,
                driver=driver,
            ),
            private_root=root,
        )


@pytest.mark.parametrize(
    ("use_break_glass", "username", "password"),
    [
        (False, None, None),
        (True, "username", "password"),
        (False, "username", None),
        (False, None, "password"),
    ],
)
def test_login_source_selection_must_be_explicit_and_complete(
    tmp_path: Path,
    use_break_glass: bool,
    username: str | None,
    password: str | None,
) -> None:
    root = _private_root(tmp_path)
    username_path = (
        _private_file(root / "login/username", username) if username else None
    )
    password_path = (
        _private_file(root / "login/password", password) if password else None
    )

    with pytest.raises(MODULE.BrowserInputError):
        MODULE.prepare_browser_input(
            _request(
                root,
                login_mode="breakGlass" if use_break_glass else "files",
                username=username_path,
                password=password_path,
            ),
            private_root=root,
        )


@pytest.mark.parametrize("invalid", ["", "name\n", " name", "name\x7f"])
def test_invalid_username_artifacts_are_rejected(tmp_path: Path, invalid: str) -> None:
    root = _private_root(tmp_path)
    paths = MODULE.canonical_paths(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
        ),
        private_root=root,
    )
    paths.break_glass_username.write_text(invalid, encoding="utf-8")

    with pytest.raises(MODULE.BrowserInputError, match="username is invalid"):
        MODULE.prepare_browser_input(
            _request(root),
            private_root=root,
        )


def test_public_and_hardlinked_credential_files_are_rejected(
    tmp_path: Path,
) -> None:
    root = _private_root(tmp_path)
    username = _private_file(root / "login/username", "directory-user")
    password = _private_file(root / "login/password", "directory-secret")
    password.chmod(0o644)

    with pytest.raises(MODULE.BrowserInputError):
        MODULE.prepare_browser_input(
            _request(
                root,
                login_mode="files",
                username=username,
                password=password,
            ),
            private_root=root,
        )

    password.chmod(0o600)
    linked = root / "login/linked-password"
    os.link(password, linked)
    with pytest.raises(MODULE.BrowserInputError):
        MODULE.prepare_browser_input(
            _request(
                root,
                login_mode="files",
                username=username,
                password=linked,
            ),
            private_root=root,
        )


def test_symbolic_link_credential_file_is_rejected(tmp_path: Path) -> None:
    root = _private_root(tmp_path)
    target = _private_file(root / "login/real-username", "directory-user")
    username = root / "login/username"
    username.symlink_to(target)
    password = _private_file(root / "login/password", "directory-secret")

    with pytest.raises(MODULE.BrowserInputError):
        MODULE.prepare_browser_input(
            _request(
                root,
                login_mode="files",
                username=username,
                password=password,
            ),
            private_root=root,
        )


def test_private_root_lock_contention_fails_without_publication(tmp_path: Path) -> None:
    root = _private_root(tmp_path)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(
            MODULE.BrowserInputError,
            match="another browser-input preparation is already running",
        ):
            MODULE.prepare_browser_input(
                _request(root),
                private_root=root,
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    assert not MODULE.canonical_paths(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
        ),
        private_root=root,
    ).output.exists()


def test_login_pair_rotation_during_source_read_cannot_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    username = _private_file(root / "directory-login/username", "directory-old")
    password = _private_file(root / "directory-login/password", "secret-old")
    original_read = MODULE.PRIVATE_INPUT.read_private_bytes
    rotated = False

    def rotating_read(path: Path, *args, **kwargs) -> bytes:
        nonlocal rotated
        content = original_read(path, *args, **kwargs)
        if path == username and not rotated:
            rotated = True
            username.write_text("directory-new", encoding="utf-8")
            password.write_text("secret-new", encoding="utf-8")
        return content

    monkeypatch.setattr(MODULE.PRIVATE_INPUT, "read_private_bytes", rotating_read)

    with pytest.raises(
        MODULE.BrowserInputError,
        match="credential source set changed before publication",
    ):
        MODULE.prepare_browser_input(
            _request(
                root,
                login_mode="files",
                username=username,
                password=password,
            ),
            private_root=root,
        )

    assert not MODULE.canonical_paths(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
        ),
        private_root=root,
    ).output.exists()


def test_existing_input_is_write_once_and_drift_is_rejected(tmp_path: Path) -> None:
    root = _private_root(tmp_path)
    output = MODULE.prepare_browser_input(
        _request(root),
        private_root=root,
    )
    original = output.read_bytes()

    assert (
        MODULE.prepare_browser_input(
            _request(root),
            private_root=root,
        )
        == output
    )
    paths = MODULE.canonical_paths(
        expected_commit=COMMIT,
        deployment_run_id=RUN_ID,
        identity_artifacts_directory=(
            root / "install-secrets/rke2/identity-artifacts"
        ),
        private_root=root,
    )
    paths.break_glass_password.write_text("replacement-secret", encoding="utf-8")

    with pytest.raises(MODULE.BrowserInputError):
        MODULE.prepare_browser_input(
            _request(root),
            private_root=root,
        )
    assert output.read_bytes() == original


def test_invalid_commit_and_run_identity_are_rejected(tmp_path: Path) -> None:
    root = _private_root(tmp_path)

    with pytest.raises(MODULE.BrowserInputError):
        MODULE.canonical_paths(
            expected_commit="short",
            deployment_run_id=RUN_ID,
            identity_artifacts_directory=(
                root / "install-secrets/rke2/identity-artifacts"
            ),
            private_root=root,
        )
    with pytest.raises(MODULE.BrowserInputError):
        MODULE.canonical_paths(
            expected_commit=COMMIT,
            deployment_run_id="run-invalid/escape",
            identity_artifacts_directory=(
                root / "install-secrets/rke2/identity-artifacts"
            ),
            private_root=root,
        )


def test_cli_exposes_only_identity_and_private_login_inputs() -> None:
    options = {
        option
        for action in MODULE.build_parser()._actions
        for option in action.option_strings
    }

    assert options == {
        "-h",
        "--help",
        "--expected-commit",
        "--deployment-run-id",
        "--authentication-mode",
        "--login-mode",
        "--login-username-file",
        "--login-password-file",
        "--identity-artifacts-directory",
        "--username-selector",
        "--password-selector",
        "--submit-selector",
        "--error-selector",
    }
    assert "--output" not in options
    assert "--admin-password-file" not in options
    assert "--break-glass-password-file" not in options
