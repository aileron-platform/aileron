from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import stat
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy/rke2/acceptance_release.py"
SPEC = importlib.util.spec_from_file_location("acceptance_release", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = json.loads(
    (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
)
KEY = bytes(range(32))
COMMIT = "a" * 40
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
IDENTITY_DIGEST = "b" * 64


def _images() -> list[dict[str, str]]:
    return [
        {
            "component": component,
            "revision": COMMIT,
            "platform": "linux/amd64",
            "taggedImage": f"harbor.example.test/library/{component}:git-{COMMIT}",
            "immutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 1:064x}"
            ),
            "runtimeImmutableImage": (
                f"harbor.example.test/library/{component}@sha256:{index + 101:064x}"
            ),
        }
        for index, component in enumerate(CONTRACT["publishedComponents"])
    ]


def test_signed_inventory_returns_exact_workspace_manager_image(tmp_path: Path) -> None:
    path = tmp_path / "signed-image-inventory.json"
    MODULE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=_images(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["schemaVersion"] == (
        "aileron-signed-image-inventory/v2"
    )
    image = MODULE.load_workspace_manager_image(
        path=path,
        private_root=tmp_path,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    assert image["revision"] == COMMIT
    assert image["immutableImage"].startswith(
        "harbor.example.test/library/workspace-manager@sha256:"
    )
    assert image["runtimeImmutableImage"].startswith(
        "harbor.example.test/library/workspace-manager@sha256:"
    )


def test_signed_inventory_rejects_missing_component(tmp_path: Path) -> None:
    with pytest.raises(MODULE.AcceptanceReleaseError, match="release contract"):
        MODULE.write_signed_image_inventory(
            path=tmp_path / "signed-image-inventory.json",
            private_root=tmp_path,
            images=_images()[:-1],
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )


def test_signed_inventory_accepts_omitted_optional_redis_image(tmp_path: Path) -> None:
    images = [image for image in _images() if image["component"] != "platform-redis"]

    MODULE.write_signed_image_inventory(
        path=tmp_path / "signed-image-inventory.json",
        private_root=tmp_path,
        images=images,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )

    assert (
        len(
            MODULE.load_signed_image_inventory(
                path=tmp_path / "signed-image-inventory.json",
                private_root=tmp_path,
                key=KEY,
                context="rke2-homelab",
                commit=COMMIT,
                cluster_uid=CLUSTER_UID,
                installation_identity_sha256=IDENTITY_DIGEST,
            )
        )
        == 10
    )


def test_signed_inventory_rejects_equal_index_and_runtime_digest(
    tmp_path: Path,
) -> None:
    images = _images()
    images[0]["runtimeImmutableImage"] = images[0]["immutableImage"]

    with pytest.raises(MODULE.AcceptanceReleaseError, match="entry is invalid"):
        MODULE.write_signed_image_inventory(
            path=tmp_path / "signed-image-inventory.json",
            private_root=tmp_path,
            images=images,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )


def test_signed_inventory_v1_is_rejected_even_with_a_valid_signature(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signed-image-inventory.json"
    MODULE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=_images(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    document = json.loads(path.read_text())
    document["schemaVersion"] = "aileron-signed-image-inventory/v1"
    document.pop("signature")
    document["signature"] = hmac.new(
        KEY, MODULE._canonical(document), hashlib.sha256
    ).hexdigest()
    path.write_bytes(MODULE._canonical(document) + b"\n")
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceReleaseError, match="identity does not match"):
        MODULE.load_signed_image_inventory(
            path=path,
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )


def test_signed_inventory_must_exactly_match_the_unsigned_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signed-image-inventory.json"
    images = _images()
    MODULE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=images,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )

    assert (
        MODULE.load_matching_signed_image_inventory(
            path=path,
            private_root=tmp_path,
            expected_images=images,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )
        == images
    )

    changed = [dict(image) for image in images]
    changed[0]["immutableImage"] = (
        changed[0]["immutableImage"].rsplit(":", 1)[0] + ":" + "f" * 64
    )
    with pytest.raises(MODULE.AcceptanceReleaseError, match="does not match"):
        MODULE.load_matching_signed_image_inventory(
            path=path,
            private_root=tmp_path,
            expected_images=changed,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )


@pytest.mark.parametrize("tamper", ["duplicate", "whitespace", "order", "utf8"])
def test_signed_inventory_rejects_noncanonical_or_ambiguous_json(
    tmp_path: Path,
    tamper: str,
) -> None:
    path = tmp_path / "signed-image-inventory.json"
    MODULE.write_signed_image_inventory(
        path=path,
        private_root=tmp_path,
        images=_images(),
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    raw = path.read_bytes()
    document = json.loads(raw)
    if tamper == "duplicate":
        member = f'"commit":"{COMMIT}"'
        raw = raw.replace(member.encode(), f"{member},{member}".encode(), 1)
    elif tamper == "whitespace":
        raw = json.dumps(document, indent=2, sort_keys=True).encode() + b"\n"
    elif tamper == "order":
        raw = (
            json.dumps(
                dict(reversed(list(document.items()))),
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
    else:
        raw = raw[:-1] + b"\xff\n"
    path.write_bytes(raw)
    path.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceReleaseError, match="invalid JSON|canonical"):
        MODULE.load_signed_image_inventory(
            path=path,
            private_root=tmp_path,
            key=KEY,
            context="rke2-homelab",
            commit=COMMIT,
            cluster_uid=CLUSTER_UID,
            installation_identity_sha256=IDENTITY_DIGEST,
        )
