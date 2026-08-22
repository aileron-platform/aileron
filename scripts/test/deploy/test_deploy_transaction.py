from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
COMMIT = "a" * 40


def _directory(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _private(path: Path, value: str = "fixture") -> Path:
    _directory(path.parent)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _executable(path: Path, content: str) -> Path:
    _directory(path.parent)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return path


def _prepare_direct_deploy(
    tmp_path: Path, *, identity_mode: str = "externalOidc"
) -> dict:
    repository = _directory(tmp_path / "repository")
    script_directory = _directory(repository / "scripts/deploy/rke2")
    for name in (
        "deploy.sh",
        "private_input.py",
        "installation_state.py",
        "installation_transaction.py",
        "namespace_contract.py",
    ):
        shutil.copy2(ROOT / "scripts/deploy/rke2" / name, script_directory / name)
    (script_directory / "deploy.sh").chmod(0o755)
    (script_directory / "private_input.py").chmod(0o755)

    event_log = tmp_path / "events.log"
    _executable(
        script_directory / "preflight.sh",
        "#!/bin/sh\n"
        "printf 'preflight\\n' >> \"$EVENT_LOG\"\n"
        '[ "${PREFLIGHT_FAIL:-0}" != 1 ]\n',
    )

    fake_bin = _directory(tmp_path / "bin")
    _executable(
        fake_bin / "git",
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['status', '--porcelain']:\n"
        "    raise SystemExit(0)\n"
        "if args[:2] == ['rev-parse', '--verify']:\n"
        "    print(os.environ['EXPECTED_COMMIT'])\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(97)\n",
    )
    _executable(
        fake_bin / "helm",
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "def event(value):\n"
        "    with open(os.environ['EVENT_LOG'], 'a', encoding='utf-8') as stream:\n"
        "        stream.write(value + '\\n')\n"
        "def events():\n"
        "    try:\n"
        "        with open(os.environ['EVENT_LOG'], encoding='utf-8') as stream:\n"
        "            return stream.read().splitlines()\n"
        "    except FileNotFoundError:\n"
        "        return []\n"
        "if 'list' in args:\n"
        "    namespace = args[args.index('--namespace') + 1]\n"
        "    if namespace == 'aileron-identity-system':\n"
        "        event('identity-list')\n"
        "        if os.environ['TEST_IDENTITY_MODE'] == 'bundledKeycloak':\n"
        "            print(json.dumps([{'name': 'aileron-identity', 'status': 'deployed'}]))\n"
        "        else:\n"
        "            print('[]')\n"
        "    else:\n"
        "        previous_events = events()\n"
        "        rollback_inventory = 'core-upgrade' in previous_events\n"
        "        event('core-list')\n"
        "        if os.environ.get('CORE_LIST_ERROR') == '1' and not rollback_inventory:\n"
        "            raise SystemExit(46)\n"
        "        release_exists = os.environ.get('EXISTING_CORE') == '1'\n"
        "        if rollback_inventory and os.environ.get('HELM_UPGRADE_FAIL') != '1':\n"
        "            release_exists = True\n"
        "        if release_exists:\n"
        "            print(json.dumps([{'name': 'aileron', 'status': 'deployed'}]))\n"
        "        else:\n"
        "            print('[]')\n"
        "    raise SystemExit(0)\n"
        "if 'history' in args:\n"
        "    event('core-history')\n"
        "    print(json.dumps([{'revision': '7', 'status': 'deployed'}]))\n"
        "    raise SystemExit(0)\n"
        "if 'upgrade' in args:\n"
        "    event('core-upgrade')\n"
        "    raise SystemExit(44 if os.environ.get('HELM_UPGRADE_FAIL') == '1' else 0)\n"
        "if 'rollback' in args:\n"
        "    event('core-rollback-' + args[args.index('aileron') + 1])\n"
        "    raise SystemExit(45 if os.environ.get('ROLLBACK_FAIL') == '1' else 0)\n"
        "if 'uninstall' in args:\n"
        "    event('core-uninstall')\n"
        "    raise SystemExit(45 if os.environ.get('ROLLBACK_FAIL') == '1' else 0)\n"
        "if 'get' in args and 'manifest' in args:\n"
        "    release = args[args.index('manifest') + 1]\n"
        "    if release == 'aileron-identity':\n"
        "        event('identity-manifest')\n"
        "        print('apiVersion: v1\\nkind: Service\\nmetadata: {name: identity}')\n"
        "    else:\n"
        "        event('core-manifest')\n"
        "        print('apiVersion: networking.k8s.io/v1\\nkind: Ingress\\nmetadata: {name: aileron, namespace: workspace-system}')\n"
        "    raise SystemExit(0)\n"
        "if 'get' in args and 'hooks' in args:\n"
        "    event('identity-hooks')\n"
        "    print('apiVersion: batch/v1\\nkind: Job\\nmetadata: {name: bootstrap, annotations: {helm.sh/hook: post-install}}')\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(97)\n",
    )
    _executable(
        fake_bin / "kubectl",
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "def event(value):\n"
        "    with open(os.environ['EVENT_LOG'], 'a', encoding='utf-8') as stream:\n"
        "        stream.write(value + '\\n')\n"
        "def events():\n"
        "    try:\n"
        "        with open(os.environ['EVENT_LOG'], encoding='utf-8') as stream:\n"
        "            return stream.read().splitlines()\n"
        "    except FileNotFoundError:\n"
        "        return []\n"
        "if 'get' in args and 'customresourcedefinition' in args:\n"
        "    event('crd-get')\n"
        "    after_apply = 'core-crd-apply' in events()\n"
        "    if after_apply or os.environ.get('EXISTING_CRD') == '1':\n"
        "        recreated = after_apply and os.environ.get('CRD_RECREATE_AFTER_APPLY') == '1'\n"
        "        uid = 'crd-external' if recreated else ('crd-old' if os.environ.get('EXISTING_CRD') == '1' else 'crd-new')\n"
        "        version = '22' if after_apply else '10'\n"
        "        marker = 'original' if not after_apply or os.environ.get('CRD_RECREATE_SEMANTIC_SAME') == '1' else 'desired'\n"
        "        print(json.dumps({'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition', 'metadata': {'name': 'workspaces.platform.aileron.io', 'uid': uid, 'resourceVersion': version}, 'spec': {'marker': marker}}))\n"
        "    raise SystemExit(0)\n"
        "if 'apply' in args:\n"
        "    event('core-crd-apply')\n"
        "    raise SystemExit(48 if os.environ.get('CRD_APPLY_FAIL') == '1' else 0)\n"
        "if 'delete' in args and '--raw' in args:\n"
        "    options = json.loads(Path(args[args.index('--filename') + 1]).read_text(encoding='utf-8'))\n"
        "    event('crd-delete')\n"
        "    valid = options.get('preconditions') == {'uid': 'crd-new', 'resourceVersion': '22'}\n"
        "    raise SystemExit(0 if valid and os.environ.get('CRD_RECOVERY_FAIL') != '1' else 55)\n"
        "if ('replace' in args or 'create' in args) and '--filename' in args:\n"
        "    manifest = json.loads(Path(args[args.index('--filename') + 1]).read_text(encoding='utf-8'))\n"
        "    event('crd-replace' if 'replace' in args else 'crd-create')\n"
        "    valid = '--force' not in args and (('create' in args) or manifest.get('metadata', {}).get('resourceVersion') == '22')\n"
        "    raise SystemExit(0 if valid and os.environ.get('CRD_RECOVERY_FAIL') != '1' else 55)\n"
        "if 'get' in args and 'secret' in args:\n"
        "    event('core-tls-secret')\n"
        "    print('Zml4dHVyZQ==', end='')\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(97)\n",
    )
    _executable(
        fake_bin / "jq",
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "query = ' '.join(sys.argv[1:-1])\n"
        "with open(sys.argv[-1], encoding='utf-8') as stream:\n"
        "    value = json.load(stream)\n"
        "if 'then length' in query:\n"
        "    print(len(value))\n"
        "elif '| max' in query:\n"
        "    deployed = [int(row['revision']) for row in value if row.get('status') == 'deployed']\n"
        "    if not deployed:\n"
        "        raise SystemExit(1)\n"
        "    print(max(deployed))\n"
        "elif 'length == 0' in query:\n"
        "    raise SystemExit(0 if isinstance(value, list) and len(value) == 0 else 1)\n"
        "elif 'length == 1' in query and 'aileron-identity' in query:\n"
        "    valid = len(value) == 1 and value[0].get('name') == 'aileron-identity' and value[0].get('status') == 'deployed'\n"
        "    raise SystemExit(0 if valid else 1)\n"
        "elif '.[0].name == \"aileron\"' in query:\n"
        "    raise SystemExit(0 if len(value) == 1 and value[0].get('name') == 'aileron' else 1)\n"
        "else:\n"
        "    raise SystemExit(97)\n",
    )
    _executable(
        fake_bin / "python3",
        f"#!{sys.executable}\n"
        "import importlib.util, os, sys\n"
        "from pathlib import Path\n"
        "target = Path(sys.argv[1])\n"
        "name = target.name\n"
        "def event(value):\n"
        "    with open(os.environ['EVENT_LOG'], 'a', encoding='utf-8') as stream:\n"
        "        stream.write(value + '\\n')\n"
        "if name == 'private_input.py':\n"
        "    specification = importlib.util.spec_from_file_location('direct_private_input', target)\n"
        "    assert specification and specification.loader\n"
        "    module = importlib.util.module_from_spec(specification)\n"
        "    specification.loader.exec_module(module)\n"
        "    module.INSTALLATION_STATE.PRIVATE_ROOT = Path(os.environ['TEST_PRIVATE_ROOT'])\n"
        "    sys.argv = sys.argv[1:]\n"
        "    raise SystemExit(module.main())\n"
        "if name == 'installation_transaction.py':\n"
        "    if (os.environ.get('RESULT_WRITE_FAIL_ON_SUCCESS') == '1'\n"
        "            and len(sys.argv) > 2\n"
        "            and sys.argv[2] == 'write-core-result'\n"
        "            and sys.argv[sys.argv.index('--primary-exit-code') + 1] == '0'):\n"
        "        event('core-result-success-write-failed')\n"
        "        raise SystemExit(61)\n"
        "    specification = importlib.util.spec_from_file_location('direct_installation_transaction', target)\n"
        "    assert specification and specification.loader\n"
        "    module = importlib.util.module_from_spec(specification)\n"
        "    specification.loader.exec_module(module)\n"
        "    module.INSTALLATION_STATE.PRIVATE_ROOT = Path(os.environ['TEST_PRIVATE_ROOT'])\n"
        "    sys.argv = sys.argv[1:]\n"
        "    raise SystemExit(module.main())\n"
        "if name == 'wait_for_oidc.py':\n"
        "    event('oidc-readiness')\n"
        "    raise SystemExit(1 if os.environ.get('OIDC_FAIL') == '1' else 0)\n"
        "if name == 'ensure_installation_namespaces.py':\n"
        "    event('namespace-ensure')\n"
        "    raise SystemExit(0)\n"
        "if name == 'preflight_manifest.py':\n"
        "    action = sys.argv[2]\n"
        "    if action == 'assert-equivalent-manifests':\n"
        "        event('identity-attestation')\n"
        "        raise SystemExit(1 if os.environ.get('IDENTITY_DRIFT') == '1' else 0)\n"
        "    if action == 'ingress-tls-secret':\n"
        "        print('workspace-system\\taileron-apps-tls')\n"
        "        raise SystemExit(0)\n"
        "raise SystemExit(97)\n",
    )
    _executable(
        fake_bin / "getent",
        "#!/bin/sh\n"
        '[ "${POSTCHECK_FAIL:-0}" != 1 ] || exit 49\n'
        "printf '192.0.2.1 STREAM fixture\\n'\n",
    )
    _executable(
        fake_bin / "openssl",
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  x509) printf 'SHA256 Fingerprint=AA\\n' ;;\n"
        "  s_client) printf '%s\\n' '-----BEGIN CERTIFICATE-----' fixture '-----END CERTIFICATE-----' ;;\n"
        "  *) exit 97 ;;\n"
        "esac\n",
    )

    private_root = _directory(tmp_path / "private")
    snapshots = _directory(private_root / "install" / COMMIT / "snapshots")
    values = _private(snapshots / "core-values.json", "{}\n")
    identity_manifest = _private(
        snapshots / "identity-rendered.yaml",
        "apiVersion: v1\nkind: Service\nmetadata: {name: identity}\n",
    )
    kubeconfig = _private(private_root / "inputs/kubeconfig")
    dockerconfig = _private(private_root / "inputs/dockerconfig.json", "{}\n")
    apps_tls = _private(private_root / "inputs/apps-tls.crt")
    oidc_ca = _private(private_root / "inputs/oidc-ca.crt")
    install_secrets = _directory(private_root / "install-secrets")
    homelab_secrets = _directory(install_secrets / "homelab")
    platform_artifacts = _directory(homelab_secrets / "platform-artifacts")
    install_root = _directory(private_root / "install")
    install_work = _directory(install_root / COMMIT)
    install_transactions = _directory(install_work / "transactions")
    installer_transaction = _directory(
        install_transactions / "install.0123456789abcdef"
    )
    result_sidecar = _private(
        installer_transaction / "core-deploy-result.json",
        "{"
        f'"commit":"{COMMIT}",'
        '"schemaVersion":"aileron-core-deployment-result/v1",'
        '"state":"pending"}\n',
    )

    command = [
        str(script_directory / "deploy.sh"),
        "--commit",
        COMMIT,
        "--registry",
        "harbor.example.test",
        "--project",
        "library",
        "--values",
        str(values),
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        "rke",
        "--namespace",
        "workspace-system",
        "--identity-mode",
        identity_mode,
        "--harbor-dockerconfig",
        str(dockerconfig),
        "--apps-tls-cert",
        str(apps_tls),
        "--oidc-issuer",
        (
            "https://keycloak.apps.rke.soez.tw/realms/aileron"
            if identity_mode == "bundledKeycloak"
            else "https://auth.example.test/o/aileron/"
        ),
        "--oidc-ca",
        str(oidc_ca),
        "--platform-artifacts",
        str(platform_artifacts),
        "--result-sidecar",
        str(result_sidecar),
    ]
    if identity_mode == "bundledKeycloak":
        command.extend(["--identity-manifest", str(identity_manifest)])

    return {
        "command": command,
        "repository": repository,
        "event_log": event_log,
        "fake_bin": fake_bin,
        "private_root": private_root,
        "kubeconfig": kubeconfig,
        "result_sidecar": result_sidecar,
        "environment": {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "EVENT_LOG": str(event_log),
            "EXPECTED_COMMIT": COMMIT,
            "TEST_IDENTITY_MODE": identity_mode,
            "TEST_PRIVATE_ROOT": str(private_root),
        },
    }


def _run(fixture: dict, **environment: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        fixture["command"],
        cwd=fixture["repository"],
        env={**fixture["environment"], **environment},
        capture_output=True,
        check=False,
        text=True,
    )


def _events(fixture: dict) -> list[str]:
    event_log = fixture["event_log"]
    if not event_log.exists():
        return []
    return event_log.read_text(encoding="utf-8").splitlines()


def _result(fixture: dict) -> dict:
    path = fixture["result_sidecar"]
    assert path.stat().st_mode & 0o777 == 0o600
    return json.loads(path.read_text(encoding="utf-8"))


def test_direct_deploy_runs_fresh_preflight_before_valid_core_install(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(fixture)

    assert completed.returncode == 0, completed.stderr
    assert "core-stage=passed" in completed.stdout
    events = _events(fixture)
    assert events.index("oidc-readiness") < events.index("preflight")
    assert events.index("preflight") < events.index("namespace-ensure")
    assert events.index("namespace-ensure") < events.index("core-crd-apply")
    assert events.index("core-crd-apply") < events.index("core-upgrade")
    assert "core-uninstall" not in events
    assert _result(fixture) == {
        "schemaVersion": "aileron-core-deployment-result/v1",
        "state": "completed",
        "commit": COMMIT,
        "primaryExitCode": 0,
        "coreRollbackAttempted": False,
        "coreRollbackSucceeded": False,
    }


@pytest.mark.parametrize("existing_release", [False, True])
def test_direct_deploy_rolls_back_any_post_helm_failure(
    tmp_path: Path,
    existing_release: bool,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(
        fixture,
        POSTCHECK_FAIL="1",
        EXISTING_CORE="1" if existing_release else "0",
        EXISTING_CRD="1" if existing_release else "0",
    )

    assert completed.returncode == 1
    events = _events(fixture)
    assert "core-upgrade" in events
    expected_rollback = "core-rollback-7" if existing_release else "core-uninstall"
    expected_crd_recovery = "crd-replace" if existing_release else "crd-delete"
    assert events.index("core-upgrade") < events.index(expected_rollback)
    assert events.index(expected_rollback) < events.index(expected_crd_recovery)
    result = _result(fixture)
    assert result["primaryExitCode"] == 1
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is True


def test_direct_deploy_reports_failed_core_rollback_without_hiding_primary_exit(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(fixture, POSTCHECK_FAIL="1", ROLLBACK_FAIL="1")

    assert completed.returncode == 1
    result = _result(fixture)
    assert result["primaryExitCode"] == completed.returncode
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is False
    serialized = completed.stdout + completed.stderr + json.dumps(result)
    assert "private" not in serialized


def test_direct_deploy_rolls_back_when_success_result_cannot_be_recorded(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(fixture, RESULT_WRITE_FAIL_ON_SUCCESS="1")

    assert completed.returncode == 1
    events = _events(fixture)
    assert events.index("core-upgrade") < events.index(
        "core-result-success-write-failed"
    )
    assert events.index("core-result-success-write-failed") < events.index(
        "core-uninstall"
    )
    result = _result(fixture)
    assert result["primaryExitCode"] == 1
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is True
    assert "core-stage=passed" not in completed.stdout


def test_direct_deploy_accepts_atomic_cleanup_of_failed_fresh_install(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(fixture, HELM_UPGRADE_FAIL="1")

    assert completed.returncode == 1
    events = _events(fixture)
    assert events.count("core-list") == 2
    assert "core-upgrade" in events
    assert "core-uninstall" not in events
    result = _result(fixture)
    assert result["primaryExitCode"] == 1
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is True


@pytest.mark.parametrize("existing_release", [False, True])
def test_direct_deploy_recovers_only_crd_when_apply_reports_partial_failure(
    tmp_path: Path, existing_release: bool
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(
        fixture,
        CRD_APPLY_FAIL="1",
        EXISTING_CORE="1" if existing_release else "0",
        EXISTING_CRD="1" if existing_release else "0",
    )

    assert completed.returncode == 1
    events = _events(fixture)
    assert events.index("crd-get") < events.index("core-crd-apply")
    expected_recovery = "crd-replace" if existing_release else "crd-delete"
    assert events.index("core-crd-apply") < events.index(expected_recovery)
    assert "core-upgrade" not in events
    assert not any(event.startswith("core-rollback-") for event in events)
    assert "core-uninstall" not in events
    result = _result(fixture)
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is True


@pytest.mark.parametrize("existing_crd", [False, True])
def test_direct_deploy_reports_crd_cas_recovery_failure_as_core_rollback_failure(
    tmp_path: Path,
    existing_crd: bool,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(
        fixture,
        POSTCHECK_FAIL="1",
        CRD_RECOVERY_FAIL="1",
        EXISTING_CRD="1" if existing_crd else "0",
    )

    assert completed.returncode == 1
    events = _events(fixture)
    assert "core-uninstall" in events
    expected_event = "crd-replace" if existing_crd else "crd-delete"
    assert expected_event in events
    result = _result(fixture)
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is False
    transactions = list((fixture["private_root"] / "transactions").iterdir())
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction.stat().st_mode & 0o777 == 0o700
    inventory_path = transaction / "workspace-crd-transaction.json"
    assert inventory_path.stat().st_mode & 0o777 == 0o600
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory["state"] == ("existing" if existing_crd else "absent")
    if existing_crd:
        restore = json.loads(
            (transaction / "workspace-crd-restore.json").read_text(encoding="utf-8")
        )
        assert restore["metadata"]["resourceVersion"] == "22"
        assert restore["spec"] == {"marker": "original"}
    else:
        options = json.loads(
            (transaction / "workspace-crd-delete-options.json").read_text(
                encoding="utf-8"
            )
        )
        assert options["preconditions"] == {
            "uid": "crd-new",
            "resourceVersion": "22",
        }


def test_existing_crd_uid_change_fails_before_semantic_accept_or_replace(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(
        fixture,
        POSTCHECK_FAIL="1",
        EXISTING_CORE="1",
        EXISTING_CRD="1",
        CRD_RECREATE_AFTER_APPLY="1",
        CRD_RECREATE_SEMANTIC_SAME="1",
    )

    assert completed.returncode == 1
    events = _events(fixture)
    assert "core-rollback-7" in events
    assert "crd-replace" not in events
    result = _result(fixture)
    assert result["coreRollbackAttempted"] is True
    assert result["coreRollbackSucceeded"] is False
    transactions = list((fixture["private_root"] / "transactions").iterdir())
    assert len(transactions) == 1
    transaction = transactions[0]
    current = json.loads(
        (transaction / "workspace-crd-current.json").read_text(encoding="utf-8")
    )
    assert current["metadata"]["uid"] == "crd-external"
    assert not (transaction / "workspace-crd-restore.json").exists()


def test_direct_deploy_treats_core_inventory_error_as_failure_not_not_found(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)

    completed = _run(fixture, CORE_LIST_ERROR="1")

    assert completed.returncode == 1
    events = _events(fixture)
    assert "core-list" in events
    assert "core-crd-apply" not in events
    assert "core-upgrade" not in events
    assert "core-uninstall" not in events
    result = _result(fixture)
    assert result["primaryExitCode"] == 1
    assert result["coreRollbackAttempted"] is False
    assert result["coreRollbackSucceeded"] is False


@pytest.mark.parametrize("failure", ["mode", "symlink", "ancestor-symlink"])
def test_direct_deploy_rejects_insecure_kubeconfig_before_preflight_or_mutation(
    tmp_path: Path,
    failure: str,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path)
    kubeconfig = fixture["kubeconfig"]
    if failure == "mode":
        kubeconfig.chmod(0o644)
    elif failure == "symlink":
        target = _private(fixture["private_root"] / "inputs/kubeconfig-target")
        kubeconfig.unlink()
        kubeconfig.symlink_to(target)
    else:
        real_parent = _directory(fixture["private_root"] / "real-inputs")
        target = _private(real_parent / "kubeconfig")
        linked_parent = fixture["private_root"] / "linked-inputs"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        index = fixture["command"].index("--kubeconfig") + 1
        fixture["command"][index] = str(linked_parent / target.name)

    completed = _run(fixture)

    assert completed.returncode == 1
    assert _events(fixture) == []


def test_direct_deploy_rejects_live_identity_drift_before_core_preflight(
    tmp_path: Path,
) -> None:
    fixture = _prepare_direct_deploy(tmp_path, identity_mode="bundledKeycloak")

    completed = _run(fixture, IDENTITY_DRIFT="1")

    assert completed.returncode == 1
    events = _events(fixture)
    assert "identity-attestation" in events
    assert "oidc-readiness" not in events
    assert "preflight" not in events
    assert "core-crd-apply" not in events
    assert "core-upgrade" not in events
