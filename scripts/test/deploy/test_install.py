"""Top-level RKE2 installation orchestration contract tests."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "install.py"
SPEC = importlib.util.spec_from_file_location("rke2_install", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
IMAGE_CONTRACT = json.loads(
    (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
)
COMMIT = "a" * 40
ACCEPTANCE_KEY = bytes(range(32))
ACCEPTANCE_SECRET_UID = "22222222-2222-4222-8222-222222222222"
HARBOR_DOCKERCONFIG = b'{"auths":{"harbor.example.test":{"auth":"dXNlcjpwYXNz"}}}'


def test_cli_and_installer_do_not_accept_private_state_selection() -> None:
    completed = subprocess.run(
        ["python3", str(MODULE_PATH), "--help"],
        capture_output=True,
        check=True,
        text=True,
    )

    assert "--private-root" not in completed.stdout
    assert "--secret-store" not in completed.stdout
    assert "private_root" not in MODULE.install_rke2.__annotations__
    assert "secret_store" not in MODULE.install_rke2.__annotations__


def test_cli_direct_script_fallback_runs_outside_checkout(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        ["python3", str(MODULE_PATH), "--help"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "{validate,prepare-cluster,apply}" in completed.stdout


def test_cli_exposes_only_three_phases_and_rejects_legacy_dry_run() -> None:
    help_result = subprocess.run(
        ["python3", str(MODULE_PATH), "--help"],
        capture_output=True,
        check=True,
        text=True,
    )

    assert "{validate,prepare-cluster,apply}" in help_result.stdout
    assert "--dry-run" not in help_result.stdout
    for phase in ("validate", "prepare-cluster", "apply"):
        phase_help = subprocess.run(
            ["python3", str(MODULE_PATH), phase, "--help"],
            capture_output=True,
            check=True,
            text=True,
        )
        assert "--dry-run" not in phase_help.stdout
        assert "--execution-profile" in phase_help.stdout

    rejected = subprocess.run(
        [
            "python3",
            str(MODULE_PATH),
            "validate",
            "--commit",
            COMMIT,
            "--context",
            "rke",
            "--identity-mode",
            "externalOidc",
            "--inventory",
            "/private/inventory",
            "--execution-profile",
            "/private/backend-execution-profile.json",
            "--work-directory",
            "/private/work",
            "--kubeconfig",
            "/private/kubeconfig",
            "--registry",
            "harbor.example.test",
            "--project",
            "library",
            "--platform-url",
            "https://platform.example.test",
            "--harbor-dockerconfig",
            "/private/dockerconfig",
            "--apps-tls-cert",
            "/private/apps.crt",
            "--apps-tls-key",
            "/private/apps.key",
            "--apps-tls-ca",
            "/private/apps-ca.crt",
            "--oidc-ca",
            "/private/oidc-ca.crt",
            "--turn-url",
            "turn:turn.example.test:3478",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert rejected.returncode == 2
    assert "unrecognized arguments: --dry-run" in rejected.stderr


def test_platform_url_is_required_by_install_and_preparation_public_seams(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "bundledKeycloak")
    inputs["platform_url"] = "https://custom-platform.example.test"
    runner = FakeRunner()

    MODULE.install_rke2(**inputs, runner=runner)

    assert "platform_url" in MODULE.install_rke2.__annotations__
    assert "platform_url" in (
        MODULE.INSTALLATION_PREPARATION.InstallationPreparationRequest._fields
    )
    generator = next(
        command
        for command in _commands(runner)
        if "identity-installation/generate_secrets.py" in command
    )
    assert "--platform-origin https://custom-platform.example.test" in generator
    assert (
        "--platform-admin-subject " "00000000-0000-4000-8000-000000000001"
    ) in generator
    assert "--homelab-insecure-defaults" in generator

    invalid_root = tmp_path / "invalid"
    invalid_root.mkdir()
    invalid = _inputs(invalid_root, "externalOidc")
    invalid["platform_url"] = "https://platform..example.test"
    with pytest.raises(MODULE.InstallationError, match="platform URL"):
        MODULE.install_rke2(**invalid, runner=FakeRunner())


@pytest.mark.parametrize(
    "phase",
    (
        MODULE.InstallationPhase.VALIDATE,
        MODULE.InstallationPhase.PREPARE_CLUSTER,
    ),
)
def test_non_apply_phase_validates_without_publishing_backend_profile(
    tmp_path: Path,
    phase: MODULE.InstallationPhase,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=phase)
    fixed_profile = MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE

    MODULE.install_rke2(
        **inputs,
        confirm_create_namespaces=(phase is MODULE.InstallationPhase.PREPARE_CLUSTER),
        runner=FakeRunner(),
    )

    assert not fixed_profile.exists()


def test_apply_write_once_publishes_exact_backend_profile(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    source = inputs["execution_profile"]
    fixed_profile = MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE

    MODULE.install_rke2(**inputs, runner=FakeRunner())

    assert fixed_profile.read_bytes() == source.read_bytes()
    assert stat.S_IMODE(fixed_profile.stat().st_mode) == 0o600
    MODULE.install_rke2(**inputs, runner=FakeRunner())
    assert fixed_profile.read_bytes() == source.read_bytes()


def test_installer_rejects_backend_profile_drift_without_overwrite(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    fixed_profile = MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE
    _private_directory(fixed_profile.parent)
    _execution_profile(fixed_profile)
    installed = json.loads(fixed_profile.read_text(encoding="utf-8"))
    installed["localPathNodes"][0]["mountRoots"] = ["/different-root"]
    fixed_profile.write_text(
        json.dumps(installed, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fixed_profile.chmod(0o600)
    original = fixed_profile.read_bytes()

    with pytest.raises(
        MODULE.InstallationError,
        match="installed backend execution profile changed",
    ):
        MODULE.install_rke2(**inputs, runner=FakeRunner())

    assert fixed_profile.read_bytes() == original


@pytest.mark.parametrize(
    ("primary_exit_code", "expected"),
    [(23, 23), (126, 70), (128 + signal.SIGTERM, 70)],
)
def test_cli_preserves_safe_primary_exit_code_instead_of_parser_exit_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    primary_exit_code: int,
    expected: int,
) -> None:
    primary = (
        MODULE.InstallationInterrupted(signal.SIGTERM)
        if primary_exit_code == 128 + signal.SIGTERM
        else MODULE.InstallationCommandError(
            command_identity="deploy.sh",
            exit_code=primary_exit_code,
        )
    )
    failure = MODULE.InstallationRecoveryError(
        stage="core deployment",
        primary_cause=primary,
        core_rollback_cause=MODULE.InstallationError("rollback failed"),
        identity_recovery_skipped=True,
    )

    def fail_install(**_: object) -> None:
        raise failure

    monkeypatch.setattr(MODULE, "install_rke2", fail_install)
    monkeypatch.setattr(
        MODULE.sys,
        "argv",
        [
            "install.py",
            "apply",
            "--commit",
            COMMIT,
            "--context",
            "rke",
            "--identity-mode",
            "externalOidc",
            "--inventory",
            "/private/inventory",
            "--execution-profile",
            "/private/backend-execution-profile.json",
            "--work-directory",
            "/private/work",
            "--kubeconfig",
            "/private/kubeconfig",
            "--registry",
            "harbor.example.test",
            "--project",
            "library",
            "--platform-url",
            "https://platform.example.test",
            "--harbor-dockerconfig",
            "/private/dockerconfig",
            "--apps-tls-cert",
            "/private/apps.crt",
            "--apps-tls-key",
            "/private/apps.key",
            "--apps-tls-ca",
            "/private/apps-ca.crt",
            "--oidc-ca",
            "/private/oidc-ca.crt",
            "--turn-url",
            "turn:turn.example.test:3478",
            "--external-oidc-client-secret",
            "/private/oidc-client-secret",
            "--external-oidc-issuer-url",
            "https://auth.example.test/o/aileron/",
            "--external-oidc-client-id",
            "aileron",
        ],
    )

    assert MODULE.main() == expected
    captured = capsys.readouterr()
    assert "parser.error" not in captured.err
    assert "private stderr" not in captured.err


def test_missing_yaml_runtime_stops_before_any_installation_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_find_spec = MODULE.INSTALLATION_PREPARATION.importlib.util.find_spec
    monkeypatch.setattr(
        MODULE.INSTALLATION_PREPARATION.importlib.util,
        "find_spec",
        lambda name: None if name == "yaml" else real_find_spec(name),
    )
    runner = FakeRunner()

    with pytest.raises(MODULE.InstallationError, match="PyYAML==6.0.2"):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)

    assert runner.calls == []


def test_top_level_installer_rejects_concurrent_process_without_waiting(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    private_root = MODULE.INSTALLATION_STATE.PRIVATE_ROOT
    lock_holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, os, sys\n"
                "fd = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)\n"
                "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                "print('locked', flush=True)\n"
                "sys.stdin.readline()\n"
                "fcntl.flock(fd, fcntl.LOCK_UN)\n"
                "os.close(fd)\n"
            ),
            str(private_root),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert lock_holder.stdout is not None
    assert lock_holder.stdout.readline().strip() == "locked"
    runner = FakeRunner()
    try:
        with pytest.raises(MODULE.InstallationError, match="already running"):
            MODULE.install_rke2(**inputs, runner=runner)
    finally:
        assert lock_holder.stdin is not None
        lock_holder.stdin.write("\n")
        lock_holder.stdin.flush()
        _, stderr = lock_holder.communicate(timeout=5)

    assert lock_holder.returncode == 0, stderr
    assert runner.calls == []
    assert not (private_root / "installation.lock").exists()


@pytest.mark.parametrize("failure", ["mode", "symlink"])
def test_top_level_installer_rejects_insecure_private_root_lock_target(
    tmp_path: Path,
    failure: str,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    private_root = MODULE.INSTALLATION_STATE.PRIVATE_ROOT
    if failure == "mode":
        private_root.chmod(0o755)
    else:
        target = tmp_path / "real-private"
        private_root.rename(target)
        private_root.symlink_to(target, target_is_directory=True)
        MODULE.INSTALLATION_STATE.SECRET_STORE = target / "install-secrets/rke2"
    runner = FakeRunner()

    with pytest.raises(MODULE.InstallationError):
        MODULE.install_rke2(**inputs, runner=runner)

    assert runner.calls == []


def test_interrupted_real_command_quiesces_grandchild_before_recovery_can_start(
    tmp_path: Path,
) -> None:
    direct_pid_path = tmp_path / "direct.pid"
    grandchild_pid_path = tmp_path / "grandchild.pid"
    marker_path = tmp_path / "side-effect.log"
    grandchild = tmp_path / "grandchild.py"
    grandchild.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import signal\n"
        "import sys\n"
        "import time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "while True:\n"
        "    with Path(sys.argv[2]).open('a', encoding='utf-8') as stream:\n"
        "        stream.write('tick\\n')\n"
        "    time.sleep(0.01)\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "spawn-tree.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "child_pid=''\n"
        "terminate() {\n"
        '    if [ -n "${child_pid}" ]; then\n'
        '        kill -KILL "${child_pid}" 2>/dev/null || true\n'
        '        wait "${child_pid}" 2>/dev/null || true\n'
        "    fi\n"
        "    exit 143\n"
        "}\n"
        "trap terminate HUP INT TERM\n"
        'printf \'%s\\n\' "$$" > "$1"\n'
        'python3 "$2" "$3" "$4" &\n'
        "child_pid=$!\n"
        'wait "${child_pid}"\n',
        encoding="utf-8",
    )
    trigger_errors: list[str] = []

    def interrupt_parent() -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if direct_pid_path.exists() and grandchild_pid_path.exists():
                os.kill(os.getpid(), signal.SIGTERM)
                return
            time.sleep(0.01)
        trigger_errors.append("process tree did not start")

    trigger = threading.Thread(target=interrupt_parent)
    trigger.start()
    with pytest.raises(MODULE.InstallationInterrupted) as caught:
        with MODULE._installation_signal_boundary():
            MODULE._run_command(
                [
                    "sh",
                    str(wrapper),
                    str(direct_pid_path),
                    str(grandchild),
                    str(grandchild_pid_path),
                    str(marker_path),
                ]
            )
    trigger.join(timeout=5)

    assert caught.value.signal_number == signal.SIGTERM
    assert trigger.is_alive() is False
    assert trigger_errors == []
    direct_pid = int(direct_pid_path.read_text(encoding="utf-8"))
    grandchild_pid = int(grandchild_pid_path.read_text(encoding="utf-8"))
    for process_id in (direct_pid, grandchild_pid):
        with pytest.raises(ProcessLookupError):
            os.kill(process_id, 0)
    size_when_recovery_can_start = marker_path.stat().st_size
    time.sleep(0.15)
    assert marker_path.stat().st_size == size_when_recovery_can_start


def test_repeated_signal_during_real_command_quiesce_cannot_bypass_reaping(
    tmp_path: Path,
) -> None:
    direct_pid_path = tmp_path / "direct.pid"
    grandchild_pid_path = tmp_path / "grandchild.pid"
    marker_path = tmp_path / "side-effect.log"
    quiesce_started_path = tmp_path / "quiesce-started"
    grandchild = tmp_path / "grandchild.py"
    grandchild.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import signal\n"
        "import sys\n"
        "import time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "while True:\n"
        "    with Path(sys.argv[2]).open('a', encoding='utf-8') as stream:\n"
        "        stream.write('tick\\n')\n"
        "    time.sleep(0.01)\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "spawn-tree.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "child_pid=''\n"
        'quiesce_started="$5"\n'
        "terminate() {\n"
        "    printf 'quiescing\\n' > \"${quiesce_started}\"\n"
        "    sleep 0.25\n"
        '    if [ -n "${child_pid}" ]; then\n'
        '        kill -KILL "${child_pid}" 2>/dev/null || true\n'
        '        wait "${child_pid}" 2>/dev/null || true\n'
        "    fi\n"
        "    exit 143\n"
        "}\n"
        "trap terminate HUP INT TERM\n"
        'printf \'%s\\n\' "$$" > "$1"\n'
        'python3 "$2" "$3" "$4" &\n'
        "child_pid=$!\n"
        'wait "${child_pid}"\n',
        encoding="utf-8",
    )
    trigger_errors: list[str] = []

    def interrupt_parent_twice() -> None:
        startup_deadline = time.monotonic() + 5
        while time.monotonic() < startup_deadline:
            if direct_pid_path.exists() and grandchild_pid_path.exists():
                os.kill(os.getpid(), signal.SIGTERM)
                break
            time.sleep(0.01)
        else:
            trigger_errors.append("process tree did not start")
            return
        quiesce_deadline = time.monotonic() + 5
        while time.monotonic() < quiesce_deadline:
            if quiesce_started_path.exists():
                os.kill(os.getpid(), signal.SIGINT)
                return
            time.sleep(0.01)
        trigger_errors.append("process tree did not begin quiescing")

    trigger = threading.Thread(target=interrupt_parent_twice)
    trigger.start()
    with pytest.raises(MODULE.InstallationInterrupted) as caught:
        with MODULE._installation_signal_boundary():
            MODULE._run_command(
                [
                    "sh",
                    str(wrapper),
                    str(direct_pid_path),
                    str(grandchild),
                    str(grandchild_pid_path),
                    str(marker_path),
                    str(quiesce_started_path),
                ]
            )
    trigger.join(timeout=5)

    assert caught.value.signal_number == signal.SIGTERM
    assert trigger.is_alive() is False
    assert trigger_errors == []
    direct_pid = int(direct_pid_path.read_text(encoding="utf-8"))
    grandchild_pid = int(grandchild_pid_path.read_text(encoding="utf-8"))
    for process_id in (direct_pid, grandchild_pid):
        with pytest.raises(ProcessLookupError):
            os.kill(process_id, 0)
    size_when_recovery_can_start = marker_path.stat().st_size
    time.sleep(0.15)
    assert marker_path.stat().st_size == size_when_recovery_can_start


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


def _private(path: Path, value: str = "fixture-value") -> Path:
    _private_directory(path.parent)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _inventory(path: Path, commit: str = COMMIT) -> Path:
    rows = []
    for index, component in enumerate(IMAGE_CONTRACT["publishedComponents"]):
        repository = f"harbor.example.test/library/{component}"
        rows.append(
            f"{component}\t{commit}\tlinux/amd64\t{repository}:git-{commit}"
            f"\t{repository}@sha256:{index + 1:064x}"
            f"\t{repository}@sha256:{index + 101:064x}\n"
        )
    return _private(path, "".join(rows))


def _published_images(commit: str = COMMIT) -> list[dict[str, str]]:
    return [
        {
            "component": component,
            "revision": commit,
            "platform": "linux/amd64",
            "taggedImage": (f"harbor.example.test/library/{component}:git-{commit}"),
            "immutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 1:064x}"
            ),
            "runtimeImmutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 101:064x}"
            ),
        }
        for index, component in enumerate(IMAGE_CONTRACT["publishedComponents"])
    ]


def _kubeconfig(path: Path, *, context: str = "rke") -> Path:
    return _private(
        path,
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": context,
                "clusters": [
                    {
                        "name": context,
                        "cluster": {
                            "server": "https://192.0.2.10:6443",
                            "certificate-authority-data": "Y2E=",
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": context,
                        "context": {"cluster": context, "user": context},
                    }
                ],
                "users": [
                    {
                        "name": context,
                        "user": {
                            "client-certificate-data": "Y2VydA==",
                            "client-key-data": "a2V5",
                        },
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def _execution_profile(path: Path) -> Path:
    return _private(
        path,
        json.dumps(
            {
                "schemaVersion": "aileron-backend-execution-profile/v1",
                "executionNamespace": "aileron-backend-attestor-system",
                "namespaceOwner": "aileron-installer",
                "imagePullSecret": "harbor-rke-creds",
                "nfsMountRoots": [],
                "localPathNodes": [
                    {
                        "hostname": "rke2-worker-1",
                        "nodeUid": "node-uid-1",
                        "mountRoots": ["/var/lib/aileron"],
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
    )


def _secret_document(namespace: str, name: str, value: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "namespace": namespace,
            "name": name,
            "resourceVersion": "17",
            "uid": "11111111-1111-4111-8111-111111111111",
        },
        "type": "Opaque",
        "data": {"private": value},
    }


def _inputs(
    tmp_path: Path,
    mode: str,
    *,
    phase: MODULE.InstallationPhase = MODULE.InstallationPhase.APPLY,
    commit: str = COMMIT,
) -> dict:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700, exist_ok=True)
    work = private_root / "install" / commit
    work.parent.mkdir(mode=0o700, exist_ok=True)
    work.parent.chmod(0o700)
    work.mkdir(mode=0o700)
    secret_store = _private_directory(private_root / "install-secrets/rke2")
    MODULE.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.INSTALLATION_STATE.SECRET_STORE = secret_store
    MODULE.INSTALLATION_STATE.BACKEND_ATTESTOR_PROFILE = (
        private_root / "backend-attestor/execution-profile.json"
    )
    inputs = {
        "expected_commit": commit,
        "context": "rke",
        "identity_mode": mode,
        "inventory_path": _inventory(private_root / f"images-{commit}.tsv", commit),
        "execution_profile": _execution_profile(
            private_root / "inputs/backend-execution-profile.json"
        ),
        "work_directory": work,
        "kubeconfig": _kubeconfig(private_root / "kubeconfig"),
        "registry": "harbor.example.test",
        "project": "library",
        "platform_url": "https://platform.example.test",
        "harbor_dockerconfig": _private(
            private_root / "dockerconfig.json", HARBOR_DOCKERCONFIG.decode()
        ),
        "apps_tls_cert": _private(
            private_root / "apps.crt",
            "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
        ),
        "apps_tls_key": _private(
            private_root / "apps.key",
            "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
        ),
        "apps_tls_ca": _private(
            private_root / "apps-ca.crt",
            "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
        ),
        "oidc_ca": _private(
            private_root / "oidc-ca.crt",
            "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
        ),
        "turn_url": "turn:turn.apps.example.test:3478",
        "phase": phase,
    }
    if mode == "bundledKeycloak":
        inputs.update(
            {
                "identity_tls_cert": _private(
                    private_root / "identity.crt",
                    "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
                ),
                "identity_tls_key": _private(
                    private_root / "identity.key",
                    "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
                ),
                "external_oidc_client_secret": None,
                "external_oidc_issuer_url": None,
                "external_oidc_client_id": None,
            }
        )
    else:
        inputs.update(
            {
                "identity_tls_cert": None,
                "identity_tls_key": None,
                "external_oidc_client_secret": _private(
                    private_root / "external-client-secret"
                ),
                "external_oidc_issuer_url": "https://auth.example.test/o/aileron/",
                "external_oidc_client_id": "external-client",
            }
        )
    identity = MODULE.INSTALLATION_STATE.installation_identity_document(
        installation_id="44444444-4444-4444-8444-444444444444",
        identity_mode=mode,
        issuer_url=(
            MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL
            if mode == "bundledKeycloak"
            else inputs["external_oidc_issuer_url"]
        ),
        client_id=(
            MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID
            if mode == "bundledKeycloak"
            else inputs["external_oidc_client_id"]
        ),
        cluster_uid="11111111-1111-4111-8111-111111111111",
    )
    identity_path = _private(
        secret_store / "installation-identity.json",
        json.dumps(identity, indent=2, sort_keys=True) + "\n",
    )
    key_path = secret_store / "acceptance-hmac.key"
    key_path.write_bytes(ACCEPTANCE_KEY)
    key_path.chmod(0o600)
    identity_digest = hashlib.sha256(identity_path.read_bytes()).hexdigest()
    _private(
        secret_store / "acceptance-trust-anchor.json",
        json.dumps(
            MODULE.INSTALLATION_STATE.acceptance_anchor_document(
                cluster_uid="11111111-1111-4111-8111-111111111111",
                identity_digest=identity_digest,
                key_digest=hashlib.sha256(ACCEPTANCE_KEY).hexdigest(),
                secret_uid=ACCEPTANCE_SECRET_UID,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT = private_root
    MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE = secret_store
    MODULE.INSTALLATION_PREPARATION.ACCEPTANCE_RELEASE.write_signed_image_inventory(
        path=work / "signed-image-inventory.json",
        private_root=private_root,
        images=_published_images(commit),
        key=ACCEPTANCE_KEY,
        context="rke",
        commit=commit,
        cluster_uid="11111111-1111-4111-8111-111111111111",
        installation_identity_sha256=identity_digest,
    )
    return inputs


class FakeRunner:
    def __init__(
        self,
        *,
        previous_identity_revision: int | None = None,
        fail_core_preflight: bool = False,
        core_failure_command: list[str] | None = None,
        core_failure_exit_code: int = 23,
        rollback_failure_command: list[str] | None = None,
        fail_identity_upgrade: bool = False,
        core_rollback_succeeded: bool = True,
        fail_secret_apply_stage: str | None = None,
        fail_secret_restore_for: tuple[str, str] | None = None,
        recreate_secret_for: tuple[str, str] | None = None,
        interrupt_signal: int | None = None,
        process_quiescence_failure: bool = False,
        dirty: bool = False,
        head_commit: str = COMMIT,
        cluster_uid: str = "11111111-1111-4111-8111-111111111111",
        namespaces_ready: bool = True,
        namespace_prepare_failure: str | None = None,
        replace_namespace_before_guard: bool = False,
        flattened_kubeconfig: str | None = None,
        terminating_namespace: str | None = None,
        acceptance_secret_drift: str | None = None,
        backend_prerequisite_state: str | None = None,
    ) -> None:
        self.fail_core_preflight = fail_core_preflight
        self.core_failure_command = core_failure_command
        self.core_failure_exit_code = core_failure_exit_code
        self.rollback_failure_command = rollback_failure_command
        self.fail_identity_upgrade = fail_identity_upgrade
        self.core_rollback_succeeded = core_rollback_succeeded
        self.fail_secret_apply_stage = fail_secret_apply_stage
        self.fail_secret_restore_for = fail_secret_restore_for
        self.recreate_secret_for = recreate_secret_for
        self.interrupt_signal = interrupt_signal
        self.process_quiescence_failure = process_quiescence_failure
        self.dirty = dirty
        self.head_commit = head_commit
        self.cluster_uid = cluster_uid
        self.namespaces_ready = namespaces_ready
        self.namespace_prepare_failure = namespace_prepare_failure
        self.replace_namespace_before_guard = replace_namespace_before_guard
        self.flattened_kubeconfig = flattened_kubeconfig
        self.terminating_namespace = terminating_namespace
        self.acceptance_secret_drift = acceptance_secret_drift
        self.backend_prerequisite_state = backend_prerequisite_state
        self.acceptance_secret_reads = 0
        self.backend_namespace_reads = 0
        self.namespace_created: list[str] = []
        self.namespace_uids: dict[str, str] = {}
        self.namespace_phase_calls = 0
        self.calls: list[tuple[list[str], dict[str, str], Path | None]] = []
        self.generator_owners: list[set[int]] = []
        self.generator_input_owners: list[int] = []
        self.identity_revision = previous_identity_revision
        self.identity_status = (
            "deployed" if previous_identity_revision is not None else None
        )
        self.identity_history = (
            [
                {
                    "revision": str(previous_identity_revision),
                    "status": "deployed",
                }
            ]
            if previous_identity_revision is not None
            else []
        )
        self.secrets: dict[tuple[str, str], dict] = {}

    def __call__(
        self,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        stdout_path: Path | None = None,
    ) -> str:
        self.calls.append((command, environment or {}, stdout_path))
        joined = " ".join(command)
        if command[-2:] == ["status", "--porcelain"]:
            return "M dirty\n" if self.dirty else ""
        if command[-3:] == ["rev-parse", "--verify", "HEAD"]:
            return f"{self.head_commit}\n"
        if command[0] == "kubectl" and command[-6:] == [
            "config",
            "view",
            "--raw",
            "--flatten",
            "--minify",
            "--output=json",
        ]:
            raw_snapshot = Path(command[command.index("--kubeconfig") + 1])
            return self.flattened_kubeconfig or raw_snapshot.read_text(encoding="utf-8")
        if command[0] == "kubectl" and command[-2:] == [
            "config",
            "current-context",
        ]:
            return command[command.index("--context") + 1]
        if command[0] == "python3" and command[1].endswith(
            "ensure_installation_namespaces.py"
        ):
            if self.terminating_namespace is not None:
                raise MODULE.InstallationCommandError(
                    command_identity="ensure_installation_namespaces.py",
                    exit_code=65,
                )
            identity_mode = command[command.index("--identity-mode") + 1]
            targets = [
                "workspace-system",
                "aileron-turn-system",
                "aileron-backend-attestor-system",
            ]
            if identity_mode == "bundledKeycloak":
                targets.append("aileron-identity-system")
            validate_only = "--validate-only" in command
            self.namespace_phase_calls += 1
            if (
                self.namespace_phase_calls > 1
                and self.acceptance_secret_drift == "rebound"
            ):
                anchor_path = (
                    MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE
                    / "acceptance-trust-anchor.json"
                )
                anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
                anchor["secretUid"] = "33333333-3333-4333-8333-333333333333"
                anchor_path.write_text(
                    json.dumps(anchor, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                anchor_path.chmod(0o600)
            if self.namespaces_ready and not self.namespace_uids:
                self.namespace_uids = {target: f"uid-{target}" for target in targets}
            if (
                validate_only
                and self.replace_namespace_before_guard
                and self.namespace_phase_calls > 1
            ):
                self.namespace_uids[targets[0]] = f"replacement-{targets[0]}"
            initially_missing = [
                target for target in targets if target not in self.namespace_uids
            ]
            changed = []
            if not validate_only:
                if self.namespace_prepare_failure == "signal":
                    self.namespace_created.append(targets[0])
                    raise MODULE.InstallationInterrupted(signal.SIGTERM)
                if self.namespace_prepare_failure == "reverify-drift":
                    self.namespace_created.extend(targets)
                    raise MODULE.InstallationCommandError(
                        command_identity="ensure_installation_namespaces.py",
                        exit_code=65,
                    )
                changed = list(initially_missing)
                self.namespace_created.extend(initially_missing)
                self.namespace_uids.update(
                    {target: f"uid-{target}" for target in initially_missing}
                )
                self.namespaces_ready = True
            return json.dumps(
                {
                    "schemaVersion": "aileron-installation-namespace-result/v2",
                    "mode": "validate" if validate_only else "prepare",
                    "ready": not initially_missing if validate_only else True,
                    "targetNamespaces": targets,
                    "targetNamespaceIdentities": [
                        {"name": target, "uid": self.namespace_uids[target]}
                        for target in targets
                        if target in self.namespace_uids
                    ],
                    "initiallyMissingNamespaces": initially_missing,
                    "changedNamespaces": changed,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        if (
            command[0] == "kubectl"
            and "get" in command
            and "namespace" in command
            and MODULE.BACKEND_PREPARER.NAMESPACE in command
        ):
            self.backend_namespace_reads += 1
            if self.backend_prerequisite_state == "missing":
                return ""
            uid = (
                "replacement-backend-namespace-uid"
                if self.backend_prerequisite_state == "replaced"
                and self.backend_namespace_reads > 2
                else "backend-namespace-uid"
            )
            labels = {
                MODULE.BACKEND_PREPARER.NAMESPACE_OWNER_LABEL: (
                    MODULE.BACKEND_PREPARER.NAMESPACE_OWNER
                ),
                **MODULE.BACKEND_PREPARER.PSA_LABELS,
            }
            if self.backend_prerequisite_state == "drifted":
                labels["pod-security.kubernetes.io/enforce"] = "restricted"
            return json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {
                        "name": MODULE.BACKEND_PREPARER.NAMESPACE,
                        "uid": uid,
                        "resourceVersion": "17",
                        "labels": labels,
                    },
                    "status": {"phase": "Active"},
                }
            )
        if (
            command[0] == "kubectl"
            and "get" in command
            and "secret" in command
            and MODULE.BACKEND_PREPARER.SECRET_NAME in command
            and "--ignore-not-found" in command
            and stdout_path is None
        ):
            if self.backend_prerequisite_state == "missing":
                return ""
            return json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {
                        "namespace": MODULE.BACKEND_PREPARER.NAMESPACE,
                        "name": MODULE.BACKEND_PREPARER.SECRET_NAME,
                        "uid": "backend-pull-secret-uid",
                        "resourceVersion": "23",
                        "labels": {
                            MODULE.BACKEND_PREPARER.SECRET_OWNER_LABEL: (
                                MODULE.BACKEND_PREPARER.NAMESPACE_OWNER
                            )
                        },
                    },
                    "type": "kubernetes.io/dockerconfigjson",
                    "data": {
                        ".dockerconfigjson": base64.b64encode(
                            HARBOR_DOCKERCONFIG
                        ).decode()
                    },
                }
            )
        if (
            command[0] == "kubectl"
            and "get" in command
            and "namespace" in command
            and "--output=json" in command
        ):
            namespace = command[command.index("namespace") + 1]
            if namespace in self.namespace_uids:
                return json.dumps(
                    {
                        "apiVersion": "v1",
                        "kind": "Namespace",
                        "metadata": {
                            "name": namespace,
                            "uid": self.namespace_uids[namespace],
                            "resourceVersion": "17",
                            "labels": MODULE.INSTALLATION_TRANSACTION.NAMESPACE_CONTRACT.profile_labels(
                                namespace
                            ),
                        },
                        "status": {"phase": "Active"},
                    }
                )
        if (
            command[0] == "kubectl"
            and "get" in command
            and "namespace" in command
            and "aileron-acceptance-system" in command
        ):
            return json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {
                        "name": "aileron-acceptance-system",
                        "uid": "44444444-4444-4444-8444-444444444444",
                        "resourceVersion": "17",
                        "labels": MODULE.INSTALLATION_TRANSACTION.NAMESPACE_CONTRACT.profile_labels(
                            "aileron-acceptance-system"
                        ),
                    },
                    "status": {"phase": "Active"},
                }
            )
        if (
            command[0] == "kubectl"
            and "get" in command
            and "secret" in command
            and "aileron-acceptance-signing" in command
        ):
            self.acceptance_secret_reads += 1
            if (
                self.acceptance_secret_reads > 1
                and self.acceptance_secret_drift == "deleted"
            ):
                raise MODULE.InstallationCommandError(
                    command_identity="kubectl", exit_code=1
                )
            secret_store = MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE
            identity_digest = hashlib.sha256(
                (secret_store / "installation-identity.json").read_bytes()
            ).hexdigest()
            key = (secret_store / "acceptance-hmac.key").read_bytes()
            context = command[command.index("--context") + 1]
            return json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "immutable": True,
                    "metadata": {
                        "name": "aileron-acceptance-signing",
                        "namespace": "aileron-acceptance-system",
                        "resourceVersion": "19",
                        "uid": (
                            "33333333-3333-4333-8333-333333333333"
                            if self.acceptance_secret_reads > 1
                            and self.acceptance_secret_drift in {"replaced", "rebound"}
                            else ACCEPTANCE_SECRET_UID
                        ),
                        "labels": {
                            "platform.aileron.dev/secret-owner": ("aileron-installer"),
                            "platform.aileron.dev/cluster-uid": self.cluster_uid,
                        },
                        "annotations": {
                            "platform.aileron.dev/installation-identity-sha256": (
                                identity_digest
                            ),
                        },
                    },
                    "type": "Opaque",
                    "data": {"hmac-key": base64.b64encode(key).decode()},
                }
            )
        if not self.namespaces_ready and (
            (command[0] == "helm" and "--namespace" in command)
            or "identity-installation/apply_secrets.sh" in joined
            or "apply_platform_secrets.py" in joined
            or command[0].endswith("preflight.sh")
            or (
                command[0] == "kubectl"
                and "secret" in command
                and "kube-system" not in command
            )
        ):
            raise AssertionError(
                "namespace-scoped validation or mutation ran before namespace readiness"
            )
        if "namespace" in command and "kube-system" in command:
            return f"{self.cluster_uid}\n"
        if command[:2] == ["helm", "list"]:
            if self.identity_revision is None:
                return "[]"
            return json.dumps(
                [
                    {
                        "name": "aileron-identity",
                        "revision": str(self.identity_revision),
                        "status": self.identity_status,
                    }
                ]
            )
        if command[:3] == ["helm", "history", "aileron-identity"]:
            return json.dumps(self.identity_history)
        if (
            command[:4] == ["helm", "upgrade", "--install", "aileron-identity"]
            and "--dry-run=server" not in command
        ):
            prior = self.identity_revision
            if self.identity_history:
                self.identity_history[-1]["status"] = "superseded"
            self.identity_revision = 1 if prior is None else prior + 1
            self.identity_status = (
                "failed" if self.fail_identity_upgrade else "deployed"
            )
            self.identity_history.append(
                {
                    "revision": str(self.identity_revision),
                    "status": self.identity_status,
                }
            )
            if self.fail_identity_upgrade:
                raise MODULE.InstallationCommandError(
                    command_identity="helm", exit_code=42
                )
        if command[:3] == ["helm", "rollback", "aileron-identity"]:
            if self.rollback_failure_command is not None:
                MODULE._run_command(self.rollback_failure_command)
            self.identity_revision = (self.identity_revision or 0) + 1
            self.identity_status = "deployed"
            self.identity_history.append(
                {
                    "revision": str(self.identity_revision),
                    "status": "deployed",
                }
            )
            return ""
        if command[:3] == ["helm", "uninstall", "aileron-identity"]:
            if self.rollback_failure_command is not None:
                MODULE._run_command(self.rollback_failure_command)
            self.identity_revision = None
            self.identity_status = None
            return ""
        if (
            command[0] == "kubectl"
            and "get" in command
            and "secret" in command
            and "--ignore-not-found" in command
        ):
            namespace = command[command.index("--namespace") + 1]
            name = command[command.index("secret") + 1]
            document = self.secrets.get((namespace, name))
            assert stdout_path is not None
            stdout_path.write_text(
                "" if document is None else json.dumps(document), encoding="utf-8"
            )
            stdout_path.chmod(0o600)
            return ""
        if command[0] == "kubectl" and "delete" in command and "--raw" in command:
            namespace = command[command.index("--namespace") + 1]
            name = command[command.index("--raw") + 1].rsplit("/", 1)[-1]
            if self.fail_secret_restore_for == (namespace, name):
                raise MODULE.InstallationCommandError(
                    command_identity="kubectl", exit_code=53
                )
            options = json.loads(
                Path(command[command.index("--filename") + 1]).read_text(
                    encoding="utf-8"
                )
            )
            current = self.secrets.get((namespace, name))
            if current is None or options.get("preconditions") != {
                "uid": current["metadata"]["uid"],
                "resourceVersion": current["metadata"]["resourceVersion"],
            }:
                raise MODULE.InstallationCommandError(
                    command_identity="kubectl", exit_code=54
                )
            self.secrets.pop((namespace, name), None)
            return ""
        if (
            command[0] == "kubectl"
            and ("create" in command or "replace" in command)
            and "--filename" in command
        ):
            manifest = json.loads(
                Path(command[command.index("--filename") + 1]).read_text(
                    encoding="utf-8"
                )
            )
            metadata = manifest["metadata"]
            if self.fail_secret_restore_for == (
                metadata["namespace"],
                metadata["name"],
            ):
                raise MODULE.InstallationCommandError(
                    command_identity="kubectl", exit_code=53
                )
            key = (metadata["namespace"], metadata["name"])
            if "replace" in command:
                assert "--force" not in command
                current = self.secrets.get(key)
                if (
                    current is None
                    or metadata.get("resourceVersion")
                    != current["metadata"]["resourceVersion"]
                ):
                    raise MODULE.InstallationCommandError(
                        command_identity="kubectl", exit_code=54
                    )
                metadata["uid"] = current["metadata"]["uid"]
            else:
                metadata.setdefault("resourceVersion", "1")
                metadata.setdefault("uid", "22222222-2222-4222-8222-222222222222")
            self.secrets[key] = manifest
            return ""
        if "identity-installation/generate_secrets.py" in joined:
            output = Path(command[command.index("--output-dir") + 1])
            client_secret = output / "aileron-oidc-client/client-secret"
            if not client_secret.exists():
                _private(client_secret)
        if command[:2] == ["docker", "run"]:
            output_mount = next(
                value for value in command if value.endswith(":/output")
            )
            output = Path(output_mount.removesuffix(":/output"))
            self.generator_owners.append(
                {entry.stat().st_uid for entry in [output, *output.rglob("*")]}
            )
            values_mount = next(
                value
                for value in command
                if value.endswith(":/installation-contract/core-values.json:ro")
            )
            self.generator_input_owners.append(
                Path(values_mount.split(":", 1)[0]).stat().st_uid
            )
            marker = output / "simulated-container-artifact"
            marker.write_text("generated", encoding="utf-8")
            marker.chmod(0o600)
            uid, gid = (
                int(value) for value in command[command.index("--user") + 1].split(":")
            )
            os.chown(marker, uid, gid)
        if command[:2] == ["helm", "template"] and stdout_path is not None:
            stdout_path.write_text(
                "apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8"
            )
            stdout_path.chmod(0o600)
        if self.fail_core_preflight and command[0].endswith("preflight.sh"):
            raise MODULE.InstallationCommandError(
                command_identity="preflight.sh", exit_code=1
            )
        if (
            "identity-installation/apply_secrets.sh" in joined
            and "--dry-run" not in command
        ):
            transaction_directory = Path(
                command[command.index("--transaction-directory") + 1]
            )
            transaction_commit = command[command.index("--transaction-commit") + 1]
            context = command[command.index("--context") + 1]
            identity_transaction_environment = dict(environment or {})

            def identity_transaction_runner(
                transaction_command: list[str],
                *,
                environment: dict[str, str] | None = None,
                stdout_path: Path | None = None,
            ) -> str:
                del environment
                return self(
                    transaction_command,
                    environment=identity_transaction_environment,
                    stdout_path=stdout_path,
                )

            for (
                namespace,
                name,
            ) in MODULE.INSTALLATION_TRANSACTION.IDENTITY_SECRET_REFERENCES:
                document = _secret_document(namespace, name, "mutated")
                manifest = json.dumps(document).encode()
                mutation = MODULE.INSTALLATION_TRANSACTION.prepare_secret_mutation(
                    transaction_directory=transaction_directory,
                    commit=transaction_commit,
                    context=context,
                    identity_mode="bundledKeycloak",
                    namespace=namespace,
                    name=name,
                    expected_manifest=manifest,
                    runner=identity_transaction_runner,
                )
                applied = json.loads(
                    MODULE.INSTALLATION_TRANSACTION.render_secret_mutation_manifest(
                        expected_manifest=manifest,
                        namespace=namespace,
                        name=name,
                        transaction_marker=mutation["transactionMarker"],
                        uid=mutation.get("uid"),
                        resource_version=mutation.get("resourceVersion"),
                    )
                )
                applied["metadata"].setdefault("uid", document["metadata"]["uid"])
                applied["metadata"].setdefault(
                    "resourceVersion", document["metadata"]["resourceVersion"]
                )
                self.secrets[(namespace, name)] = applied
                MODULE.INSTALLATION_TRANSACTION.record_secret_post_state(
                    transaction_directory=transaction_directory,
                    commit=transaction_commit,
                    context=context,
                    identity_mode="bundledKeycloak",
                    namespace=namespace,
                    name=name,
                    expected_manifest=manifest,
                    runner=identity_transaction_runner,
                )
                if self.recreate_secret_for == (namespace, name):
                    applied["metadata"]["uid"] = "33333333-3333-4333-8333-333333333333"
                    applied["metadata"]["resourceVersion"] = "29"
            if self.fail_secret_apply_stage == "identity":
                raise MODULE.InstallationCommandError(
                    command_identity="apply_secrets.sh", exit_code=51
                )
        if "apply_platform_secrets.py" in joined and "--apply" in command:
            transaction_directory = Path(
                command[command.index("--transaction-directory") + 1]
            )
            transaction_commit = command[command.index("--transaction-commit") + 1]
            context = command[command.index("--context") + 1]
            identity_mode = command[command.index("--transaction-identity-mode") + 1]
            platform_transaction_environment = dict(environment or {})

            def platform_transaction_runner(
                transaction_command: list[str],
                *,
                environment: dict[str, str] | None = None,
                stdout_path: Path | None = None,
            ) -> str:
                del environment
                return self(
                    transaction_command,
                    environment=platform_transaction_environment,
                    stdout_path=stdout_path,
                )

            references = MODULE.INSTALLATION_TRANSACTION.secret_references(
                identity_mode="externalOidc"
            )
            for namespace, name in references:
                document = _secret_document(namespace, name, "mutated")
                manifest = json.dumps(document).encode()
                mutation = MODULE.INSTALLATION_TRANSACTION.prepare_secret_mutation(
                    transaction_directory=transaction_directory,
                    commit=transaction_commit,
                    context=context,
                    identity_mode=identity_mode,
                    namespace=namespace,
                    name=name,
                    expected_manifest=manifest,
                    runner=platform_transaction_runner,
                )
                applied = json.loads(
                    MODULE.INSTALLATION_TRANSACTION.render_secret_mutation_manifest(
                        expected_manifest=manifest,
                        namespace=namespace,
                        name=name,
                        transaction_marker=mutation["transactionMarker"],
                        uid=mutation.get("uid"),
                        resource_version=mutation.get("resourceVersion"),
                    )
                )
                applied["metadata"].setdefault("uid", document["metadata"]["uid"])
                applied["metadata"].setdefault(
                    "resourceVersion", document["metadata"]["resourceVersion"]
                )
                self.secrets[(namespace, name)] = applied
                MODULE.INSTALLATION_TRANSACTION.record_secret_post_state(
                    transaction_directory=transaction_directory,
                    commit=transaction_commit,
                    context=context,
                    identity_mode=identity_mode,
                    namespace=namespace,
                    name=name,
                    expected_manifest=manifest,
                    runner=platform_transaction_runner,
                )
                if self.recreate_secret_for == (namespace, name):
                    applied["metadata"]["uid"] = "33333333-3333-4333-8333-333333333333"
                    applied["metadata"]["resourceVersion"] = "29"
            if self.fail_secret_apply_stage == "platform":
                raise MODULE.InstallationCommandError(
                    command_identity="apply_platform_secrets.py", exit_code=52
                )
        if command[0].endswith("deploy.sh"):
            result_path = Path(command[command.index("--result-sidecar") + 1])
            if self.process_quiescence_failure:
                raise MODULE.InstallationProcessQuiescenceError(
                    MODULE.InstallationInterrupted(signal.SIGTERM)
                )
            if self.interrupt_signal is not None:
                MODULE.INSTALLATION_TRANSACTION.write_core_result(
                    path=result_path,
                    commit=self.head_commit,
                    primary_exit_code=128 + self.interrupt_signal,
                    core_rollback_attempted=True,
                    core_rollback_succeeded=True,
                )
                os.kill(os.getpid(), self.interrupt_signal)
                raise AssertionError("installation signal handler did not interrupt")
            if self.core_failure_command is not None:
                MODULE.INSTALLATION_TRANSACTION.write_core_result(
                    path=result_path,
                    commit=self.head_commit,
                    primary_exit_code=self.core_failure_exit_code,
                    core_rollback_attempted=True,
                    core_rollback_succeeded=self.core_rollback_succeeded,
                )
                MODULE._run_command(self.core_failure_command)
            MODULE.INSTALLATION_TRANSACTION.write_core_result(
                path=result_path,
                commit=self.head_commit,
                primary_exit_code=0,
                core_rollback_attempted=False,
                core_rollback_succeeded=False,
            )
        return ""


def _commands(runner: FakeRunner) -> list[str]:
    return [" ".join(command) for command, _, _ in runner.calls]


def _private_tree_snapshot(root: Path) -> list[tuple[str, str, int, bytes]]:
    snapshot: list[tuple[str, str, int, bytes]] = []
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else str(path.relative_to(root))
        if path.is_dir():
            snapshot.append((relative, "directory", path.stat().st_mode & 0o777, b""))
        else:
            snapshot.append(
                (relative, "file", path.stat().st_mode & 0o777, path.read_bytes())
            )
    return snapshot


def _recovery_result(inputs: dict) -> dict:
    transactions = list((inputs["work_directory"] / "transactions").iterdir())
    assert len(transactions) == 1
    result_path = transactions[0] / "install-recovery-result.json"
    assert result_path.stat().st_mode & 0o777 == 0o600
    return json.loads(result_path.read_text(encoding="utf-8"))


def _failing_core_command(tmp_path: Path, *, exit_code: int = 23) -> list[str]:
    command = tmp_path / "deploy.sh"
    command.write_text(
        f"#!/bin/sh\nprintf '%s\\n' 'private stderr value' >&2\nexit {exit_code}\n",
        encoding="utf-8",
    )
    command.chmod(0o700)
    return [
        str(command),
        "--client-secret",
        str(tmp_path / "private/client-secret"),
        "private-argument-value",
    ]


def _failing_rollback_command(tmp_path: Path, *, exit_code: int = 31) -> list[str]:
    command = tmp_path / "helm"
    command.write_text(
        f"#!/bin/sh\nprintf '%s\\n' 'private rollback stderr' >&2\nexit {exit_code}\n",
        encoding="utf-8",
    )
    command.chmod(0o700)
    return [command.as_posix(), "private-rollback-argument"]


def test_bundled_preflights_before_mutations_then_checks_identity_discovery(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "bundledKeycloak")
    runner = FakeRunner()
    MODULE.install_rke2(**inputs, runner=runner)
    commands = _commands(runner)

    identity_upgrade = next(
        index
        for index, command in enumerate(commands)
        if command.startswith("helm upgrade --install aileron-identity")
        and "--dry-run=server" not in command
    )
    readiness = next(
        index for index, command in enumerate(commands) if "wait_for_oidc.py" in command
    )
    platform_generator = next(
        index
        for index, command in enumerate(commands)
        if command.startswith("docker run")
    )
    core_preflight = next(
        index
        for index, command in enumerate(commands)
        if command.startswith(str(ROOT / "scripts/deploy/rke2/preflight.sh"))
    )
    identity_secret_apply = next(
        index
        for index, command in enumerate(commands)
        if "identity-installation/apply_secrets.sh" in command
        and "--dry-run" not in command
    )
    platform_secret_apply = next(
        index
        for index, command in enumerate(commands)
        if "apply_platform_secrets.py" in command and "--apply" in command
    )
    core_deploy = next(
        index
        for index, command in enumerate(commands)
        if command.startswith(str(ROOT / "scripts/deploy/rke2/deploy.sh"))
    )
    assert (
        platform_generator
        < core_preflight
        < identity_secret_apply
        < platform_secret_apply
        < identity_upgrade
        < readiness
        < core_deploy
    )

    secret_snapshot_queries = [
        index
        for index, (command, _, stdout_path) in enumerate(runner.calls)
        if command[0] == "kubectl"
        and "get" in command
        and "secret" in command
        and "--ignore-not-found" in command
        and stdout_path is not None
        and stdout_path.parent.name == "secrets"
    ]
    assert secret_snapshot_queries
    assert max(secret_snapshot_queries) < identity_secret_apply
    core_environment = runner.calls[core_deploy][1]
    assert core_environment["IDENTITY_MODE"] == "bundledKeycloak"
    assert core_environment["IDENTITY_RENDERED_MANIFEST"].endswith(
        "identity-rendered.yaml"
    )
    assert any(
        "apply_platform_secrets.py" in command and " --apply" in command
        for command in commands
    )
    for expected_argument in (
        "--identity-mode bundledKeycloak",
        (
            f"--identity-manifest {inputs['work_directory']}"
            "/snapshots/identity-rendered.yaml"
        ),
        (
            f"--harbor-dockerconfig {inputs['work_directory']}"
            "/snapshots/harbor-dockerconfig.json"
        ),
        f"--apps-tls-cert {inputs['work_directory']}/snapshots/apps-tls.crt",
        f"--oidc-ca {inputs['work_directory']}/snapshots/oidc-ca.crt",
        "--oidc-issuer https://keycloak.apps.rke.soez.tw/realms/aileron",
        (
            f"--platform-artifacts {MODULE.INSTALLATION_STATE.SECRET_STORE}"
            "/platform-artifacts"
        ),
    ):
        assert expected_argument in commands[core_deploy]
    assert "preflight-receipt" not in commands[core_deploy]
    generator = next(
        command for command in commands if command.startswith("docker run")
    )
    assert "--user 0:0" not in generator
    assert (
        "secret-registry.json:/installation-contract/secret-registry.json:ro"
        in generator
    )
    assert "--registry /installation-contract/secret-registry.json" in generator


@pytest.mark.parametrize(
    "phase",
    (MODULE.InstallationPhase.VALIDATE, MODULE.InstallationPhase.APPLY),
)
def test_external_data_service_inputs_follow_rendered_postgres_switches(
    tmp_path: Path,
    phase: MODULE.InstallationPhase,
) -> None:
    inputs = _inputs(tmp_path, "bundledKeycloak", phase=phase)
    private_root = inputs["work_directory"].parents[1]
    inputs.update(
        {
            "core_data_service_values": _private(
                private_root / "core-data-services.yaml",
                "postgres:\n  enabled: false\nredis:\n  enabled: false\n",
            ),
            "identity_data_service_values": _private(
                private_root / "identity-data-services.yaml",
                "postgres:\n  enabled: false\n",
            ),
            "identity_database_username": _private(
                private_root / "identity-database-username", "identity_login"
            ),
            "identity_database_password": _private(
                private_root / "identity-database-password", "identity-secret"
            ),
            "identity_database_ca": _private(
                private_root / "identity-database-ca.crt", "certificate"
            ),
        }
    )
    core_artifacts = tuple(
        (artifact_id, _private(private_root / f"{artifact_id}.input", value))
        for artifact_id, value in (
            (
                "database-url",
                "postgresql://platform_login:secret@db.example.test/platform",
            ),
            ("platform-database-ca", "certificate"),
            ("redis-general-url", "rediss://redis.example.test:6379/0"),
            ("redis-job-queue-url", "rediss://redis.example.test:6379/1"),
            ("redis-job-result-url", "rediss://redis.example.test:6379/2"),
            ("redis-general-ca", "certificate"),
            ("redis-job-queue-ca", "certificate"),
            ("redis-job-result-ca", "certificate"),
        )
    )
    inputs["core_data_service_inputs"] = core_artifacts
    inventory = inputs["inventory_path"]
    inventory.write_text(
        "".join(
            row
            for row in inventory.read_text(encoding="utf-8").splitlines(
                keepends=True
            )
            if not row.startswith("platform-redis\t")
        ),
        encoding="utf-8",
    )
    identity_path = (
        private_root / "install-secrets/rke2/installation-identity.json"
    )
    signed_inventory = inputs["work_directory"] / "signed-image-inventory.json"
    signed_inventory.unlink()
    MODULE.INSTALLATION_PREPARATION.ACCEPTANCE_RELEASE.write_signed_image_inventory(
        path=signed_inventory,
        private_root=private_root,
        images=[
            image
            for image in _published_images()
            if image["component"] != "platform-redis"
        ],
        key=ACCEPTANCE_KEY,
        context="rke",
        commit=COMMIT,
        cluster_uid="11111111-1111-4111-8111-111111111111",
        installation_identity_sha256=hashlib.sha256(
            identity_path.read_bytes()
        ).hexdigest(),
    )
    runner = FakeRunner()

    MODULE.install_rke2(**inputs, runner=runner)
    commands = _commands(runner)

    identity_generator = next(
        command
        for command in commands
        if "identity-installation/generate_secrets.py" in command
    )
    identity_apply = next(
        command
        for command in commands
        if "identity-installation/apply_secrets.sh" in command
    )
    platform_apply = next(
        command for command in commands if "apply_platform_secrets.py" in command
    )
    assert "postgres-disabled" in identity_generator
    assert "--values" in identity_generator
    assert "--postgres-username-file" in identity_apply
    assert "--postgres-password-file" in identity_apply
    assert "--postgres-ca-file" in identity_apply
    assert all(
        f"--external-input {artifact_id}=" in platform_apply
        for artifact_id, _ in core_artifacts
    )


def test_external_mode_skips_all_identity_workloads(tmp_path: Path) -> None:
    runner = FakeRunner()
    MODULE.install_rke2(**_inputs(tmp_path, "externalOidc"), runner=runner)
    commands = _commands(runner)

    assert not any("aileron-identity" in command for command in commands)
    assert not any("identity-installation/" in command for command in commands)
    readiness = next(command for command in commands if "wait_for_oidc.py" in command)
    assert "https://auth.example.test/o/aileron/" in readiness
    core_index = next(
        index
        for index, command in enumerate(commands)
        if command.startswith(str(ROOT / "scripts/deploy/rke2/deploy.sh"))
    )
    assert runner.calls[core_index][1]["IDENTITY_MODE"] == "externalOidc"
    assert "IDENTITY_RENDERED_MANIFEST" not in runner.calls[core_index][1]
    assert not (
        tmp_path / "private/install" / COMMIT / "release-values/identity-values.json"
    ).exists()


def test_successful_install_retains_structured_transaction_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    runner = FakeRunner()

    def fail_cleanup(**_: object) -> None:
        raise MODULE.INSTALLATION_TRANSACTION.InstallationTransactionError(
            "private cleanup detail"
        )

    monkeypatch.setattr(
        MODULE.INSTALLATION_TRANSACTION,
        "discard_transaction",
        fail_cleanup,
    )

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert str(caught.value) == (
        "installation failed during installation transaction cleanup; "
        "installer private transaction cleanup failed"
    )
    assert caught.value.__cause__ is caught.value.primary_cause
    assert caught.value.transaction_cleanup_cause is caught.value.primary_cause
    recovery = _recovery_result(inputs)
    assert recovery["primaryFailure"] == {
        "stage": "installation transaction cleanup",
        "exitCode": None,
    }
    for operation in ("secretRestore", "coreRollback", "identityRecovery"):
        assert recovery[operation] == {
            "attempted": False,
            "succeeded": False,
            "skipped": True,
        }
    assert "private cleanup detail" not in json.dumps(recovery)


def test_validate_missing_namespaces_returns_exit_78_and_preserves_private_tree(
    tmp_path: Path,
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    before = _private_tree_snapshot(MODULE.INSTALLATION_STATE.PRIVATE_ROOT)
    runner = FakeRunner(namespaces_ready=False)

    with pytest.raises(
        MODULE.InstallationPrerequisiteError,
        match="required namespaces are absent.*no Kubernetes resources were created",
    ) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert MODULE._safe_failure_exit_code(caught.value) == 78
    assert _private_tree_snapshot(MODULE.INSTALLATION_STATE.PRIVATE_ROOT) == before
    assert runner.namespaces_ready is False
    assert runner.namespace_created == []
    commands = _commands(runner)
    namespace_phase = next(
        index
        for index, command in enumerate(commands)
        if "ensure_installation_namespaces.py" in command
    )
    assert namespace_phase == len(commands) - 1
    assert not runner.secrets
    assert runner.identity_revision is None


def test_prepare_cluster_without_confirmation_runs_no_commands(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.PREPARE_CLUSTER,
    )
    runner = FakeRunner(namespaces_ready=False)

    with pytest.raises(MODULE.InstallationError, match="requires"):
        MODULE.install_rke2(**inputs, runner=runner)

    assert runner.calls == []
    assert runner.namespace_created == []


def test_prepare_cluster_persists_only_namespaces_then_runs_full_validation(
    tmp_path: Path,
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.PREPARE_CLUSTER,
    )
    inputs["confirm_create_namespaces"] = True
    before = _private_tree_snapshot(MODULE.INSTALLATION_STATE.PRIVATE_ROOT)
    runner = FakeRunner(namespaces_ready=False)

    MODULE.install_rke2(**inputs, runner=runner)

    assert runner.namespaces_ready is True
    assert runner.namespace_created == [
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    ]
    assert _private_tree_snapshot(MODULE.INSTALLATION_STATE.PRIVATE_ROOT) == before
    commands = _commands(runner)
    namespace_phase = next(
        index
        for index, command in enumerate(commands)
        if "ensure_installation_namespaces.py" in command
    )
    scoped_validation = [
        index
        for index, command in enumerate(commands)
        if command.startswith("helm upgrade") or "preflight.sh" in command
    ]
    assert scoped_validation
    assert min(scoped_validation) > namespace_phase
    assert all(
        "--dry-run=server" in command
        for command in commands
        if command.startswith("helm upgrade")
    )
    assert not runner.secrets
    assert runner.identity_revision is None
    assert not any("/deploy.sh " in command for command in commands)


def test_apply_requires_prepared_namespaces_without_mutating_cluster(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(namespaces_ready=False)

    with pytest.raises(MODULE.InstallationPrerequisiteError) as caught:
        MODULE.install_rke2(
            **_inputs(tmp_path, "externalOidc"),
            runner=runner,
        )

    assert MODULE._safe_failure_exit_code(caught.value) == 78
    assert runner.namespace_created == []
    commands = _commands(runner)
    namespace_commands = [
        command
        for command in commands
        if "ensure_installation_namespaces.py" in command
    ]
    assert len(namespace_commands) == 1
    assert "--validate-only" in namespace_commands[0]
    assert not any(
        " --apply" in command or "/deploy.sh " in command for command in commands
    )


def test_prepare_namespace_signal_preserves_partial_namespace_and_skips_mutation(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        namespaces_ready=False,
        namespace_prepare_failure="signal",
    )

    with pytest.raises(MODULE.InstallationInterrupted):
        inputs = _inputs(
            tmp_path,
            "externalOidc",
            phase=MODULE.InstallationPhase.PREPARE_CLUSTER,
        )
        inputs["confirm_create_namespaces"] = True
        MODULE.install_rke2(
            **inputs,
            runner=runner,
        )

    assert runner.namespace_created == ["workspace-system"]
    assert runner.namespaces_ready is False
    assert not runner.secrets
    assert runner.identity_revision is None
    commands = _commands(runner)
    assert "ensure_installation_namespaces.py" in commands[-1]
    assert not any(
        " --apply" in command
        or "/deploy.sh " in command
        or (command.startswith("helm upgrade") and "--dry-run=server" not in command)
        for command in commands
    )


def test_prepare_namespace_reverification_drift_skips_secret_and_release_mutation(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        namespaces_ready=False,
        namespace_prepare_failure="reverify-drift",
    )

    with pytest.raises(MODULE.InstallationCommandError):
        inputs = _inputs(
            tmp_path,
            "externalOidc",
            phase=MODULE.InstallationPhase.PREPARE_CLUSTER,
        )
        inputs["confirm_create_namespaces"] = True
        MODULE.install_rke2(
            **inputs,
            runner=runner,
        )

    assert runner.namespace_created == [
        "workspace-system",
        "aileron-turn-system",
        "aileron-backend-attestor-system",
    ]
    assert not runner.secrets
    assert runner.identity_revision is None
    commands = _commands(runner)
    assert "ensure_installation_namespaces.py" in commands[-1]
    assert not any(
        " --apply" in command
        or "/deploy.sh " in command
        or (command.startswith("helm upgrade") and "--dry-run=server" not in command)
        for command in commands
    )


def test_apply_rejects_namespace_replacement_after_preflight_before_transaction(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        replace_namespace_before_guard=True,
    )

    with pytest.raises(MODULE.InstallationError, match="namespace identity changed"):
        MODULE.install_rke2(
            **_inputs(tmp_path, "externalOidc"),
            runner=runner,
        )

    assert runner.namespace_phase_calls == 2
    assert runner.namespace_created == []
    assert not runner.secrets
    assert runner.identity_revision is None
    commands = _commands(runner)
    second_namespace_guard = max(
        index
        for index, command in enumerate(commands)
        if "ensure_installation_namespaces.py" in command
    )
    assert "--validate-only" in commands[second_namespace_guard]
    assert not any(
        " get secret " in command
        or " --apply" in command
        or "/deploy.sh " in command
        or (command.startswith("helm upgrade") and "--dry-run=server" not in command)
        for command in commands[second_namespace_guard + 1 :]
    )


@pytest.mark.parametrize("state", ["missing", "drifted"])
def test_install_requires_exact_retained_backend_resources_without_mutation(
    tmp_path: Path,
    state: str,
) -> None:
    runner = FakeRunner(backend_prerequisite_state=state)

    with pytest.raises(
        MODULE.InstallationPrerequisiteError,
        match="retained backend attestor prerequisite is invalid",
    ) as caught:
        MODULE.install_rke2(
            **_inputs(tmp_path, "externalOidc"),
            runner=runner,
        )

    assert MODULE._safe_failure_exit_code(caught.value) == 78
    assert runner.secrets == {}
    assert runner.identity_revision is None
    assert not any(
        " --apply" in command or "/deploy.sh " in command
        for command in _commands(runner)
    )


def test_apply_rejects_retained_backend_namespace_replacement_before_transaction(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(backend_prerequisite_state="replaced")

    with pytest.raises(
        MODULE.InstallationPrerequisiteError,
        match="changed after validation",
    ):
        MODULE.install_rke2(
            **_inputs(tmp_path, "externalOidc"),
            runner=runner,
        )

    assert runner.backend_namespace_reads == 4
    assert runner.secrets == {}
    assert not any(
        output is not None and "get" in command and "secret" in command
        for command, _, output in runner.calls
    )


@pytest.mark.parametrize("drift", ["deleted", "replaced"])
def test_apply_revalidates_live_acceptance_trust_before_secret_transaction(
    tmp_path: Path,
    drift: str,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    anchor = MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-trust-anchor.json"
    original_anchor = anchor.read_bytes()
    runner = FakeRunner(acceptance_secret_drift=drift)

    with pytest.raises(
        MODULE.InstallationError,
        match="live acceptance trust changed after installation validation",
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    assert runner.acceptance_secret_reads == 2
    assert anchor.read_bytes() == original_anchor
    assert runner.secrets == {}
    commands = _commands(runner)
    assert not any(
        (
            " get secret " in command
            and "--ignore-not-found" in command
            and "aileron-backend-attestor-system" not in command
        )
        or " --apply" in command
        or "/deploy.sh " in command
        or (command.startswith("helm upgrade") and "--dry-run=server" not in command)
        or ("create" in command and "aileron-acceptance-signing" in command)
        for command in commands
    )


def test_apply_rejects_concurrent_acceptance_trust_rebind_before_mutation(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(acceptance_secret_drift="rebound")

    with pytest.raises(
        MODULE.InstallationError,
        match="live acceptance trust changed after installation validation",
    ):
        MODULE.install_rke2(**_inputs(tmp_path, "externalOidc"), runner=runner)

    assert runner.acceptance_secret_reads == 2
    assert runner.secrets == {}
    commands = _commands(runner)
    assert not any(
        (
            " get secret " in command
            and "--ignore-not-found" in command
            and "aileron-backend-attestor-system" not in command
        )
        or " --apply" in command
        or "/deploy.sh " in command
        for command in commands
    )


@pytest.mark.parametrize(
    "phase",
    [
        MODULE.InstallationPhase.VALIDATE,
        MODULE.InstallationPhase.PREPARE_CLUSTER,
        MODULE.InstallationPhase.APPLY,
    ],
)
def test_terminating_namespace_stops_every_phase_before_secret_transaction(
    tmp_path: Path,
    phase: MODULE.InstallationPhase,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=phase)
    if phase is MODULE.InstallationPhase.PREPARE_CLUSTER:
        inputs["confirm_create_namespaces"] = True
    runner = FakeRunner(terminating_namespace="workspace-system")

    with pytest.raises(
        MODULE.InstallationCommandError,
        match="ensure_installation_namespaces.py exited with code 65",
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    commands = _commands(runner)
    assert any("ensure_installation_namespaces.py" in command for command in commands)
    assert not any(
        (" get secret " in command and "--ignore-not-found" in command)
        or " --apply" in command
        or "/deploy.sh " in command
        or (command.startswith("helm upgrade") and "--dry-run=server" not in command)
        for command in commands
    )
    assert runner.secrets == {}


def test_validate_phase_has_no_release_or_secret_mutation(tmp_path: Path) -> None:
    runner = FakeRunner()
    MODULE.install_rke2(
        **_inputs(
            tmp_path,
            "bundledKeycloak",
            phase=MODULE.InstallationPhase.VALIDATE,
        ),
        runner=runner,
    )
    commands = _commands(runner)

    assert all(
        "--dry-run=server" in command
        for command in commands
        if command.startswith("helm upgrade")
    )
    assert not any(
        command.endswith("deploy.sh") or "/deploy.sh " in command
        for command in commands
    )
    assert not any(
        " --apply" in command
        for command in commands
        if "apply_platform_secrets.py" in command
    )
    assert any(
        "--dry-run" in command for command in commands if "apply_secrets.sh" in command
    )
    assert any("--dry-run=server" in command for command in commands)
    assert any(
        "ensure_installation_namespaces.py" in command and "--validate-only" in command
        for command in commands
    )


@pytest.mark.parametrize("previous_revision", [None, 7])
def test_core_failure_recovers_identity_release(
    tmp_path: Path, previous_revision: int | None
) -> None:
    runner = FakeRunner(
        previous_identity_revision=previous_revision,
        core_failure_command=_failing_core_command(tmp_path),
    )
    with pytest.raises(MODULE.InstallationError, match="recovered"):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)
    commands = _commands(runner)

    if previous_revision is None:
        recovery = next(
            index
            for index, command in enumerate(commands)
            if command.startswith("helm uninstall aileron-identity")
        )
    else:
        recovery = next(
            index
            for index, command in enumerate(commands)
            if command.startswith("helm rollback aileron-identity 7")
        )
    core_deploy = next(
        index
        for index, command in enumerate(commands)
        if command.startswith(str(ROOT / "scripts/deploy/rke2/deploy.sh"))
    )
    secret_restore_commands = [
        index
        for index, command in enumerate(commands)
        if index > core_deploy
        and command.startswith("kubectl ")
        and (" get secret " in command or " delete --raw " in command)
    ]
    assert secret_restore_commands
    assert max(secret_restore_commands) < recovery


@pytest.mark.parametrize(
    ("previous_revision", "signal_number"),
    [(None, signal.SIGINT), (7, signal.SIGTERM)],
)
def test_catchable_interruption_uses_transactional_recovery_and_retains_result(
    tmp_path: Path,
    previous_revision: int | None,
    signal_number: int,
) -> None:
    runner = FakeRunner(
        previous_identity_revision=previous_revision,
        interrupt_signal=signal_number,
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")
    previous_handlers = {
        signal_value: signal.getsignal(signal_value)
        for signal_value in (signal.SIGINT, signal.SIGTERM)
    }

    with pytest.raises(MODULE.InstallationError, match="recovered") as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert isinstance(caught.value.__cause__, MODULE.InstallationInterrupted)
    assert caught.value.__cause__.signal_number == signal_number
    assert {
        signal_value: signal.getsignal(signal_value)
        for signal_value in (signal.SIGINT, signal.SIGTERM)
    } == previous_handlers
    recovery = _recovery_result(inputs)
    assert recovery["primaryFailure"] == {
        "stage": "core deployment",
        "exitCode": 128 + signal_number,
    }
    assert recovery["secretRestore"]["succeeded"] is True
    assert recovery["coreRollback"] == {
        "attempted": True,
        "succeeded": True,
        "skipped": False,
    }
    assert recovery["identityRecovery"] == {
        "attempted": True,
        "succeeded": True,
        "skipped": False,
    }
    assert runner.secrets == {}
    assert runner.identity_status in (None, "deployed")


def test_unquiesced_interrupted_process_skips_all_cluster_recovery(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        previous_identity_revision=7,
        process_quiescence_failure=True,
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert caught.value.process_quiescence_cause is not None
    assert caught.value.identity_recovery_skipped is True
    commands = _commands(runner)
    core_deploy = next(
        index
        for index, command in enumerate(commands)
        if command.startswith(str(ROOT / "scripts/deploy/rke2/deploy.sh"))
    )
    assert not any(
        command.startswith("kubectl ") and " get secret " in command
        for command in commands[core_deploy + 1 :]
    )
    assert not any(
        command.startswith(
            ("helm rollback aileron-identity", "helm uninstall aileron-identity")
        )
        for command in commands[core_deploy + 1 :]
    )
    recovery = _recovery_result(inputs)
    assert recovery["primaryFailure"] == {
        "stage": "core deployment",
        "exitCode": 128 + signal.SIGTERM,
    }
    for operation in ("secretRestore", "coreRollback", "identityRecovery"):
        assert recovery[operation] == {
            "attempted": False,
            "succeeded": False,
            "skipped": True,
        }


def test_post_identity_failure_reports_safe_stage_command_and_exit_code(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        previous_identity_revision=7,
        core_failure_command=_failing_core_command(tmp_path),
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert str(caught.value) == (
        "installation failed during core deployment "
        "(command deploy.sh exited with code 23); "
        "installer-owned Secret state was restored; Identity release was recovered"
    )
    assert isinstance(caught.value.__cause__, MODULE.InstallationCommandError)
    assert caught.value.__cause__.command_identity == "deploy.sh"
    assert caught.value.__cause__.exit_code == 23
    serialized_error = repr(caught.value) + repr(caught.value.__cause__)
    assert "private stderr value" not in serialized_error
    assert "private-argument-value" not in serialized_error
    assert str(tmp_path) not in serialized_error
    recovery = _recovery_result(inputs)
    assert recovery["primaryFailure"] == {
        "stage": "core deployment",
        "exitCode": 23,
    }
    assert recovery["secretRestore"] == {
        "attempted": True,
        "succeeded": True,
        "skipped": False,
    }
    assert recovery["coreRollback"] == {
        "attempted": True,
        "succeeded": True,
        "skipped": False,
    }
    assert recovery["identityRecovery"] == {
        "attempted": True,
        "succeeded": True,
        "skipped": False,
    }
    serialized_recovery = json.dumps(recovery)
    assert "private" not in serialized_recovery
    assert str(tmp_path) not in serialized_recovery


def test_identity_recovery_failure_preserves_primary_cause_and_safe_stage(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        previous_identity_revision=7,
        core_failure_command=_failing_core_command(tmp_path),
        rollback_failure_command=_failing_rollback_command(tmp_path),
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert str(caught.value) == (
        "installation failed during core deployment "
        "(command deploy.sh exited with code 23); Identity recovery failed "
        "(command helm exited with code 31)"
    )
    assert caught.value.__cause__ is caught.value.primary_cause
    assert caught.value.primary_cause.command_identity == "deploy.sh"
    assert caught.value.primary_cause.exit_code == 23
    assert caught.value.identity_recovery_cause.command_identity == "helm"
    assert caught.value.identity_recovery_cause.exit_code == 31
    serialized_error = (
        repr(caught.value)
        + repr(caught.value.primary_cause)
        + repr(caught.value.identity_recovery_cause)
    )
    assert "private stderr value" not in serialized_error
    assert "private rollback stderr" not in serialized_error
    assert "private-argument-value" not in serialized_error
    assert "private-rollback-argument" not in serialized_error
    assert str(tmp_path) not in serialized_error
    recovery = _recovery_result(inputs)
    assert recovery["secretRestore"]["succeeded"] is True
    assert recovery["coreRollback"]["succeeded"] is True
    assert recovery["identityRecovery"] == {
        "attempted": True,
        "succeeded": False,
        "skipped": False,
    }


@pytest.mark.parametrize("previous_revision", [None, 7])
def test_atomic_identity_command_failure_uses_prearmed_live_recovery_guard(
    tmp_path: Path, previous_revision: int | None
) -> None:
    runner = FakeRunner(
        previous_identity_revision=previous_revision,
        fail_identity_upgrade=True,
    )

    with pytest.raises(
        MODULE.InstallationError, match="Identity release was recovered"
    ):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)

    commands = _commands(runner)
    identity_upgrade = next(
        index
        for index, command in enumerate(commands)
        if command.startswith("helm upgrade --install aileron-identity")
        and "--dry-run=server" not in command
    )
    if previous_revision is None:
        recovery = next(
            index
            for index, command in enumerate(commands)
            if command.startswith("helm uninstall aileron-identity")
        )
    else:
        recovery = next(
            index
            for index, command in enumerate(commands)
            if command.startswith("helm rollback aileron-identity 7")
        )
    assert identity_upgrade < recovery
    assert runner.identity_status in (None, "deployed")
    assert runner.secrets == {}


def test_failed_core_rollback_blocks_identity_recovery_and_preserves_two_causes(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        previous_identity_revision=7,
        core_failure_command=_failing_core_command(tmp_path),
        core_rollback_succeeded=False,
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert str(caught.value) == (
        "installation failed during core deployment "
        "(command deploy.sh exited with code 23); Core rollback failed; "
        "Identity recovery was skipped"
    )
    assert caught.value.__cause__ is caught.value.primary_cause
    assert caught.value.primary_cause.command_identity == "deploy.sh"
    assert caught.value.primary_cause.exit_code == 23
    assert isinstance(caught.value.core_rollback_cause, MODULE.InstallationError)
    assert caught.value.identity_recovery_cause is None
    assert runner.secrets == {}
    commands = _commands(runner)
    assert not any(
        command.startswith(
            ("helm rollback aileron-identity", "helm uninstall aileron-identity")
        )
        for command in commands
    )
    recovery = _recovery_result(inputs)
    assert recovery["secretRestore"]["succeeded"] is True
    assert recovery["coreRollback"] == {
        "attempted": True,
        "succeeded": False,
        "skipped": False,
    }
    assert recovery["identityRecovery"] == {
        "attempted": False,
        "succeeded": False,
        "skipped": True,
    }


def test_secret_restore_failure_blocks_identity_recovery_and_retains_transaction(
    tmp_path: Path,
) -> None:
    failed_reference = MODULE.INSTALLATION_TRANSACTION.IDENTITY_SECRET_REFERENCES[0]
    runner = FakeRunner(
        previous_identity_revision=7,
        core_failure_command=_failing_core_command(tmp_path),
        fail_secret_restore_for=failed_reference,
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert str(caught.value) == (
        "installation failed during core deployment "
        "(command deploy.sh exited with code 23); "
        "installer-owned Secret restore failed; Identity recovery was skipped"
    )
    assert caught.value.__cause__ is caught.value.primary_cause
    assert caught.value.primary_cause.command_identity == "deploy.sh"
    assert caught.value.primary_cause.exit_code == 23
    assert caught.value.secret_restore_cause is not None
    assert caught.value.identity_recovery_cause is None
    assert failed_reference in runner.secrets
    commands = _commands(runner)
    assert not any(
        command.startswith(
            ("helm rollback aileron-identity", "helm uninstall aileron-identity")
        )
        for command in commands
    )
    transactions = list((inputs["work_directory"] / "transactions").iterdir())
    assert len(transactions) == 1
    assert transactions[0].is_dir()
    recovery = _recovery_result(inputs)
    assert recovery["secretRestore"] == {
        "attempted": True,
        "succeeded": False,
        "skipped": False,
    }
    assert recovery["coreRollback"]["succeeded"] is True
    assert recovery["identityRecovery"] == {
        "attempted": False,
        "succeeded": False,
        "skipped": True,
    }


def test_existing_secret_uid_change_retains_transaction_and_skips_identity_recovery(
    tmp_path: Path,
) -> None:
    reference = MODULE.INSTALLATION_TRANSACTION.IDENTITY_SECRET_REFERENCES[0]
    runner = FakeRunner(
        previous_identity_revision=7,
        core_failure_command=_failing_core_command(tmp_path),
        recreate_secret_for=reference,
    )
    runner.secrets[reference] = _secret_document(
        *reference, "semantic-original-private-value"
    )
    inputs = _inputs(tmp_path, "bundledKeycloak")

    with pytest.raises(MODULE.InstallationRecoveryError) as caught:
        MODULE.install_rke2(**inputs, runner=runner)

    assert caught.value.secret_restore_cause is not None
    assert caught.value.identity_recovery_skipped is True
    assert runner.secrets[reference]["metadata"]["uid"] == (
        "33333333-3333-4333-8333-333333333333"
    )
    commands = _commands(runner)
    assert not any(
        command.startswith(
            ("helm rollback aileron-identity", "helm uninstall aileron-identity")
        )
        for command in commands
    )
    recovery = _recovery_result(inputs)
    assert recovery["secretRestore"] == {
        "attempted": True,
        "succeeded": False,
        "skipped": False,
    }
    assert recovery["coreRollback"]["succeeded"] is True
    assert recovery["identityRecovery"] == {
        "attempted": False,
        "succeeded": False,
        "skipped": True,
    }


@pytest.mark.parametrize("failure_stage", ["identity", "platform"])
def test_mid_apply_failure_restores_only_exact_secret_allowlist(
    tmp_path: Path, failure_stage: str
) -> None:
    runner = FakeRunner(fail_secret_apply_stage=failure_stage)
    identity_ref = MODULE.INSTALLATION_TRANSACTION.IDENTITY_SECRET_REFERENCES[0]
    platform_ref = MODULE.INSTALLATION_TRANSACTION.secret_references(
        identity_mode="externalOidc"
    )[0]
    unrelated_ref = ("workspace-system", "unrelated-private-secret")
    initial = {
        identity_ref: _secret_document(*identity_ref, "identity-original"),
        platform_ref: _secret_document(*platform_ref, "platform-original"),
        unrelated_ref: _secret_document(*unrelated_ref, "unrelated-original"),
    }
    runner.secrets = copy.deepcopy(initial)

    with pytest.raises(MODULE.InstallationError, match="Secret state was restored"):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)

    assert runner.secrets == initial
    commands = _commands(runner)
    assert not any(
        command.startswith("helm upgrade --install aileron-identity")
        and "--dry-run=server" not in command
        for command in commands
    )


def test_core_capacity_preflight_failure_does_not_mutate_identity_release(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(previous_identity_revision=7, fail_core_preflight=True)

    with pytest.raises(
        MODULE.InstallationCommandError, match="preflight.sh exited with code 1"
    ):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)

    commands = _commands(runner)
    assert any(
        command.startswith(str(ROOT / "scripts/deploy/rke2/preflight.sh"))
        for command in commands
    )
    assert not any(
        "identity-installation/apply_secrets.sh" in command
        and "--dry-run" not in command
        for command in commands
    )
    assert not any(
        "apply_platform_secrets.py" in command and "--apply" in command
        for command in commands
    )
    assert not any(
        command.startswith("helm upgrade --install aileron-identity")
        and "--dry-run=server" not in command
        for command in commands
    )
    assert not any(
        command.startswith(
            ("helm rollback aileron-identity", "helm uninstall aileron-identity")
        )
        for command in commands
    )


def test_dirty_or_wrong_commit_stops_before_namespace_or_secret_actions(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(dirty=True)
    with pytest.raises(MODULE.InstallationError, match="clean"):
        MODULE.install_rke2(**_inputs(tmp_path, "bundledKeycloak"), runner=runner)
    assert len(runner.calls) == 1


def test_commands_never_contain_private_file_contents(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    private_value = "must-not-appear-in-command-or-environment"
    inputs["external_oidc_client_secret"].write_text(private_value, encoding="utf-8")
    runner = FakeRunner()
    MODULE.install_rke2(**inputs, runner=runner)

    serialized = json.dumps(
        [
            {"command": command, "environment": environment}
            for command, environment, _ in runner.calls
        ]
    )
    assert private_value not in serialized


def test_platform_artifact_tree_is_reusable_by_non_root_generator(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    runner = FakeRunner()

    MODULE.install_rke2(**inputs, runner=runner)
    MODULE.install_rke2(**inputs, runner=runner)

    assert len(runner.generator_owners) == 2
    assert all(owners == {65532} for owners in runner.generator_owners)
    assert runner.generator_input_owners == [65532, 65532]
    artifact = (
        MODULE.INSTALLATION_STATE.SECRET_STORE
        / "platform-artifacts/simulated-container-artifact"
    )
    assert artifact.stat().st_uid == 0
    assert (
        inputs["work_directory"] / "snapshots/core-values.json"
    ).stat().st_uid == 0


def test_credentials_use_stable_store_not_commit_evidence_and_survive_recovery(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "bundledKeycloak")
    stable_secret = _private(
        MODULE.INSTALLATION_STATE.SECRET_STORE
        / "identity-artifacts/aileron-oidc-client/client-secret",
        "stable-across-releases",
    )
    runner = FakeRunner(core_failure_command=_failing_core_command(tmp_path))

    with pytest.raises(MODULE.InstallationError, match="recovered"):
        MODULE.install_rke2(**inputs, runner=runner)

    assert stable_secret.read_text(encoding="utf-8") == "stable-across-releases"
    commands = _commands(runner)
    generator = next(
        command for command in commands if command.startswith("docker run")
    )
    assert (
        str(MODULE.INSTALLATION_STATE.SECRET_STORE / "platform-artifacts") in generator
    )
    assert str(inputs["work_directory"] / "platform-artifacts") not in generator
    assert any(
        f"--output-dir {MODULE.INSTALLATION_STATE.SECRET_STORE / 'identity-artifacts'}"
        in command
        for command in commands
    )


def test_rejects_secret_store_inside_commit_evidence(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    nested = inputs["work_directory"] / "secrets"
    nested.mkdir(mode=0o700)
    MODULE.INSTALLATION_STATE.SECRET_STORE = nested

    with pytest.raises(MODULE.InstallationError, match="separate"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())


def test_rejects_counterfeit_install_work_directory_prefix(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    counterfeit = (
        MODULE.INSTALLATION_STATE.PRIVATE_ROOT
        / "counterfeit-prefix"
        / "install"
        / COMMIT
    )
    _private_directory(counterfeit)
    inputs["work_directory"] = counterfeit

    with pytest.raises(MODULE.InstallationError, match="canonical commit directory"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())


def test_rejects_symlinked_private_input_and_ancestor(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    target = _private(MODULE.INSTALLATION_STATE.PRIVATE_ROOT / "real-client-secret")
    linked = MODULE.INSTALLATION_STATE.PRIVATE_ROOT / "linked-client-secret"
    linked.symlink_to(target)
    inputs["external_oidc_client_secret"] = linked
    with pytest.raises(MODULE.InstallationError, match="symbolic link"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())

    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    linked_parent = MODULE.INSTALLATION_STATE.PRIVATE_ROOT / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)
    inputs["external_oidc_client_secret"] = _private(outside / "client-secret")
    inputs["apps_tls_ca"] = linked_parent / "client-secret"
    with pytest.raises(MODULE.InstallationError, match="symbolic link"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())


def test_rejects_private_input_outside_explicit_root(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc", phase=MODULE.InstallationPhase.VALIDATE)
    inputs["oidc_ca"] = _private(tmp_path / "outside-ca.crt")
    with pytest.raises(MODULE.InstallationError, match="private root"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())


@pytest.mark.parametrize(
    "boundary",
    [
        "private-root",
        "install-root",
        "work-directory",
        "secret-store-parent",
        "secret-store",
        "kubeconfig",
    ],
)
def test_installer_rejects_mode_correct_private_state_owned_by_another_uid(
    tmp_path: Path,
    boundary: str,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    private_root = MODULE.INSTALLATION_STATE.PRIVATE_ROOT
    target = {
        "private-root": private_root,
        "install-root": private_root / "install",
        "work-directory": inputs["work_directory"],
        "secret-store-parent": MODULE.INSTALLATION_STATE.SECRET_STORE.parent,
        "secret-store": MODULE.INSTALLATION_STATE.SECRET_STORE,
        "kubeconfig": inputs["kubeconfig"],
    }[boundary]
    os.chown(target, 65532, 65532)

    with pytest.raises(MODULE.InstallationError, match="owner-controlled"):
        MODULE.install_rke2(**inputs, runner=FakeRunner())


def test_two_commits_reuse_the_same_installation_secret_store(tmp_path: Path) -> None:
    first = _inputs(tmp_path, "externalOidc")
    MODULE.install_rke2(**first, runner=FakeRunner())
    fixed_store = MODULE.INSTALLATION_STATE.SECRET_STORE
    marker = fixed_store / "platform-artifacts/simulated-container-artifact"
    original = marker.read_bytes()

    second_commit = "b" * 40
    second = _inputs(
        tmp_path,
        "externalOidc",
        commit=second_commit,
    )
    MODULE.install_rke2(
        **second,
        runner=FakeRunner(head_commit=second_commit),
    )

    assert MODULE.INSTALLATION_STATE.SECRET_STORE == fixed_store
    assert marker.read_bytes() == original
    assert first["work_directory"] != second["work_directory"]


def test_installer_consumes_identity_profile_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejecting_schema = _private(
        tmp_path / "rejecting-profile.schema.json",
        json.dumps({"type": "object", "required": ["impossible"]}),
    )
    monkeypatch.setattr(MODULE, "IDENTITY_PROFILE_SCHEMA", rejecting_schema)

    with pytest.raises(MODULE.InstallationError, match="profile violates"):
        MODULE.install_rke2(
            **_inputs(
                tmp_path,
                "externalOidc",
                phase=MODULE.InstallationPhase.VALIDATE,
            ),
            runner=FakeRunner(),
        )


def test_bundled_installer_converges_with_shared_prereset_identity(
    tmp_path: Path,
) -> None:
    inputs = _inputs(
        tmp_path, "bundledKeycloak", phase=MODULE.InstallationPhase.VALIDATE
    )
    runner = FakeRunner()
    expected = MODULE.INSTALLATION_STATE.installation_identity_document(
        installation_id="44444444-4444-4444-8444-444444444444",
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
        client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
        cluster_uid=runner.cluster_uid,
    )
    manifest = MODULE.INSTALLATION_STATE.SECRET_STORE / "installation-identity.json"
    _private(manifest, json.dumps(expected, indent=2, sort_keys=True) + "\n")

    MODULE.install_rke2(**inputs, runner=runner)

    assert json.loads(manifest.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("drift", ["context", "cluster", "issuer"])
def test_stable_installation_identity_rejects_drift_before_apply(
    tmp_path: Path, drift: str
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    MODULE.install_rke2(**inputs, runner=FakeRunner())
    manifest = MODULE.INSTALLATION_STATE.SECRET_STORE / "installation-identity.json"
    assert manifest.stat().st_mode & 0o777 == 0o600
    signing_key = MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-hmac.key"
    assert signing_key.stat().st_mode & 0o777 == 0o600
    assert len(signing_key.read_bytes()) == 32

    runner = FakeRunner()
    if drift == "context":
        inputs["context"] = "other-context"
    elif drift == "cluster":
        runner = FakeRunner(cluster_uid="22222222-2222-4222-8222-222222222222")
    else:
        inputs["external_oidc_issuer_url"] = "https://other.example.test/oidc/"

    expected_failure = (
        "kubeconfig snapshot context"
        if drift == "context"
        else "live acceptance trust" if drift == "cluster" else "installation identity"
    )
    with pytest.raises(MODULE.InstallationError, match=expected_failure):
        MODULE.install_rke2(**inputs, runner=runner)
    assert not any(
        "apply_secrets.sh" in command or "apply_platform_secrets.py" in command
        for command in _commands(runner)
    )


def test_rejects_malformed_cluster_uid_before_apply(tmp_path: Path) -> None:
    runner = FakeRunner(cluster_uid="11111111----------------------------")

    with pytest.raises(MODULE.InstallationError, match="live acceptance trust"):
        MODULE.install_rke2(
            **_inputs(
                tmp_path,
                "externalOidc",
                phase=MODULE.InstallationPhase.VALIDATE,
            ),
            runner=runner,
        )
    assert not any(
        "apply_secrets.sh" in command or "apply_platform_secrets.py" in command
        for command in _commands(runner)
    )


def test_installer_consumes_live_trust_and_prepared_exact_image_inventory(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    envelope_path = inputs["work_directory"] / "signed-image-inventory.json"
    prepared_envelope = envelope_path.read_bytes()
    MODULE.install_rke2(**inputs, runner=FakeRunner())

    assert envelope_path.stat().st_mode & 0o777 == 0o600
    assert envelope_path.read_bytes() == prepared_envelope
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    signature = envelope.pop("signature")
    canonical = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    key = (MODULE.INSTALLATION_STATE.SECRET_STORE / "acceptance-hmac.key").read_bytes()
    assert hmac.compare_digest(
        signature, hmac.new(key, canonical, hashlib.sha256).hexdigest()
    )
    assert envelope["schemaVersion"] == "aileron-signed-image-inventory/v2"
    assert envelope["commit"] == COMMIT
    assert envelope["clusterUid"] == "11111111-1111-4111-8111-111111111111"
    assert envelope["context"] == "rke"
    assert len(envelope["images"]) == 11

    runner = FakeRunner()
    (tmp_path / "other").mkdir(mode=0o700)
    other_inputs = _inputs(tmp_path / "other", "externalOidc")
    MODULE.install_rke2(**other_inputs, runner=runner)
    apply_command = next(
        command
        for command in _commands(runner)
        if "apply_platform_secrets.py" in command
    )
    assert "--private-root" not in apply_command
    assert "--secret-store" not in apply_command
    assert "--acceptance-signing-key" not in apply_command
    assert "--installation-identity" not in apply_command


def test_installer_never_signs_or_reconstructs_missing_release_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    signed = inputs["work_directory"] / "signed-image-inventory.json"
    signed.unlink()
    monkeypatch.setattr(
        MODULE.INSTALLATION_PREPARATION.ACCEPTANCE_RELEASE,
        "write_signed_image_inventory",
        lambda **_arguments: pytest.fail("installer must not sign image inventory"),
    )
    runner = FakeRunner()

    with pytest.raises(
        MODULE.InstallationError,
        match="canonical signed image inventory is invalid",
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    assert not signed.exists()
    assert not any(
        "ensure_installation_namespaces.py" in command for command in _commands(runner)
    )


def test_installer_rejects_unsigned_inventory_drift_from_prepared_envelope(
    tmp_path: Path,
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    signed = inputs["work_directory"] / "signed-image-inventory.json"
    prepared_envelope = signed.read_bytes()
    rows = inputs["inventory_path"].read_text(encoding="utf-8").splitlines()
    columns = rows[0].split("\t")
    columns[-1] = columns[-1].rsplit(":", 1)[0] + ":" + "f" * 64
    inputs["inventory_path"].write_text(
        "\t".join(columns) + "\n" + "\n".join(rows[1:]) + "\n",
        encoding="utf-8",
    )
    inputs["inventory_path"].chmod(0o600)
    runner = FakeRunner()

    with pytest.raises(
        MODULE.InstallationError,
        match="canonical signed image inventory is invalid",
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    assert signed.read_bytes() == prepared_envelope
    assert not any(
        "ensure_installation_namespaces.py" in command for command in _commands(runner)
    )


def test_installation_has_no_replayable_core_preflight_receipt(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    runner = FakeRunner()

    MODULE.install_rke2(**inputs, runner=runner)

    secret_store = MODULE.INSTALLATION_STATE.SECRET_STORE
    assert not (secret_store / "core-preflight-hmac.key").exists()
    assert not (inputs["work_directory"] / "core-preflight-receipt.json").exists()
    serialized_commands = json.dumps(runner.calls, default=str)
    assert "preflight-receipt" not in serialized_commands


@pytest.mark.parametrize("mode", ["bundledKeycloak", "externalOidc"])
def test_install_rke2_prepares_mode_specific_owned_snapshots(
    tmp_path: Path,
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path, mode)
    runner = FakeRunner()
    observed_prepared: list[MODULE.INSTALLATION_PREPARATION.PreparedInstallation] = []
    execute_prepared = MODULE._install_rke2_locked

    def observe_prepared(
        *,
        prepared: MODULE.INSTALLATION_PREPARATION.PreparedInstallation,
        runner: FakeRunner,
    ) -> None:
        assert isinstance(prepared, tuple)
        assert isinstance(prepared.snapshots, tuple)
        assert isinstance(prepared.acceptance_trust, tuple)
        assert not any(
            isinstance(value, (dict, list, set))
            for group in (prepared, prepared.snapshots, prepared.acceptance_trust)
            for value in group
        )
        observed_prepared.append(prepared)
        execute_prepared(prepared=prepared, runner=runner)

    monkeypatch.setattr(MODULE, "_install_rke2_locked", observe_prepared)

    MODULE.install_rke2(**inputs, runner=runner)

    assert len(observed_prepared) == 1
    snapshot_directory = inputs["work_directory"] / "snapshots"
    expected_snapshots = {
        snapshot_directory / "kubeconfig.raw",
        snapshot_directory / "kubeconfig",
        snapshot_directory / "published-image-inventory.tsv",
        snapshot_directory / "harbor-dockerconfig.json",
        snapshot_directory / "apps-tls.crt",
        snapshot_directory / "apps-tls.key",
        snapshot_directory / "apps-tls-ca.crt",
        snapshot_directory / "oidc-ca.crt",
        snapshot_directory / "core-values.json",
    }
    mode_snapshots = (
        {
            snapshot_directory / "identity-tls.crt",
            snapshot_directory / "identity-tls.key",
            snapshot_directory / "identity-values.json",
            snapshot_directory / "identity-rendered.yaml",
        }
        if mode == "bundledKeycloak"
        else {snapshot_directory / "external-oidc-client-secret"}
    )
    expected_snapshots.update(mode_snapshots)
    assert all(path.is_file() for path in expected_snapshots)
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in expected_snapshots)
    unexpected_snapshots = (
        {snapshot_directory / "external-oidc-client-secret"}
        if mode == "bundledKeycloak"
        else {
            snapshot_directory / "identity-tls.crt",
            snapshot_directory / "identity-tls.key",
            snapshot_directory / "identity-values.json",
            snapshot_directory / "identity-rendered.yaml",
        }
    )
    assert not any(path.exists() for path in unexpected_snapshots)
    serialized_commands = json.dumps(runner.calls, default=str)
    assert str(inputs["work_directory"] / "release-values/core-values.json") not in (
        serialized_commands
    )
    assert (
        str(inputs["work_directory"] / "release-values/identity-values.json")
        not in serialized_commands
    )
    common_source_names = (
        "kubeconfig",
        "inventory_path",
        "harbor_dockerconfig",
        "apps_tls_cert",
        "apps_tls_key",
        "apps_tls_ca",
        "oidc_ca",
    )
    mode_source_names = (
        ("identity_tls_cert", "identity_tls_key")
        if mode == "bundledKeycloak"
        else ("external_oidc_client_secret",)
    )
    for source_name in (*common_source_names, *mode_source_names):
        assert str(inputs[source_name]) not in serialized_commands
    common_command_snapshots = (
        "kubeconfig.raw",
        "kubeconfig",
        "harbor-dockerconfig.json",
        "apps-tls.crt",
        "apps-tls.key",
        "apps-tls-ca.crt",
        "oidc-ca.crt",
        "core-values.json",
    )
    mode_command_snapshots = (
        (
            "identity-tls.crt",
            "identity-tls.key",
            "identity-values.json",
            "identity-rendered.yaml",
        )
        if mode == "bundledKeycloak"
        else ("external-oidc-client-secret",)
    )
    for snapshot_name in (*common_command_snapshots, *mode_command_snapshots):
        assert str(snapshot_directory / snapshot_name) in serialized_commands
    flatten_index = next(
        index
        for index, (command, _, _) in enumerate(runner.calls)
        if command[0] == "kubectl" and "--flatten" in command
    )
    assert runner.calls[flatten_index][1]["KUBECONFIG"] == str(
        snapshot_directory / "kubeconfig.raw"
    )
    assert all(
        environment.get("KUBECONFIG") == str(snapshot_directory / "kubeconfig")
        for _, environment, _ in runner.calls[flatten_index + 1 :]
    )


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("cluster", "certificate-authority", "/private/ca.crt"),
        ("user", "client-certificate", "/private/client.crt"),
        ("user", "client-key", "/private/client.key"),
        ("user", "tokenFile", "/private/token"),
        ("user", "token-file", "/private/token"),
        ("user", "exec", {"command": "credential-plugin"}),
        ("user", "auth-provider", {"name": "oidc"}),
    ],
)
def test_kubeconfig_rejects_every_external_or_dynamic_reference_before_flattening(
    tmp_path: Path,
    section: str,
    key: str,
    value: object,
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    document = json.loads(inputs["kubeconfig"].read_text(encoding="utf-8"))
    if section == "cluster":
        document["clusters"][0]["cluster"][key] = value
    else:
        document["users"][0]["user"][key] = value
    inputs["kubeconfig"].write_text(
        json.dumps(document, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    runner = FakeRunner()

    with pytest.raises(
        MODULE.InstallationError,
        match="external or dynamic reference",
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    commands = _commands(runner)
    assert not any("config view" in command for command in commands)
    assert not any(
        "ensure_installation_namespaces.py" in command for command in commands
    )


@pytest.mark.parametrize(
    ("drift", "expected_error"),
    [
        ("server", "selected identity changed"),
        ("certificate-authority-data", "selected identity changed"),
        ("client-key-data", "selected identity changed"),
        ("namespace", "selected identity changed"),
        ("proxy-url", "selected cluster contains unsupported fields"),
        ("tls-server-name", "selected cluster contains unsupported fields"),
    ],
)
def test_flattened_kubeconfig_must_preserve_the_complete_selected_identity(
    tmp_path: Path,
    drift: str,
    expected_error: str,
) -> None:
    inputs = _inputs(
        tmp_path,
        "externalOidc",
        phase=MODULE.InstallationPhase.VALIDATE,
    )
    flattened = json.loads(inputs["kubeconfig"].read_text(encoding="utf-8"))
    if drift == "server":
        flattened["clusters"][0]["cluster"][drift] = "https://192.0.2.11:6443"
    elif drift == "certificate-authority-data":
        flattened["clusters"][0]["cluster"][drift] = "b3RoZXItY2E="
    elif drift == "client-key-data":
        flattened["users"][0]["user"][drift] = "b3RoZXIta2V5"
    elif drift == "namespace":
        flattened["contexts"][0]["context"][drift] = "other-system"
    elif drift == "proxy-url":
        flattened["clusters"][0]["cluster"][drift] = "https://proxy.example.test"
    else:
        flattened["clusters"][0]["cluster"][drift] = "api.example.test"
    runner = FakeRunner(
        flattened_kubeconfig=json.dumps(
            flattened,
            separators=(",", ":"),
            sort_keys=True,
        )
    )

    with pytest.raises(
        MODULE.InstallationError,
        match=expected_error,
    ):
        MODULE.install_rke2(**inputs, runner=runner)

    assert not any(
        "ensure_installation_namespaces.py" in command for command in _commands(runner)
    )


def test_private_input_change_during_same_descriptor_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    source = _private(private_root / "source", "first-value")
    real_read = MODULE.PRIVATE_INPUT.os.read
    changed = False

    def mutate_after_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        chunk = real_read(descriptor, size)
        if chunk and not changed:
            changed = True
            source.write_text("a-different-value", encoding="utf-8")
        return chunk

    monkeypatch.setattr(MODULE.PRIVATE_INPUT.os, "read", mutate_after_read)

    with pytest.raises(
        MODULE.PRIVATE_INPUT.PrivateInputError,
        match="changed while it was read",
    ):
        MODULE.PRIVATE_INPUT.read_private_bytes(
            source,
            "test input",
            private_root=private_root,
        )


def test_phase_snapshot_is_write_once_across_retries(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path, "externalOidc")
    MODULE.install_rke2(**inputs, runner=FakeRunner())
    original_snapshot = (
        inputs["work_directory"] / "snapshots/apps-tls.crt"
    ).read_bytes()
    inputs["apps_tls_cert"].write_text(
        "-----BEGIN CERTIFICATE-----\nchanged\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    retry_runner = FakeRunner()

    with pytest.raises(
        MODULE.InstallationError,
        match="Apps TLS certificate snapshot content changed",
    ):
        MODULE.install_rke2(**inputs, runner=retry_runner)

    assert (
        inputs["work_directory"] / "snapshots/apps-tls.crt"
    ).read_bytes() == original_snapshot
    assert not any(
        "ensure_installation_namespaces.py" in command
        for command in _commands(retry_runner)
    )
