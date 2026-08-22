"""Copy external Identity inputs through a no-follow private-root boundary."""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _reject_symlinks(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("external Identity input path contains a symbolic link")


def copy_private(private_root: Path, source: Path, destination: Path) -> None:
    if not private_root.is_absolute() or not source.is_absolute():
        raise ValueError("external Identity input paths must be absolute")
    _reject_symlinks(private_root)
    _reject_symlinks(source)
    if (
        not private_root.is_dir()
        or stat.S_IMODE(os.lstat(private_root).st_mode) != 0o700
    ):
        raise ValueError("Identity private root must be a mode 0700 directory")
    try:
        private_root.resolve(strict=True).relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Identity private root must be outside the repository")
    try:
        source.resolve(strict=True).relative_to(private_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "external Identity input must be within the private root"
        ) from exc
    try:
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError("external Identity input is unreadable") from exc
    try:
        metadata = os.fstat(source_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise ValueError("external Identity input must be a mode 0600 regular file")
        destination_fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            while chunk := os.read(source_fd, 65536):
                os.write(destination_fd, chunk)
            os.fsync(destination_fd)
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--destination-dir", type=Path, required=True)
    parser.add_argument("--image-pull-secret", type=Path, required=True)
    parser.add_argument("--tls-certificate", type=Path, required=True)
    parser.add_argument("--tls-private-key", type=Path, required=True)
    parser.add_argument("--postgres-username", type=Path)
    parser.add_argument("--postgres-password", type=Path)
    parser.add_argument("--postgres-ca", type=Path)
    arguments = parser.parse_args()
    postgres_inputs = (
        arguments.postgres_username,
        arguments.postgres_password,
        arguments.postgres_ca,
    )
    if any(value is not None for value in postgres_inputs) and not all(
        value is not None for value in postgres_inputs
    ):
        parser.error("external PostgreSQL inputs must be provided as a complete set")
    try:
        copy_private(
            arguments.private_root,
            arguments.image_pull_secret,
            arguments.destination_dir / "dockerconfig.json",
        )
        copy_private(
            arguments.private_root,
            arguments.tls_certificate,
            arguments.destination_dir / "tls.crt",
        )
        copy_private(
            arguments.private_root,
            arguments.tls_private_key,
            arguments.destination_dir / "tls.key",
        )
        if all(value is not None for value in postgres_inputs):
            copy_private(
                arguments.private_root,
                arguments.postgres_username,
                arguments.destination_dir / "postgres-username",
            )
            copy_private(
                arguments.private_root,
                arguments.postgres_password,
                arguments.destination_dir / "postgres-password",
            )
            copy_private(
                arguments.private_root,
                arguments.postgres_ca,
                arguments.destination_dir / "postgres-ca.crt",
            )
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
