#!/usr/bin/env python3
"""Run fixed acceptance transport handshakes and emit protocol-level raw results."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import stat
import subprocess
import time

TURN_PROBE_TTL_SECONDS = 300


def _read_credential(path: str, description: str) -> str:
    try:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{description} must be a regular file")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            value = os.read(descriptor, 4097)
        finally:
            os.close(descriptor)
    except (OSError, ValueError) as exc:
        raise SystemExit(
            f"fixed TURN credential input is invalid: {description}"
        ) from exc
    if not value or len(value) > 4096:
        raise SystemExit(f"fixed TURN credential input is invalid: {description}")
    try:
        decoded = value.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise SystemExit(
            f"fixed TURN credential input is invalid: {description}"
        ) from exc
    if not decoded or "\n" in decoded or "\r" in decoded:
        raise SystemExit(f"fixed TURN credential input is invalid: {description}")
    return decoded


def _issue_turn_rest_credentials(
    username_file: str,
    shared_secret_file: str,
    identity_suffix: str = "",
    now: int | None = None,
) -> tuple[str, str]:
    identity = _read_credential(username_file, "probe identity")
    shared_secret = _read_credential(shared_secret_file, "TURN REST shared secret")
    if identity_suffix:
        identity = f"{identity}:{identity_suffix}"
    issued_at = int(time.time()) if now is None else now
    username = f"{issued_at + TURN_PROBE_TTL_SECONDS}:{identity}"
    credential = base64.b64encode(
        hmac.new(
            shared_secret.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("ascii")
    return username, credential


def _turn(host: str, path: str, username_file: str, shared_secret_file: str) -> str:
    username, credential = _issue_turn_rest_credentials(
        username_file, shared_secret_file, identity_suffix=path
    )
    command = [
        "turnutils_uclient",
        "-t",
        "-y",
        "-v",
        "-e",
        "127.0.0.1",
        "-p",
        "3478",
        "-u",
        username,
        "-w",
        credential,
        host,
    ]
    result = subprocess.run(
        command, capture_output=True, check=False, text=True, timeout=30
    )
    if result.returncode != 0:
        raise SystemExit("fixed TURN allocation probe failed")
    relay_lines = [
        line for line in result.stdout.splitlines() if "relay" in line.lower()
    ]
    if not relay_lines:
        raise SystemExit("fixed TURN allocation probe returned no relay result")
    return "\n".join(relay_lines)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="protocol", required=True)
    turn = subparsers.add_parser("turn")
    turn.add_argument("--host", required=True)
    turn.add_argument("--path", choices=("frontend", "backend"), required=True)
    turn.add_argument("--username-file", required=True)
    turn.add_argument("--shared-secret-file", required=True)
    return parser


def main() -> int:
    arguments = create_parser().parse_args()
    print(
        _turn(
            arguments.host,
            arguments.path,
            arguments.username_file,
            arguments.shared_secret_file,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
