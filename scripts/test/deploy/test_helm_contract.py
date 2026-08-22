from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "helm_contract.py"
)
SPEC = importlib.util.spec_from_file_location("helm_contract", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("v3.13.0", (3, 13, 0)),
        ("3.21.3", (3, 21, 3)),
        ("v3.21.3+g1234567", (3, 21, 3)),
    ],
)
def test_supported_helm_version(value: str, expected: tuple[int, int, int]) -> None:
    assert MODULE.validate_version(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "v3.12.9",
        "v3.13.0-rc.1",
        "v4.0.0",
        "v4.1.3",
        "latest",
    ],
)
def test_unsupported_helm_version_fails_closed(value: str) -> None:
    with pytest.raises(ValueError, match="Helm version"):
        MODULE.validate_version(value)


def test_release_mode_distinguishes_clean_install_and_upgrade() -> None:
    assert (
        MODULE.release_deployment_mode(
            [],
            namespace="workspace-system",
            release="aileron",
        )
        == "clean-install"
    )
    assert (
        MODULE.release_deployment_mode(
            [{"name": "aileron", "namespace": "workspace-system"}],
            namespace="workspace-system",
            release="aileron",
        )
        == "upgrade"
    )


@pytest.mark.parametrize(
    "inventory",
    [
        {},
        [{"name": "other", "namespace": "workspace-system"}],
        [{"name": "aileron", "namespace": "other"}],
        [
            {"name": "aileron", "namespace": "workspace-system"},
            {"name": "aileron", "namespace": "workspace-system"},
        ],
    ],
)
def test_release_mode_rejects_ambiguous_inventory(inventory: object) -> None:
    with pytest.raises(ValueError, match="Helm release inventory"):
        MODULE.release_deployment_mode(
            inventory,
            namespace="workspace-system",
            release="aileron",
        )
