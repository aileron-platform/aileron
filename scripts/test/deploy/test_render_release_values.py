"""Immutable release inventory to Helm override contract tests."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest
import yaml

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "render_release_values.py"
)
SPEC = importlib.util.spec_from_file_location("render_release_values", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
IMAGE_CONTRACT = ROOT / "scripts/deploy/rke2/image-release-contract.json"
VALUES_CONTRACT = ROOT / "scripts/deploy/rke2/release-values-contract.json"
COMMIT = "a" * 40
DIGEST = "b" * 64


def _inventory(
    path: Path, *, omit: str | None = None, duplicate: str | None = None
) -> None:
    components = json.loads(IMAGE_CONTRACT.read_text())["publishedComponents"]
    rows = []
    for index, component in enumerate(components):
        if component == omit:
            continue
        repository = f"harbor.example.test/library/{component}"
        digest = f"{index + 1:064x}"
        rows.append(
            f"{component}\t{COMMIT}\tlinux/amd64\t{repository}:git-{COMMIT}\t"
            f"{repository}@sha256:{digest}\t"
            f"{repository}@sha256:{index + 101:064x}\n"
        )
        if component == duplicate:
            rows.append(rows[-1])
    path.write_text("".join(rows), encoding="utf-8")


def test_bundled_renderer_writes_exact_core_and_identity_values(tmp_path: Path) -> None:
    inventory = tmp_path / "images.tsv"
    output = tmp_path / "values"
    _inventory(inventory)

    result = MODULE.render_release_values(
        inventory_path=inventory,
        expected_commit=COMMIT,
        expected_registry="harbor.example.test",
        expected_project="library",
        identity_mode="bundledKeycloak",
        output_directory=output,
        image_contract_path=IMAGE_CONTRACT,
        values_contract_path=VALUES_CONTRACT,
    )

    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert result.core_path == output / "core-values.json"
    assert result.identity_path == output / "identity-values.json"
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in output.iterdir())
    core = json.loads(result.core_path.read_text())
    identity = json.loads(result.identity_path.read_text())
    assert core["frontend"]["image"]["repository"].endswith("/workspace-ui")
    assert core["workspaceOperator"]["runtimeImage"]["repository"].endswith(
        "/workspace-runtime"
    )
    assert core["postgres"]["image"]["repository"].endswith("/platform-postgres")
    assert identity["images"]["postgres"] == {
        "repository": core["postgres"]["image"]["repository"],
        "digest": core["postgres"]["image"]["digest"],
    }
    assert identity["images"]["keycloak"]["repository"].endswith("/platform-keycloak")
    assert core["oidc"] == {
        "issuerUrl": "https://keycloak.apps.rke.soez.tw/realms/aileron",
        "clientId": "aileron-frontend",
        "clientSecretName": "aileron-oidc-client",
        "clientSecretKey": "client-secret",
        "caSecretName": "aileron-oidc-ca",
        "caSecretKey": "ca.crt",
    }
    assert identity["issuerUrl"] == core["oidc"]["issuerUrl"]
    assert identity["clientId"] == core["oidc"]["clientId"]
    assert identity["platformCallbackUrl"] == (
        "https://aileron.apps.rke.soez.tw/api/v1/oauth2/callback"
    )
    assert identity["ingress"]["public"]["hostname"] == "keycloak.apps.rke.soez.tw"
    assert all(
        image["tag"] == ""
        for image in (
            core["frontend"]["image"],
            core["workspaceManager"]["image"],
            core["workspaceOperator"]["image"],
            core["workspaceOperator"]["runtimeImage"],
            core["kubernetes"]["browserImage"],
            core["kubernetes"]["canvasImage"],
            core["postgres"]["image"],
            core["redis"]["image"],
            core["coturn"]["image"],
        )
    )


@pytest.mark.parametrize("boundary", ["output-directory", "output-file"])
def test_renderer_rejects_mode_correct_output_owned_by_another_uid(
    tmp_path: Path,
    boundary: str,
) -> None:
    if os.geteuid() != 0:
        pytest.skip("ownership regression requires the root deployment container")
    inventory = tmp_path / "images.tsv"
    output = tmp_path / "values"
    _inventory(inventory)
    output.mkdir(mode=0o700)
    target = output
    if boundary == "output-file":
        target = output / "core-values.json"
        target.write_text("{}\n", encoding="utf-8")
        target.chmod(0o600)
    os.chown(target, 65532, 65532)

    with pytest.raises(ValueError, match="owner-controlled"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=output,
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
        )


def test_release_contract_converges_with_both_tracked_homelab_profiles() -> None:
    contract = json.loads(VALUES_CONTRACT.read_text())
    assert contract["components"] == {
        "platform-coturn": [{"target": "core", "path": ["coturn", "image"]}],
        "platform-keycloak": [{"target": "identity", "path": ["images", "keycloak"]}],
        "platform-postgres": [
            {"target": "core", "path": ["postgres", "image"]},
            {"target": "identity", "path": ["images", "postgres"]},
        ],
        "platform-redis": [{"target": "core", "path": ["redis", "image"]}],
        "workspace-canvas": [{"target": "core", "path": ["kubernetes", "canvasImage"]}],
        "workspace-chrome": [
            {"target": "core", "path": ["kubernetes", "browserImage"]}
        ],
        "workspace-manager": [
            {"target": "core", "path": ["workspaceManager", "image"]}
        ],
        "workspace-operator": [
            {"target": "core", "path": ["workspaceOperator", "image"]}
        ],
        "workspace-runtime": [
            {"target": "core", "path": ["workspaceOperator", "runtimeImage"]}
        ],
        "workspace-ui": [{"target": "core", "path": ["frontend", "image"]}],
    }
    core = yaml.safe_load((ROOT / "helm/values-rke2-207-homelab.yaml").read_text())
    identity = yaml.safe_load(
        (ROOT / "helm/values-rke2-207-homelab-identity.yaml").read_text()
    )
    contract_core = contract["homeLab"]["core"]
    assert contract_core["bootstrap"]["admin"] == {
        "enabled": True,
        "subject": "00000000-0000-4000-8000-000000000001",
        "username": "admin",
        "email": "admin@aileron.com",
    }
    contract_identity = contract["homeLab"]["identity"]

    assert contract_core["platformPublicOrigin"] == core["platformPublicOrigin"]
    assert contract_core["oidc"] == core["oidc"]
    assert contract_identity["issuerUrl"] == identity["issuerUrl"]
    assert contract_identity["clientId"] == identity["clientId"]
    assert contract_identity["platformCallbackUrl"] == identity["platformCallbackUrl"]
    assert contract_identity["ingress"]["public"] == {
        "hostname": identity["ingress"]["public"]["hostname"],
        "tlsSecretName": identity["ingress"]["public"]["tlsSecretName"],
    }
    assert contract_identity["postgres"]["storage"] == identity["postgres"]["storage"]
    assert contract_identity["networkPolicy"] == identity["networkPolicy"]
    assert contract_identity["global"] == identity["global"]
    assert contract_identity["issuerUrl"] == core["oidc"]["issuerUrl"]
    assert contract_identity["clientId"] == core["oidc"]["clientId"]
    assert contract_identity["platformCallbackUrl"] == (
        f"{core['platformPublicOrigin']}/api/v1/oauth2/callback"
    )


def test_external_renderer_keeps_complete_inventory_but_skips_identity_values(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory)

    result = MODULE.render_release_values(
        inventory_path=inventory,
        expected_commit=COMMIT,
        expected_registry="harbor.example.test",
        expected_project="library",
        identity_mode="externalOidc",
        output_directory=tmp_path / "values",
        image_contract_path=IMAGE_CONTRACT,
        values_contract_path=VALUES_CONTRACT,
        external_oidc={
            "issuerUrl": "https://auth.example.test/application/o/aileron/",
            "clientId": "external-client",
        },
    )

    assert result.identity_path is None
    assert not (tmp_path / "values/identity-values.json").exists()
    core = json.loads(result.core_path.read_text())
    assert core["oidc"]["issuerUrl"] == (
        "https://auth.example.test/application/o/aileron/"
    )
    assert core["oidc"]["clientId"] == "external-client"
    assert "platform-keycloak" in result.published_images
    assert "platform-keycloak" not in json.dumps(core)


def test_renderer_merges_only_data_service_values(tmp_path: Path) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory, omit="platform-redis")
    core_values = tmp_path / "core-data-services.yaml"
    identity_values = tmp_path / "identity-data-services.yaml"
    core_values.write_text(
        (ROOT / "helm/values-rke2-207-homelab-external-data-services.yaml").read_text(),
        encoding="utf-8",
    )
    identity_values.write_text(
        (
            ROOT / "helm/values-rke2-207-homelab-identity-external-data-services.yaml"
        ).read_text(),
        encoding="utf-8",
    )

    result = MODULE.render_release_values(
        inventory_path=inventory,
        expected_commit=COMMIT,
        expected_registry="harbor.example.test",
        expected_project="library",
        identity_mode="bundledKeycloak",
        output_directory=tmp_path / "values",
        image_contract_path=IMAGE_CONTRACT,
        values_contract_path=VALUES_CONTRACT,
        core_data_service_values_path=core_values,
        identity_data_service_values_path=identity_values,
    )

    core = json.loads(result.core_path.read_text())
    identity = json.loads(result.identity_path.read_text())
    assert core["postgres"]["enabled"] is False
    assert core["redis"]["enabled"] is False
    assert "image" not in core["redis"]
    assert "platform-redis" not in result.published_images
    assert core["platformDatabase"]["caSecretName"] == ("aileron-platform-database-ca")
    assert core["platformDatabase"]["ciliumEgress"] == {
        "kind": "namespacePods",
        "namespace": "platform-data",
        "podLabels": {"app.kubernetes.io/name": "postgres"},
    }
    assert identity["postgres"]["enabled"] is False
    assert identity["networkPolicy"]["externalDatabaseEgress"]["mode"] == ("selector")
    assert core["workspaceManager"]["image"]["repository"].endswith(
        "/workspace-manager"
    )


@pytest.mark.parametrize(
    ("target", "document"),
    [
        ("core", {"postgres": {"image": {"repository": "attacker.invalid"}}}),
        ("core", {"external": True}),
        ("identity", {"images": {"postgres": {"repository": "attacker.invalid"}}}),
    ],
)
def test_renderer_rejects_data_service_values_outside_allowlist(
    tmp_path: Path, target: str, document: dict
) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory)
    overlay = tmp_path / "data-services.yaml"
    overlay.write_text(yaml.safe_dump(document), encoding="utf-8")
    arguments = {
        "core_data_service_values_path": overlay if target == "core" else None,
        "identity_data_service_values_path": overlay if target == "identity" else None,
    }
    with pytest.raises(ValueError, match="forbidden"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=tmp_path / "values",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
            **arguments,
        )


@pytest.mark.parametrize(
    ("identity_mode", "external_oidc", "error"),
    [
        ("externalOidc", None, "external OIDC"),
        ("bundledKeycloak", {"issuerUrl": "https://x", "clientId": "x"}, "must not"),
        ("disabled", None, "identity mode"),
    ],
)
def test_renderer_rejects_mode_input_drift(
    tmp_path: Path,
    identity_mode: str,
    external_oidc: dict[str, str] | None,
    error: str,
) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory)
    with pytest.raises(ValueError, match=error):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode=identity_mode,
            output_directory=tmp_path / "values",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
            external_oidc=external_oidc,
        )


def test_renderer_rejects_incomplete_or_duplicate_inventory(tmp_path: Path) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory, omit="platform-keycloak")
    with pytest.raises(ValueError, match="component mismatch"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=tmp_path / "missing",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
        )

    _inventory(inventory, duplicate="workspace-ui")
    with pytest.raises(ValueError, match="duplicates"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=tmp_path / "duplicate",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
        )


def test_renderer_rejects_unmapped_or_duplicate_destination_contract(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory)
    contract = json.loads(VALUES_CONTRACT.read_text())
    contract["components"].pop("workspace-ui")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=tmp_path / "unmapped",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=broken,
        )

    contract = json.loads(VALUES_CONTRACT.read_text())
    contract["components"]["workspace-manager"].append(
        contract["components"]["workspace-ui"][0]
    )
    broken.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="destination"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="bundledKeycloak",
            output_directory=tmp_path / "duplicate-destination",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=broken,
        )


def test_renderer_rejects_symlink_output_and_credentialed_external_issuer(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "images.tsv"
    _inventory(inventory)
    real_output = tmp_path / "real-output"
    real_output.mkdir(mode=0o700)
    linked_output = tmp_path / "linked-output"
    linked_output.symlink_to(real_output, target_is_directory=True)
    with pytest.raises(ValueError, match="0700"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="externalOidc",
            output_directory=linked_output,
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
            external_oidc={
                "issuerUrl": "https://identity.example.test/",
                "clientId": "client",
            },
        )
    with pytest.raises(ValueError, match="public HTTPS"):
        MODULE.render_release_values(
            inventory_path=inventory,
            expected_commit=COMMIT,
            expected_registry="harbor.example.test",
            expected_project="library",
            identity_mode="externalOidc",
            output_directory=tmp_path / "credentialed",
            image_contract_path=IMAGE_CONTRACT,
            values_contract_path=VALUES_CONTRACT,
            external_oidc={
                "issuerUrl": "https://user:password@identity.example.test/",
                "clientId": "client",
            },
        )
