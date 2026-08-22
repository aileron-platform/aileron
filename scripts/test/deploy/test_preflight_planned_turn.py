"""External TURN planned-artifact preflight behavior tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT = ROOT / "scripts" / "deploy" / "rke2" / "preflight.sh"
COMMIT = "a" * 40


def _private_file(path: Path, value: str) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _executable(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)
    return path


def _command_stubs(tmp_path: Path) -> Path:
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir(mode=0o700)
    _executable(
        bin_directory / "git",
        f"""#!/bin/sh
case "$*" in
  *"status --porcelain"*) exit 0 ;;
  *"rev-parse --verify HEAD"*) printf '%s\\n' '{COMMIT}' ;;
  *"ls-files --error-unmatch"*) exit 1 ;;
  *) exit 0 ;;
esac
""",
    )
    _executable(bin_directory / "uname", "#!/bin/sh\nprintf 'x86_64\\n'\n")
    _executable(bin_directory / "docker", "#!/bin/sh\nexit 0\n")
    _executable(
        bin_directory / "getent",
        "#!/bin/sh\nprintf '192.0.2.10 STREAM %s\\n' \"${2:-host}\"\n",
    )
    _executable(
        bin_directory / "helm",
        """#!/bin/sh
case "$*" in
  *"version --template"*) printf 'v3.21.3\\n' ;;
  *"upgrade --help"*) printf '%s\\n' '--atomic --dry-run=server --history-max' ;;
  *"rollback --help"*) printf '%s\\n' '--cleanup-on-fail' ;;
  *"list --all"*) printf '[]\\n' ;;
  *"template aileron"*)
    cat <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: planned-core
data:
  frontendHost: aileron.apps.rke.soez.tw
EOF
    ;;
esac
""",
    )
    _executable(
        bin_directory / "kubectl",
        """#!/bin/sh
case "$*" in
  *"get secret"*) exit 93 ;;
  *"config current-context"*) printf 'rke\\n' ;;
  *"get nodes -o jsonpath="*) printf 'node-one|True\\nnode-two|True\\n' ;;
  *"get storageclass aileron-nfs-rwx-delete"*)
    printf 'nfs.csi.k8s.io|Delete|Immediate\\n' ;;
  *"get storageclass aileron-nfs-rwx-retain"*)
    printf 'nfs.csi.k8s.io|Retain|Immediate\\n' ;;
  *"get storageclass aileron-local-rwo-delete"*)
    printf 'rancher.io/local-path|Delete|WaitForFirstConsumer\\n' ;;
  *"get storageclass aileron-local-rwo-retain"*)
    printf 'rancher.io/local-path|Retain|WaitForFirstConsumer\\n' ;;
  *"get nodes"*) printf '{"items":[]}\\n' ;;
  *"get pods"*) printf '{"items":[]}\\n' ;;
  *"get namespace aileron-backend-attestor-system"*)
    : > "${BACKEND_NAMESPACE_MARKER}"
    [ "${BACKEND_NAMESPACE_FAIL:-0}" = 0 ] || exit 92
    printf '{"metadata":{}}\\n' ;;
  *"get namespace"*) printf '{"metadata":{}}\\n' ;;
esac
exit 0
""",
    )
    _executable(
        bin_directory / "jq",
        """#!/bin/sh
case " $* " in
  *" -n "*) printf '{}\\n' ;;
  *) printf '3\\n' ;;
esac
""",
    )
    _executable(
        bin_directory / "openssl",
        """#!/bin/sh
case "$*" in
  *"-ext subjectAltName"*)
    printf 'X509v3 Subject Alternative Name: DNS:*.apps.rke.soez.tw\\n' ;;
esac
""",
    )
    _executable(
        bin_directory / "python3",
        """#!/bin/sh
case "${2:-}" in
  validate-version) printf '3.21.3\\n' ;;
  release-mode) printf 'clean-install\\n' ;;
  image-pull-secrets) printf 'workspace-system\\tharbor-rke-creds\\n' ;;
  validate-image-pull-secret) printf 'true\\n' ;;
  validate-execution-plane-capacity) printf 'capacity=passed\\n' ;;
  named-images) : ;;
  ingress-tls-secret) printf 'workspace-system\\taileron-apps-tls\\n' ;;
  turn-provider) printf 'external\\n' ;;
  validate-privileged-namespace)
    case "${3:-}" in
      *backend-attestor-namespace.json)
        [ "${BACKEND_NAMESPACE_PROFILE_FAIL:-0}" = 0 ] || exit 94 ;;
    esac ;;
esac
""",
    )
    return bin_directory


def _run_preflight(
    tmp_path: Path,
    platform_artifacts: Path,
    *,
    backend_namespace_fail: bool = False,
    backend_namespace_profile_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_directory = _command_stubs(tmp_path)
    values = _private_file(tmp_path / "private" / "core-values.json", "{}\n")
    dockerconfig = _private_file(
        tmp_path / "private" / "dockerconfig.json",
        '{"auths":{"harbor.example.test":{"auth":"dGVzdA=="}}}\n',
    )
    tls_certificate = _private_file(
        tmp_path / "private" / "apps-tls.crt",
        "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n",
    )
    kubeconfig = _private_file(tmp_path / "private" / "kubeconfig", "context\n")
    marker = tmp_path / "turn-preflight-ran"
    backend_namespace_marker = tmp_path / "backend-namespace-inspected"
    reachability = _executable(
        tmp_path / "turn-reachability.sh",
        '#!/bin/sh\n: > "${TURN_MARKER}"\n',
    )
    evidence = tmp_path / "evidence"
    environment = {
        **os.environ,
        "PATH": f"{bin_directory}:{os.environ['PATH']}",
        "IDENTITY_MODE": "externalOidc",
        "TURN_PREFLIGHT_SCRIPT": str(reachability),
        "TURN_MARKER": str(marker),
        "BACKEND_NAMESPACE_MARKER": str(backend_namespace_marker),
        "BACKEND_NAMESPACE_FAIL": "1" if backend_namespace_fail else "0",
        "BACKEND_NAMESPACE_PROFILE_FAIL": (
            "1" if backend_namespace_profile_fail else "0"
        ),
        "MIN_FREE_DISK_KIB": "0",
        "MIN_AMD64_WORKERS": "3",
        "BASE_DOMAIN": "apps.rke.soez.tw",
        "EVIDENCE_ROOT": str(evidence),
    }
    command = [
        str(PREFLIGHT),
        "--commit",
        COMMIT,
        "--registry",
        "harbor.example.test",
        "--project",
        "aileron",
        "--values",
        str(values),
        "--harbor-dockerconfig",
        str(dockerconfig),
        "--apps-tls-cert",
        str(tls_certificate),
        "--platform-artifacts",
        str(platform_artifacts),
        "--context",
        "rke",
        "--kubeconfig",
        str(kubeconfig),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed


def _planned_turn_artifacts(tmp_path: Path) -> Path:
    artifacts = tmp_path / "private" / "platform-artifacts"
    artifacts.mkdir(mode=0o700, parents=True)
    _private_file(
        artifacts / "turn" / "backend-ice-servers-json",
        '[{"urls":["turn:turn.example.test:3478"]}]\n',
    )
    _private_file(
        artifacts / "turn" / "frontend-ice-servers-json",
        '[{"urls":["turns:turn.example.test:5349"]}]\n',
    )
    return artifacts


def test_external_turn_uses_planned_artifacts_without_live_secret(
    tmp_path: Path,
) -> None:
    artifacts = _planned_turn_artifacts(tmp_path)

    completed = _run_preflight(tmp_path, artifacts)

    assert completed.returncode == 0, completed.stderr
    assert "preflight=passed" in completed.stdout
    assert (tmp_path / "turn-preflight-ran").is_file()
    assert (tmp_path / "backend-namespace-inspected").is_file()


@pytest.mark.parametrize(
    ("missing", "profile_drift", "expected_error"),
    [
        (True, False, "unable to inspect the retained backend-attestor namespace"),
        (
            False,
            True,
            "backend-attestor namespace ownership or privileged PSA contract is invalid",
        ),
    ],
)
def test_preflight_requires_exact_retained_backend_attestor_namespace(
    tmp_path: Path,
    missing: bool,
    profile_drift: bool,
    expected_error: str,
) -> None:
    artifacts = _planned_turn_artifacts(tmp_path)

    completed = _run_preflight(
        tmp_path,
        artifacts,
        backend_namespace_fail=missing,
        backend_namespace_profile_fail=profile_drift,
    )

    assert completed.returncode == 1
    assert expected_error in completed.stderr
    assert (tmp_path / "backend-namespace-inspected").is_file()
    assert not (tmp_path / "turn-preflight-ran").exists()


@pytest.mark.parametrize(
    ("violation", "expected_error"),
    [
        ("missing", "must be a regular file"),
        ("empty", "must not be empty"),
        ("mode", "permissions must be 0600"),
        ("file-symlink", "must not be a symbolic link"),
        ("ancestor-symlink", "path must not contain a symbolic link"),
    ],
)
def test_external_turn_rejects_untrusted_planned_artifacts_before_reachability(
    tmp_path: Path,
    violation: str,
    expected_error: str,
) -> None:
    artifacts = _planned_turn_artifacts(tmp_path)
    backend = artifacts / "turn" / "backend-ice-servers-json"
    frontend = artifacts / "turn" / "frontend-ice-servers-json"
    if violation == "missing":
        backend.unlink()
    elif violation == "empty":
        frontend.write_bytes(b"")
    elif violation == "mode":
        backend.chmod(0o640)
    elif violation == "file-symlink":
        target = _private_file(tmp_path / "private" / "outside-backend", "[]\n")
        backend.unlink()
        backend.symlink_to(target)
    elif violation == "ancestor-symlink":
        real_turn = tmp_path / "private" / "real-turn"
        (artifacts / "turn").rename(real_turn)
        (artifacts / "turn").symlink_to(real_turn, target_is_directory=True)

    completed = _run_preflight(tmp_path, artifacts)

    assert completed.returncode == 1
    assert expected_error in completed.stderr
    assert not (tmp_path / "turn-preflight-ran").exists()
