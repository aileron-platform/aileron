#!/usr/bin/env python3
"""Prepare the canonical signed image inventory before destructive reset."""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIRECTORY.parents[2]
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RESULT_SCHEMA = "aileron-release-inventory-preparation-result/v1"
COMMAND_TIMEOUT_SECONDS = 60
CommandRunner = Callable[..., str]


def _load_module(name: str, filename: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        name,
        SCRIPT_DIRECTORY / filename,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("release inventory preparation dependency is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INSTALLATION_STATE = _load_module(
    "aileron_release_prepare_installation_state",
    "installation_state.py",
)
PRIVATE_INPUT = _load_module(
    "aileron_release_prepare_private_input",
    "private_input.py",
)
RELEASE_INVENTORY = _load_module(
    "aileron_release_prepare_inventory",
    "release_inventory.py",
)
ACCEPTANCE_CLUSTER = _load_module(
    "aileron_release_prepare_acceptance_cluster",
    "acceptance_cluster.py",
)
ACCEPTANCE_RELEASE = _load_module(
    "aileron_release_prepare_acceptance_release",
    "acceptance_release.py",
)


class ReleaseInventoryPreparationError(RuntimeError):
    """Raised without exposing command output or private input content."""


def _run_command(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env={**os.environ, **(environment or {})},
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseInventoryPreparationError(
            "release inventory preparation command failed"
        ) from exc
    if process.returncode != 0:
        raise ReleaseInventoryPreparationError(
            "release inventory preparation command failed"
        )
    try:
        return process.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseInventoryPreparationError(
            "release inventory preparation command returned invalid text"
        ) from exc


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
            raise ReleaseInventoryPreparationError(
                "installation private root lock is invalid"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise ReleaseInventoryPreparationError(
                    "another installation operation is already running"
                ) from exc
            raise ReleaseInventoryPreparationError(
                "installation private root lock is unavailable"
            ) from exc
        locked = True
        yield
    except ReleaseInventoryPreparationError:
        raise
    except OSError as exc:
        raise ReleaseInventoryPreparationError(
            "installation private root lock is unavailable"
        ) from exc
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _ensure_private_directory(path: Path, *, private_root: Path) -> Path:
    if not path.is_absolute():
        raise ReleaseInventoryPreparationError(
            "release preparation directory must use an absolute path"
        )
    try:
        relative = path.relative_to(private_root)
    except ValueError as exc:
        raise ReleaseInventoryPreparationError(
            "release preparation directory is not installation-owned"
        ) from exc
    current = private_root
    for component in relative.parts:
        current /= component
        if not current.exists() and not current.is_symlink():
            try:
                current.mkdir(mode=0o700)
            except OSError as exc:
                raise ReleaseInventoryPreparationError(
                    "release preparation directory cannot be created"
                ) from exc
        try:
            PRIVATE_INPUT.validate_private_directory(
                current,
                "release preparation directory",
                private_root=private_root,
            )
        except PRIVATE_INPUT.PrivateInputError as exc:
            raise ReleaseInventoryPreparationError(str(exc)) from exc
    return path


def prepare_release_inventory(
    *,
    commit: str,
    context: str,
    kubeconfig: Path,
    inventory: Path,
    docker_config: Path,
    registry: str,
    project: str,
    omitted_components: frozenset[str] = frozenset(),
    runner: CommandRunner = _run_command,
) -> dict[str, Any]:
    """Publish or validate one canonical installation-bound image inventory."""

    if FULL_SHA_PATTERN.fullmatch(commit) is None:
        raise ReleaseInventoryPreparationError(
            "commit must be a full lowercase Git SHA"
        )
    if (
        not context
        or context != context.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in context)
    ):
        raise ReleaseInventoryPreparationError(
            "an exact Kubernetes context is required"
        )
    try:
        private_root = PRIVATE_INPUT.private_root_path(INSTALLATION_STATE.PRIVATE_ROOT)
    except PRIVATE_INPUT.PrivateInputError as exc:
        raise ReleaseInventoryPreparationError(str(exc)) from exc

    with _installation_lock(private_root):
        if runner(["git", "status", "--porcelain"], environment={}):
            raise ReleaseInventoryPreparationError(
                "release preparation requires a clean Git checkout"
            )
        actual_commit = runner(
            ["git", "rev-parse", "--verify", "HEAD"],
            environment={},
        ).strip()
        if actual_commit != commit:
            raise ReleaseInventoryPreparationError(
                "Git HEAD does not match the requested release commit"
            )

        work_directory = _ensure_private_directory(
            private_root / "install" / commit,
            private_root=private_root,
        )
        preparation_directory = _ensure_private_directory(
            work_directory / "release-preparation",
            private_root=private_root,
        )
        try:
            flattened_kubeconfig = PRIVATE_INPUT.snapshot_self_contained_kubeconfig(
                source=kubeconfig,
                raw_destination=preparation_directory / "kubeconfig.raw",
                flattened_destination=preparation_directory / "kubeconfig",
                context=context,
                runner=runner,
                private_root=private_root,
                allow_existing_exact=True,
            )
            inventory_snapshot = PRIVATE_INPUT.snapshot_private_file(
                source=inventory,
                destination=preparation_directory / "published-image-inventory.tsv",
                description="published image inventory",
                private_root=private_root,
                allow_existing_exact=True,
            )
            raw_inventory = PRIVATE_INPUT.read_private_bytes(
                inventory_snapshot,
                "published image inventory snapshot",
                private_root=private_root,
            ).decode("utf-8")
            contract = RELEASE_INVENTORY.load_contract(
                SCRIPT_DIRECTORY / "image-release-contract.json"
            )
            images = RELEASE_INVENTORY.validate_published_inventory(
                raw_inventory.splitlines(keepends=True),
                contract=contract,
                expected_commit=commit,
                expected_registry=registry,
                expected_project=project,
                omitted_components=omitted_components,
            )
        except (
            UnicodeDecodeError,
            ValueError,
            PRIVATE_INPUT.PrivateInputError,
        ) as exc:
            raise ReleaseInventoryPreparationError(
                "published release inputs are invalid"
            ) from exc

        try:
            PRIVATE_INPUT.read_private_bytes(
                docker_config,
                "Harbor Docker configuration",
                private_root=private_root,
                maximum_size=1024 * 1024,
            )
            PRIVATE_INPUT.validate_private_directory(
                docker_config.parent,
                "Harbor Docker configuration directory",
                private_root=private_root,
            )

            def inspect_remote_image(tagged_image: str) -> str:
                return runner(
                    [
                        "docker",
                        "buildx",
                        "imagetools",
                        "inspect",
                        tagged_image,
                        "--format",
                        "{{json .}}",
                    ],
                    environment={"DOCKER_CONFIG": str(docker_config.parent)},
                )

            RELEASE_INVENTORY.verify_remote_published_inventory(
                images,
                inspect=inspect_remote_image,
            )
        except (
            ValueError,
            PRIVATE_INPUT.PrivateInputError,
            ReleaseInventoryPreparationError,
        ) as exc:
            raise ReleaseInventoryPreparationError(
                "published registry provenance is invalid"
            ) from exc

        def trust_runner(command: list[str]) -> bytes:
            return runner(
                command,
                environment={"KUBECONFIG": str(flattened_kubeconfig)},
            ).encode("utf-8")

        if (
            ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT != private_root
            or ACCEPTANCE_CLUSTER.INSTALLATION_STATE.SECRET_STORE
            != INSTALLATION_STATE.SECRET_STORE
        ):
            raise ReleaseInventoryPreparationError(
                "acceptance trust private-state identity is inconsistent"
            )
        try:
            trust = ACCEPTANCE_CLUSTER.load_cluster_release_trust(
                context=context,
                kubeconfig=flattened_kubeconfig,
                runner=trust_runner,
            )
        except ACCEPTANCE_CLUSTER.AcceptanceClusterError as exc:
            raise ReleaseInventoryPreparationError(
                "live acceptance trust is invalid"
            ) from exc

        signed_inventory = work_directory / "signed-image-inventory.json"
        created = not signed_inventory.exists() and not signed_inventory.is_symlink()
        try:
            if created:
                ACCEPTANCE_RELEASE.write_signed_image_inventory(
                    path=signed_inventory,
                    private_root=private_root,
                    images=images,
                    key=trust.key,
                    context=context,
                    commit=commit,
                    cluster_uid=trust.cluster_uid,
                    installation_identity_sha256=(trust.installation_identity_sha256),
                )
            ACCEPTANCE_RELEASE.load_matching_signed_image_inventory(
                path=signed_inventory,
                private_root=private_root,
                expected_images=images,
                key=trust.key,
                context=context,
                commit=commit,
                cluster_uid=trust.cluster_uid,
                installation_identity_sha256=trust.installation_identity_sha256,
            )
            signed_raw = PRIVATE_INPUT.read_private_bytes(
                signed_inventory,
                "signed image inventory",
                private_root=private_root,
            )
        except (
            ACCEPTANCE_RELEASE.AcceptanceReleaseError,
            PRIVATE_INPUT.PrivateInputError,
        ) as exc:
            raise ReleaseInventoryPreparationError(
                "signed image inventory is invalid"
            ) from exc

        return {
            "schemaVersion": RESULT_SCHEMA,
            "commit": commit,
            "context": context,
            "imageCount": len(images),
            "created": created,
            "signedInventorySha256": hashlib.sha256(signed_raw).hexdigest(),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the canonical signed image inventory before destructive reset."
        )
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--docker-config", required=True, type=Path)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--omit-component", action="append", default=[])
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = prepare_release_inventory(
            commit=arguments.commit,
            context=arguments.context,
            kubeconfig=arguments.kubeconfig,
            inventory=arguments.inventory,
            docker_config=arguments.docker_config,
            registry=arguments.registry,
            project=arguments.project,
            omitted_components=frozenset(arguments.omit_component),
        )
    except ReleaseInventoryPreparationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
