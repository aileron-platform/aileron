from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "workspace-manager/scripts/acceptance_transport_probe.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "acceptance_transport_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_turn_rest_probe_derives_expiring_credential_from_shared_secret(
    tmp_path: Path,
) -> None:
    module = _load_module()
    username_file = tmp_path / "probe-username"
    shared_secret_file = tmp_path / "turn-rest-shared-secret"
    username_file.write_text("aileron-probe\n", encoding="utf-8")
    shared_secret_file.write_text("shared-secret\n", encoding="utf-8")

    username, credential = module._issue_turn_rest_credentials(
        str(username_file),
        str(shared_secret_file),
        identity_suffix="frontend",
        now=1_700_000_000,
    )

    expected_username = "1700000300:aileron-probe:frontend"
    expected_credential = base64.b64encode(
        hmac.new(
            b"shared-secret", expected_username.encode(), hashlib.sha1
        ).digest()
    ).decode("ascii")
    assert username == expected_username
    assert credential == expected_credential


def test_turn_rest_probe_requires_regular_secret_files(tmp_path: Path) -> None:
    module = _load_module()
    username_file = tmp_path / "probe-username"
    shared_secret_file = tmp_path / "turn-rest-shared-secret"
    username_file.write_text("aileron-probe\n", encoding="utf-8")
    shared_secret_file.write_text("shared-secret\n", encoding="utf-8")
    shared_secret_file.chmod(0o600)

    shared_secret_file.unlink()

    try:
        module._issue_turn_rest_credentials(
            str(username_file),
            str(shared_secret_file),
            now=1_700_000_000,
        )
    except SystemExit as exc:
        assert str(exc) == "fixed TURN credential input is invalid: TURN REST shared secret"
    else:
        raise AssertionError("missing TURN REST shared secret must fail closed")


def test_turn_probe_requests_verbose_relay_output(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    username_file = tmp_path / "probe-username"
    shared_secret_file = tmp_path / "turn-rest-shared-secret"
    username_file.write_text("aileron-probe\n", encoding="utf-8")
    shared_secret_file.write_text("shared-secret\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout="0: : IPv4. Received relay addr: 192.168.50.10\n",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    output = module._turn(
        "turn.apps.rke.soez.tw",
        "frontend",
        str(username_file),
        str(shared_secret_file),
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert "-t" in command
    assert "-y" in command
    assert "-v" in command
    assert "relay" in output.lower()
