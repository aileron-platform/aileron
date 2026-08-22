#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from aileron_git_core import build_git_command


AGENT_DEFAULTS_DIAGNOSTIC_MAX_BYTES = 4096


class BootstrapError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _enabled(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def sanitize_repository_url(repository_url: str) -> str:
    parts = urlsplit(repository_url)
    if parts.scheme not in {"http", "https", "ssh"} or not parts.hostname:
        return repository_url

    hostname = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    host = f"{hostname}:{parts.port}" if parts.port is not None else hostname
    if parts.scheme == "ssh" and parts.username and parts.password is None:
        host = f"{parts.username}@{host}"
    return urlunsplit(SplitResult(parts.scheme, host, parts.path, "", ""))


class WorkspaceRuntimeInitializer:
    def __init__(self) -> None:
        self.workspace_id = os.environ.get("AILERON_WORKSPACE_ID", "")
        self.workspace = Path(os.environ.get("AILERON_WORKSPACE_PATH", ""))
        self.home = Path(os.environ.get("HOME", ""))
        self.codex_home = Path(os.environ.get("CODEX_HOME") or self.home / ".codex")
        self.xdg_config_home = Path(
            os.environ.get("XDG_CONFIG_HOME") or self.home / ".config"
        )
        self.xdg_data_home = Path(
            os.environ.get("XDG_DATA_HOME") or self.home / ".local" / "share"
        )
        self.xdg_state_home = Path(
            os.environ.get("XDG_STATE_HOME") or self.home / ".local" / "state"
        )
        self.aileron_state_home = self.xdg_state_home / "aileron"
        self.bootstrap_dir = self.aileron_state_home / "bootstrap"
        self.state_path = self.bootstrap_dir / "state.json"
        self.lock_path = self.bootstrap_dir / "lock"
        self.defaults_marker = self.bootstrap_dir / "agent-defaults-v1.json"
        self.defaults_initializer = Path(
            os.environ.get(
                "AILERON_AGENT_DEFAULTS_INITIALIZER",
                "/workspace-runtime/scripts/initialize_agent_defaults.sh",
            )
        )
        self.setup_script = Path(
            os.environ.get("CUSTOM_SETUP_SCRIPT", "/scripts/custom-setup.sh")
        )
        self.revision = int(os.environ.get("WORKSPACE_BOOTSTRAP_REVISION", "1"))
        self.repo_url = os.environ.get("GIT_REPO_URL", "")
        self.public_repo_url = sanitize_repository_url(self.repo_url)
        self.branch = os.environ.get("GIT_BRANCH", "main")
        self.init_git = _enabled(os.environ.get("WORKSPACE_INIT_GIT"))
        self.setup_timeout = int(os.environ.get("CUSTOM_SETUP_TIMEOUT_SECONDS", "600"))
        self.setup_output_limit = int(
            os.environ.get("CUSTOM_SETUP_OUTPUT_MAX_BYTES", str(1024 * 1024))
        )

    def run(self) -> None:
        self._validate_paths()
        self.bootstrap_dir.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BootstrapError("RUNTIME_STATE_INIT_FAILED") from exc

            state = self._load_state()
            previously_succeeded = state.get("phase") == "Succeeded"
            if previously_succeeded and not self.defaults_marker.is_file():
                raise BootstrapError("AGENT_DEFAULTS_STATE_MISSING")

            state = self._prepare_state(state)
            try:
                self._prepare_git_credentials()
                self._bootstrap_git(state)
                self._run_agent_defaults()
                self._run_custom_setup()
            except BootstrapError as exc:
                state["phase"] = "Failed"
                state["errorCode"] = exc.code
                state["updatedAt"] = _now()
                self._save_state(state)
                raise

            state["phase"] = "Succeeded"
            state["observedRevision"] = self.revision
            state["errorCode"] = None
            state["completedAt"] = _now()
            state["updatedAt"] = state["completedAt"]
            self._save_state(state)

    def _prepare_git_credentials(self) -> None:
        private_key = os.environ.get("SSH_PRIVATE_KEY")
        if not private_key:
            return
        home = Path(os.environ.get("HOME", ""))
        if not home.is_absolute():
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED")
        try:
            ssh_dir = home / ".ssh"
            ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(ssh_dir, 0o700)
            private_key_path = ssh_dir / "id_rsa"
            private_key_path.write_text(
                private_key.rstrip("\n") + "\n", encoding="utf-8"
            )
            os.chmod(private_key_path, 0o600)
            public_key = os.environ.get("SSH_PUBLIC_KEY")
            if public_key:
                public_key_path = ssh_dir / "id_rsa.pub"
                public_key_path.write_text(
                    public_key.rstrip("\n") + "\n",
                    encoding="utf-8",
                )
                os.chmod(public_key_path, 0o644)
        except OSError as exc:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED") from exc

    def _validate_paths(self) -> None:
        state_paths = (
            self.home,
            self.codex_home,
            self.xdg_config_home,
            self.xdg_data_home,
            self.xdg_state_home,
            self.aileron_state_home,
        )
        if (
            not self.workspace_id
            or self.workspace_id != self.workspace_id.strip()
            or len(self.workspace_id) > 128
            or not self.workspace.is_absolute()
            or any(not path.is_absolute() for path in state_paths)
        ):
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED")
        if self.revision < 1 or self.setup_timeout < 1 or self.setup_output_limit < 1:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED")
        try:
            self.workspace.mkdir(parents=True, exist_ok=True)
            self.bootstrap_dir.mkdir(parents=True, exist_ok=True)
            for path in (
                self.workspace,
                self.bootstrap_dir,
                self.home,
                self.codex_home,
                self.xdg_config_home,
                self.xdg_data_home,
                self.xdg_state_home,
                self.aileron_state_home,
            ):
                path.mkdir(parents=True, exist_ok=True)
                probe = path / f".aileron-write-probe-{uuid.uuid4().hex}"
                probe.touch(mode=0o600)
                probe.unlink()
        except OSError as exc:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED") from exc

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED") from exc
        if not isinstance(state, dict) or state.get("schemaVersion") != 1:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED")
        return state

    def _prepare_state(self, state: dict[str, Any]) -> dict[str, Any]:
        repo_fingerprint = (
            hashlib.sha256(self.public_repo_url.encode("utf-8")).hexdigest()
            if self.public_repo_url
            else None
        )
        if state.get("phase") in {"Cloning", "Publishing"}:
            if (
                state.get("gitRepoFingerprint") != repo_fingerprint
                or state.get("branch") != self.branch
            ):
                raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
            return state

        return {
            "schemaVersion": 1,
            "attemptId": uuid.uuid4().hex,
            "desiredRevision": self.revision,
            "observedRevision": state.get("observedRevision", 0),
            "gitRepoFingerprint": repo_fingerprint,
            "branch": self.branch,
            "commit": self._current_commit(),
            "phase": "Preparing",
            "publishJournal": {"expected": [], "published": []},
            "errorCode": None,
            "updatedAt": _now(),
        }

    def _bootstrap_git(self, state: dict[str, Any]) -> None:
        if state.get("phase") in {"Cloning", "Publishing"}:
            self._clone_and_publish(state)
            return

        if (self.workspace / ".git").is_dir():
            self._verify_existing_repository()
            state["commit"] = self._current_commit()
            self._save_state(state)
            return

        if self.repo_url:
            self._clone_and_publish(state)
            return

        if self.init_git:
            if self._workspace_entries():
                raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
            self._git(
                "init",
                "--initial-branch",
                os.environ.get("GIT_INIT_BRANCH", "main"),
                str(self.workspace),
            )
            self._configure_repository()
            state["commit"] = self._current_commit()
            self._save_state(state)

    def _workspace_entries(self) -> list[Path]:
        return [
            entry
            for entry in self.workspace.iterdir()
            if entry.name != ".gitkeep"
            and not entry.name.startswith(".aileron-bootstrap-stage-")
        ]

    def _clone_and_publish(self, state: dict[str, Any]) -> None:
        attempt_id = str(state["attemptId"])
        stage = self.workspace / f".aileron-bootstrap-stage-{attempt_id}"
        journal = state["publishJournal"]

        if not journal["expected"]:
            if self._workspace_entries():
                raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
            state["phase"] = "Cloning"
            state["updatedAt"] = _now()
            self._save_state(state)
            if stage.exists():
                shutil.rmtree(stage)
            try:
                self._git(
                    "clone",
                    "--branch",
                    self.branch,
                    "--",
                    self.repo_url,
                    str(stage),
                )
            except BootstrapError:
                if stage.exists():
                    shutil.rmtree(stage)
                raise
            if not (stage / ".git").is_dir():
                raise BootstrapError("WORKSPACE_GIT_BOOTSTRAP_FAILED")
            self._git(
                "-C",
                str(stage),
                "remote",
                "set-url",
                "origin",
                self.public_repo_url,
            )
            expected = sorted(entry.name for entry in stage.iterdir())
            journal["expected"] = expected
            state["phase"] = "Publishing"
            state["commit"] = self._git_output("-C", str(stage), "rev-parse", "HEAD")
            state["updatedAt"] = _now()
            self._save_state(state)

        published = set(journal["published"])
        for name in journal["expected"]:
            source = stage / name
            target = self.workspace / name
            if name in published:
                if source.exists() or not target.exists():
                    raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
                continue
            if target.exists() or target.is_symlink() or not source.exists():
                raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
            source.rename(target)
            journal["published"].append(name)
            published.add(name)
            state["updatedAt"] = _now()
            self._save_state(state)

        if stage.exists():
            stage.rmdir()
        self._verify_existing_repository()
        self._configure_repository()

    def _verify_existing_repository(self) -> None:
        try:
            self._git_output("-C", str(self.workspace), "rev-parse", "--git-dir")
            if self.repo_url:
                remote = self._git_output(
                    "-C", str(self.workspace), "remote", "get-url", "origin"
                )
                if sanitize_repository_url(remote) != self.public_repo_url:
                    raise BootstrapError("WORKSPACE_BOOTSTRAP_CONFLICT")
                if remote != self.public_repo_url:
                    self._git(
                        "-C",
                        str(self.workspace),
                        "remote",
                        "set-url",
                        "origin",
                        self.public_repo_url,
                    )
        except BootstrapError:
            raise
        except Exception as exc:
            raise BootstrapError("WORKSPACE_GIT_BOOTSTRAP_FAILED") from exc

    def _configure_repository(self) -> None:
        self._git(
            "-C",
            str(self.workspace),
            "config",
            "user.name",
            os.environ.get("GIT_USER_NAME", "Developer"),
        )
        self._git(
            "-C",
            str(self.workspace),
            "config",
            "user.email",
            os.environ.get("GIT_USER_EMAIL", "developer@workspace.local"),
        )

    def _current_commit(self) -> str | None:
        if not (self.workspace / ".git").is_dir():
            return None
        try:
            return self._git_output(
                "-C", str(self.workspace), "rev-parse", "--verify", "HEAD"
            )
        except BootstrapError:
            return None

    def _run_agent_defaults(self) -> None:
        environment = {
            **os.environ,
            "AILERON_WORKSPACE_PATH": str(self.workspace),
            "XDG_STATE_HOME": str(self.xdg_state_home),
        }
        try:
            result = subprocess.run(
                [str(self.defaults_initializer)],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise BootstrapError("AGENT_DEFAULTS_INIT_FAILED") from exc
        if result.returncode != 0:
            diagnostic = (result.stderr or "").strip()
            if diagnostic:
                print(
                    "Agent defaults initializer diagnostics: "
                    f"{diagnostic[-AGENT_DEFAULTS_DIAGNOSTIC_MAX_BYTES:]}",
                    file=sys.stderr,
                )
            raise BootstrapError("AGENT_DEFAULTS_INIT_FAILED")

    def _run_custom_setup(self) -> None:
        if not self.setup_script.is_file():
            raise BootstrapError("CUSTOM_SETUP_FAILED")
        output_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.bootstrap_dir,
                prefix=".custom-setup-",
                delete=False,
            ) as output:
                output_path = Path(output.name)
                os.chmod(output.name, 0o600)
                result = subprocess.run(
                    ["/bin/sh", str(self.setup_script)],
                    cwd=self.workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=self.setup_timeout,
                    check=False,
                    preexec_fn=self._setup_limits,
                )
            if result.returncode != 0:
                raise BootstrapError("CUSTOM_SETUP_FAILED")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BootstrapError("CUSTOM_SETUP_FAILED") from exc
        finally:
            if output_path is not None:
                output_path.unlink(missing_ok=True)

    def _setup_limits(self) -> None:
        os.umask(0o007)
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (self.setup_output_limit, self.setup_output_limit),
        )

    def _git(self, *arguments: str) -> None:
        self._git_output(*arguments)

    def _git_output(self, *arguments: str) -> str:
        try:
            result = subprocess.run(
                build_git_command(self.workspace, *arguments),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise BootstrapError("WORKSPACE_GIT_BOOTSTRAP_FAILED") from exc
        if result.returncode != 0:
            raise BootstrapError("WORKSPACE_GIT_BOOTSTRAP_FAILED")
        return result.stdout.strip()

    def _save_state(self, state: dict[str, Any]) -> None:
        state["updatedAt"] = _now()
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.bootstrap_dir,
                prefix=".state.",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(state, output, separators=(",", ":"), sort_keys=True)
                output.write("\n")
            os.chmod(temporary_path, 0o600)
            temporary_path.replace(self.state_path)
        except OSError as exc:
            raise BootstrapError("RUNTIME_STATE_INIT_FAILED") from exc


def _write_termination_code(code: str) -> None:
    path = Path(os.environ.get("TERMINATION_LOG_PATH", "/dev/termination-log"))
    try:
        path.write_text(f"{code}\n", encoding="ascii")
    except OSError:
        pass


def main() -> int:
    try:
        WorkspaceRuntimeInitializer().run()
    except BootstrapError as exc:
        _write_termination_code(exc.code)
        print(exc.code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
