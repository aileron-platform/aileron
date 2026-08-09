"""Private Marketplace import source support mixin."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, parse_qs, urlparse

from aileron_git_core import GitCommandError as CoreGitCommandError
from aileron_git_core import git_allow_failure

from app.modules.marketplace.models import (
    MarketplaceImportCandidate,
    MarketplaceImportSource,
)
from app.modules.version_control.remote import user_git_environment

from .registry_operations import (
    MarketplaceImportSourceError,
    MarketplacePathError,
)


class _MarketplaceImportSourceSupport:
    """Provide import source support behavior to the composed private kernel."""

    def _resolve_import_candidate_source(
        self,
        user_id: str,
        source_root: Path,
        candidate: MarketplaceImportCandidate,
        import_metadata: dict[str, Any],
    ) -> tuple[Path, Path | None]:
        if candidate.source_metadata.get("kind") == "git":
            return self._resolve_nested_remote_import_candidate_source(
                user_id,
                candidate,
                import_metadata,
            )
        if self._get_adapter(candidate.provider).is_remote_source_value(
            candidate.source_path
        ):
            legacy_metadata = self._legacy_remote_source_metadata(candidate.source_path)
            if legacy_metadata:
                candidate = candidate.model_copy(
                    update={"source_metadata": legacy_metadata}
                )
                return self._resolve_nested_remote_import_candidate_source(
                    user_id,
                    candidate,
                    import_metadata,
                )
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.source_path_not_found"
            )
        if candidate.source_path == ".":
            package_path = source_root.resolve()
        else:
            package_path = (source_root / candidate.source_path).resolve()
        try:
            package_path.relative_to(source_root.resolve())
        except ValueError as exc:
            raise MarketplacePathError("marketplace.validation.path_escape") from exc
        if not package_path.exists() or not package_path.is_dir():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.source_path_not_found"
            )
        return package_path, None

    def _resolve_nested_remote_import_candidate_source(
        self,
        user_id: str,
        candidate: MarketplaceImportCandidate,
        import_metadata: dict[str, Any],
    ) -> tuple[Path, Path]:
        url = candidate.source_metadata.get("url")
        if not isinstance(url, str) or not url.strip():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.source_path_not_found"
            )
        checkout_parent = Path(
            tempfile.mkdtemp(prefix="nested-", dir=self._import_work_root(user_id))
        )
        checkout_root = checkout_parent / "checkout"
        try:
            self._clone_nested_import_source(
                url.strip(),
                checkout_root,
                ref=self._optional_string(candidate.source_metadata.get("ref")),
                sha=self._optional_string(candidate.source_metadata.get("sha")),
                git_env=self._nested_import_git_environment(
                    url.strip(), user_id, import_metadata
                ),
            )
            raw_path = candidate.source_metadata.get("path")
            relative_path = (
                raw_path.strip()
                if isinstance(raw_path, str) and raw_path.strip()
                else "."
            )
            package_path = (
                checkout_root.resolve()
                if relative_path == "."
                else (checkout_root / relative_path).resolve()
            )
            try:
                package_path.relative_to(checkout_root.resolve())
            except ValueError as exc:
                raise MarketplacePathError(
                    "marketplace.validation.path_escape"
                ) from exc
            if not package_path.exists() or not package_path.is_dir():
                raise MarketplaceImportSourceError(
                    "marketplace.import.validation.source_path_not_found"
                )
            return package_path, checkout_parent
        except Exception:
            shutil.rmtree(checkout_parent, ignore_errors=True)
            raise

    def _legacy_remote_source_metadata(self, source_path: str) -> dict[str, Any] | None:
        if ".git:" in source_path:
            url, path = source_path.split(".git:", 1)
            return {
                "kind": "git",
                "sourceType": "url",
                "url": f"{url}.git",
                "path": path,
            }
        return {
            "kind": "git",
            "sourceType": "url",
            "url": source_path,
        }

    def _optional_string(self, value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _nested_import_git_environment(
        self,
        url: str,
        user_id: str,
        import_metadata: dict[str, Any],
    ) -> dict[str, str] | None:
        parsed = self._parse_git_import_source(url)
        if parsed["scheme"] != "ssh":
            return None
        git_env = import_metadata.get("gitEnvironment")
        if isinstance(git_env, dict):
            return git_env
        raise MarketplaceImportSourceError("VC_SSH_KEY_REQUIRED")

    def _clone_nested_import_source(
        self,
        url: str,
        checkout_root: Path,
        *,
        ref: str | None = None,
        sha: str | None = None,
        git_env: dict[str, str] | None = None,
    ) -> None:
        command = ["git", "clone"]
        if ref:
            command.extend(["--depth", "1", "--branch", ref])
        elif not sha:
            command.extend(["--depth", "1"])
        command.extend([url, str(checkout_root)])
        try:
            result = git_allow_failure(
                checkout_root.parent,
                *command[1:],
                timeout_seconds=180,
                env=git_env,
            )
        except (CoreGitCommandError, OSError) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            ) from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            )
        if sha:
            checkout_result = git_allow_failure(
                checkout_root,
                "checkout",
                "--detach",
                sha,
                timeout_seconds=60,
                env=git_env,
            )
            if checkout_result.returncode != 0:
                raise MarketplaceImportSourceError(
                    "marketplace.import.validation.clone_failed"
                )
        if not checkout_root.exists() or not checkout_root.is_dir():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            )

    def _import_work_root(self, user_id: str) -> Path:
        path = self._get_registry_root(user_id).parent / "import-worktrees"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @contextmanager
    def _prepared_import_source_root(
        self,
        source: MarketplaceImportSource,
        metadata: dict[str, Any],
    ) -> Iterator[Path]:
        if metadata["sourceKind"] == "local":
            yield metadata["sourceRoot"]
            return

        work_root = metadata["workRoot"]
        checkout_parent = Path(tempfile.mkdtemp(prefix="scan-", dir=work_root))
        checkout_root = checkout_parent / "checkout"
        try:
            remote_url = str(metadata.get("cloneUrl") or source.source).strip()
            with user_git_environment(
                self.db,
                user_id=str(metadata.get("userId") or ""),
                remote_url=remote_url,
            ) as git_env:
                metadata["gitEnvironment"] = git_env
                self._clone_import_source(
                    source,
                    checkout_root,
                    git_env,
                    clone_url=metadata.get("cloneUrl"),
                    ref=metadata.get("ref"),
                )
                source_root = checkout_root
                source_subpath = str(metadata.get("sourceSubpath") or "").strip()
                if source_subpath:
                    relative_path = Path(source_subpath)
                    if relative_path.is_absolute() or ".." in relative_path.parts:
                        raise MarketplaceImportSourceError(
                            "marketplace.import.validation.invalid_repository_url"
                        )
                    source_root = (checkout_root / relative_path).resolve()
                    try:
                        source_root.relative_to(checkout_root.resolve())
                    except ValueError as exc:
                        raise MarketplaceImportSourceError(
                            "marketplace.import.validation.invalid_repository_url"
                        ) from exc
                    if not source_root.is_dir():
                        raise MarketplaceImportSourceError(
                            "marketplace.import.validation.invalid_repository_url"
                        )
                yield source_root
        finally:
            metadata.pop("gitEnvironment", None)
            shutil.rmtree(checkout_parent, ignore_errors=True)

    def _clone_import_source(
        self,
        source: MarketplaceImportSource,
        checkout_root: Path,
        git_env: dict[str, str] | None = None,
        *,
        clone_url: str | None = None,
        ref: str | None = None,
    ) -> None:
        command = ["git", "clone", "--depth", "1"]
        if ref:
            command.extend(["--branch", ref])
        command.extend([clone_url or source.source.strip(), str(checkout_root)])
        try:
            result = git_allow_failure(
                checkout_root.parent,
                *command[1:],
                timeout_seconds=120,
                env=git_env,
            )
        except (CoreGitCommandError, OSError) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            ) from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            )
        if not checkout_root.exists() or not checkout_root.is_dir():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.clone_failed"
            )

    def _allowed_import_local_roots(self, user_id: str) -> list[Path]:
        user_root = self._get_registry_root(user_id).parent
        return [
            (user_root / "import-sources").resolve(),
            (self.storage_root / "import-sources").resolve(),
        ]

    def _resolve_allowed_import_local_path(self, user_id: str, source: str) -> Path:
        if not source.strip():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.source_required"
            )
        path = Path(source).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.local_path_not_found"
            ) from exc
        if not resolved.is_dir():
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.local_path_not_found"
            )
        for root in self._allowed_import_local_roots(user_id):
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise MarketplaceImportSourceError(
            "marketplace.import.validation.local_path_not_allowed"
        )

    def _parse_git_import_source(self, source: str) -> dict[str, str]:
        source = source.strip()
        if not source:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.source_required"
            )
        scp_like = self._git_scp_like_pattern.match(source)
        if scp_like:
            return {
                "scheme": "ssh",
                "host": scp_like.group("host").lower(),
                "path": scp_like.group("path").strip().rstrip("/"),
            }
        parsed = urlparse(source)
        scheme = parsed.scheme.lower()
        if scheme not in {"https", "ssh"} or not parsed.netloc:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_repository_url"
            )
        if parsed.username or parsed.password:
            if scheme == "https":
                raise MarketplaceImportSourceError(
                    "marketplace.import.validation.https_token_unsupported"
                )
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_repository_url"
            )
        return {
            "scheme": scheme,
            "host": (parsed.hostname or "").lower(),
            "path": parsed.path.strip().rstrip("/"),
            **self._github_web_import_source_metadata(parsed),
        }

    def _github_web_import_source_metadata(self, parsed: ParseResult) -> dict[str, str]:
        if (parsed.hostname or "").lower() != "github.com":
            return {}
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 4 or path_parts[2] != "tree":
            return {}
        owner, repo, _, ref = path_parts[:4]
        repo_name = repo.removesuffix(".git")
        metadata = {
            "cloneUrl": f"https://github.com/{owner}/{repo_name}.git",
            "ref": ref,
        }
        source_subpath = "/".join(path_parts[4:])
        if source_subpath:
            metadata["sourceSubpath"] = source_subpath
        return metadata

    def _reject_https_token_source(self, source: str) -> None:
        parsed = urlparse(source)
        query = parse_qs(parsed.query)
        token_keys = {"token", "access_token", "auth", "password"}
        if token_keys.intersection(query):
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.https_token_unsupported"
            )
