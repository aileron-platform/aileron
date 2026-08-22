from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "release_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("release_inventory", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONTRACT = MODULE.load_contract(MODULE_PATH.with_name("image-release-contract.json"))
COMMIT = "a" * 40
VALIDATION_ARGUMENTS = {
    "contract": CONTRACT,
    "expected_commit": COMMIT,
    "expected_registry": "harbor",
    "expected_project": "library",
}


def _rows() -> list[str]:
    return [
        "\t".join(
            (
                component,
                COMMIT,
                "linux/amd64",
                f"harbor/library/{component}:git-{COMMIT}",
                f"harbor/library/{component}@sha256:{'b' * 64}",
                f"harbor/library/{component}@sha256:{'c' * 64}",
            )
        )
        for component in CONTRACT["publishedComponents"]
    ]


def _remote_document(image: dict[str, str]) -> dict:
    runtime_digest = image["runtimeImmutableImage"].rsplit("@", 1)[1]
    return {
        "name": image["taggedImage"],
        "image": {
            "os": "linux",
            "architecture": "amd64",
            "config": {
                "Labels": {
                    "org.opencontainers.image.revision": image["revision"],
                }
            },
        },
        "manifest": {
            "mediaType": MODULE.OCI_INDEX_MEDIA_TYPE,
            "digest": image["immutableImage"].rsplit("@", 1)[1],
            "manifests": [
                {
                    "mediaType": MODULE.OCI_MANIFEST_MEDIA_TYPE,
                    "digest": runtime_digest,
                    "platform": {
                        "os": "linux",
                        "architecture": "amd64",
                        "os.version": "6.1",
                        "os.features": ["feature-a"],
                        "variant": "v1",
                    },
                },
                {
                    "mediaType": MODULE.OCI_MANIFEST_MEDIA_TYPE,
                    "digest": f"sha256:{'d' * 64}",
                    "platform": {
                        "os": "unknown",
                        "architecture": "unknown",
                        "variant": "attestation",
                    },
                    "annotations": {
                        "vnd.docker.reference.type": "attestation-manifest",
                        "vnd.docker.reference.digest": runtime_digest,
                    },
                },
            ],
        },
    }


def test_published_inventory_has_exact_named_release_set() -> None:
    result = MODULE.validate_published_inventory(_rows(), **VALIDATION_ARGUMENTS)

    assert [item["component"] for item in result] == CONTRACT["publishedComponents"]
    assert "platform-keycloak" in CONTRACT["workloadComponents"]
    assert CONTRACT["buildEvidenceComponents"] == ["workspace-runtime-base-lite"]


@pytest.mark.parametrize(
    "column,value,error",
    [
        (1, "c" * 40, "revision mismatch"),
        (2, "linux/arm64", "platform mismatch"),
        (4, "harbor/library/workspace-ui:latest", "digest is invalid"),
        (5, "harbor/library/workspace-ui:latest", "runtime digest is invalid"),
    ],
)
def test_published_inventory_rejects_invalid_provenance(
    column: int, value: str, error: str
) -> None:
    rows = _rows()
    fields = rows[-1].split("\t")
    fields[column] = value
    rows[-1] = "\t".join(fields)

    with pytest.raises(ValueError, match=error):
        MODULE.validate_published_inventory(rows, **VALIDATION_ARGUMENTS)


def test_published_inventory_rejects_missing_component() -> None:
    with pytest.raises(ValueError, match="component mismatch"):
        MODULE.validate_published_inventory(_rows()[:-1], **VALIDATION_ARGUMENTS)


def test_external_redis_inventory_may_omit_only_platform_redis() -> None:
    rows = [row for row in _rows() if not row.startswith("platform-redis\t")]

    result = MODULE.validate_published_inventory(
        rows,
        **VALIDATION_ARGUMENTS,
        omitted_components=frozenset({"platform-redis"}),
    )

    assert "platform-redis" not in {item["component"] for item in result}


def test_published_inventory_rejects_equal_index_and_runtime_digest() -> None:
    rows = _rows()
    fields = rows[-1].split("\t")
    fields[5] = fields[4]
    rows[-1] = "\t".join(fields)

    with pytest.raises(ValueError, match="runtime repository or digest"):
        MODULE.validate_published_inventory(rows, **VALIDATION_ARGUMENTS)


def test_published_inventory_rejects_repository_outside_release_profile() -> None:
    rows = _rows()
    fields = rows[-1].split("\t")
    fields[3] = f"attacker.invalid/unrelated/{fields[0]}:git-{COMMIT}"
    fields[4] = f"attacker.invalid/unrelated/{fields[0]}@sha256:{'b' * 64}"
    fields[5] = f"attacker.invalid/unrelated/{fields[0]}@sha256:{'c' * 64}"
    rows[-1] = "\t".join(fields)

    with pytest.raises(ValueError, match="repository or tag mismatch"):
        MODULE.validate_published_inventory(rows, **VALIDATION_ARGUMENTS)


def test_remote_document_binds_name_and_accepts_oci_platform_extensions() -> None:
    image = MODULE.validate_published_inventory(_rows(), **VALIDATION_ARGUMENTS)[0]
    document = _remote_document(image)

    MODULE.validate_remote_image_document(document, image=image)

    document.pop("name")
    with pytest.raises(ValueError, match="remote image provenance is invalid"):
        MODULE.validate_remote_image_document(document, image=image)
