from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from _common import (
    SkillError,
    atomic_write_text,
    load_yaml,
    result_envelope,
    run_cli,
    site_id_hash,
    site_hostname,
    validate_base_domain,
    validate_hostname,
    validate_slug,
    workspace_operation_lock,
)


CONFIG_VERSION = 2
CONFIG_HEADER = """# Aileron Canvas publishing preferences.
# Provider credentials are Workspace environment variables, never stored here.
"""
CONFIG_FIELDS = frozenset(
    {
        "version",
        "siteId",
        "slug",
        "title",
        "buildType",
        "hostname",
        "lastSourceCommit",
        "lastPublicationId",
        "lastDeploymentActionId",
        "publicationHistory",
    }
)


def config_path(workspace: Path) -> Path:
    return workspace / ".aileron" / "canvas-publish.yaml"


def _slug_from_title(title: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")[:40].rstrip("-")
    return value if value and re.fullmatch(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", value) else "canvas-site"


def validate_site_config(data: Mapping[str, Any], *, allow_incomplete: bool = False) -> dict[str, Any]:
    # Ignore unknown fields so a hand-edited local config can never echo an
    # unexpected value, such as a credential, in a Result Envelope.
    normalized = {key: value for key, value in data.items() if key in CONFIG_FIELDS}
    if normalized.get("version", CONFIG_VERSION) != CONFIG_VERSION:
        raise SkillError("SITE_CONFIG_VERSION_UNSUPPORTED", "Canvas publishing preference version is unsupported.")
    normalized["version"] = CONFIG_VERSION

    site_id = normalized.get("siteId")
    if site_id not in (None, ""):
        try:
            normalized["siteId"] = str(UUID(str(site_id)))
        except ValueError as exc:
            raise SkillError("SITE_ID_INVALID", "siteId must be a UUID.") from exc
    elif not allow_incomplete:
        raise SkillError("SITE_ID_MISSING", "siteId is required for an existing Site.")

    slug = normalized.get("slug")
    if slug not in (None, ""):
        normalized["slug"] = validate_slug(str(slug), field="slug")
    elif not allow_incomplete:
        raise SkillError("SITE_SLUG_MISSING", "site slug is required.")

    title = normalized.get("title")
    if title not in (None, ""):
        normalized["title"] = str(title).strip()[:100]
        if not normalized["title"]:
            raise SkillError("SITE_TITLE_INVALID", "site title cannot be empty.")
    elif not allow_incomplete:
        raise SkillError("SITE_TITLE_MISSING", "site title is required.")

    build_type = normalized.get("buildType")
    if build_type not in (None, "", "static", "nextjs-standalone"):
        raise SkillError("BUILD_TYPE_UNSUPPORTED", "site build type is unsupported.")
    hostname = normalized.get("hostname")
    if hostname not in (None, ""):
        normalized["hostname"] = validate_hostname(str(hostname))
    history = normalized.get("publicationHistory")
    if history is not None:
        if not isinstance(history, list):
            raise SkillError("SITE_HISTORY_INVALID", "publicationHistory must be an array.")
        normalized["publicationHistory"] = [
            {
                key: item[key]
                for key in ("publicationId", "sourceCommit", "verified")
                if key in item
            }
            for item in history
            if isinstance(item, dict)
        ][-20:]
    return normalized


def load_site_config(workspace: Path, *, allow_incomplete: bool = False) -> dict[str, Any]:
    return validate_site_config(
        load_yaml(config_path(workspace), missing_ok=allow_incomplete),
        allow_incomplete=allow_incomplete,
    )


def write_site_config(workspace: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = validate_site_config(data, allow_incomplete=True)
    ordered = {"version": CONFIG_VERSION}
    for key in (
        "siteId",
        "slug",
        "title",
        "buildType",
        "hostname",
        "lastSourceCommit",
        "lastPublicationId",
        "lastDeploymentActionId",
        "publicationHistory",
    ):
        if normalized.get(key):
            ordered[key] = normalized[key]
    path = config_path(workspace)
    content = CONFIG_HEADER + "\n" + json.dumps(ordered, ensure_ascii=False, indent=2)
    # YAML accepts JSON, while the explicit JSON representation keeps the local pointer deterministic.
    atomic_write_text(path, content + "\n")
    return ordered


def resolve_site_config(
    workspace: Path,
    *,
    title: str,
    build_type: str,
    base_domain: str,
) -> dict[str, Any]:
    current = load_site_config(workspace, allow_incomplete=True)
    site_id = current.get("siteId") or str(uuid4())
    slug = current.get("slug") or _slug_from_title(title)
    resolved_title = current.get("title") or title.strip() or "Canvas Site"
    resolved_build_type = current.get("buildType") or build_type
    hostname = current.get("hostname") or site_hostname(slug, site_id, base_domain)
    if current.get("hostname"):
        validate_site_hostname(hostname, site_id=site_id, base_domain=base_domain)
    resolved = dict(current)
    resolved.update(
        {
            "version": CONFIG_VERSION,
            "siteId": site_id,
            "slug": slug,
            "title": resolved_title,
            "buildType": resolved_build_type,
            "hostname": hostname,
        }
    )
    return write_site_config(workspace, resolved)


def validate_site_hostname(hostname: str, *, site_id: str, base_domain: str) -> str:
    normalized_hostname = validate_hostname(hostname)
    normalized_domain = validate_base_domain(base_domain)
    expected_hash = site_id_hash(site_id)
    labels = normalized_hostname.split(".")
    if (
        not normalized_hostname.endswith(f".{normalized_domain}")
        or len(labels) < 2
        or not labels[0].endswith(f"-{expected_hash}")
    ):
        raise SkillError(
            "SITE_HOSTNAME_INVALID",
            "site hostname must be a generated hostname under the configured base domain.",
            details={"baseDomain": normalized_domain},
        )
    return normalized_hostname


def _check_config(workspace: Path) -> dict[str, Any]:
    current = load_site_config(workspace, allow_incomplete=True)
    missing = [key for key in ("siteId", "slug", "title", "buildType", "hostname") if not current.get(key)]
    return result_envelope(
        operation="check",
        status="READY" if not missing else "PREPARING",
        phase="CHECKING",
        site_id=current.get("siteId"),
        details={"missing": missing} if missing else {"config": current},
    )


def check_config(workspace: Path) -> dict[str, Any]:
    with workspace_operation_lock(workspace):
        return _check_config(workspace)


def _apply_settings(workspace: Path, settings: Sequence[str]) -> dict[str, Any]:
    current = load_site_config(workspace, allow_incomplete=True)
    for setting in settings:
        if "=" not in setting:
            raise SkillError("SITE_CONFIG_ARGUMENT_INVALID", "--set values must use key=value.")
        key, value = setting.split("=", 1)
        if key not in {"slug", "title", "buildType"}:
            raise SkillError("SITE_CONFIG_FIELD_UNSUPPORTED", "Only non-identity site preferences may be changed.", details={"field": key})
        current[key] = value.strip()
    return check_config_after_write(workspace, write_site_config(workspace, current))


def apply_settings(workspace: Path, settings: Sequence[str]) -> dict[str, Any]:
    with workspace_operation_lock(workspace):
        return _apply_settings(workspace, settings)


def check_config_after_write(workspace: Path, written: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in ("siteId", "slug", "title", "buildType", "hostname") if not written.get(key)]
    return result_envelope(
        operation="config",
        status="READY" if not missing else "PREPARING",
        phase="CHECKING",
        site_id=written.get("siteId"),
        details={"missing": missing, "config": dict(written)},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Canvas publishing preferences.")
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--set", action="append", dest="settings")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import os

    args = build_parser().parse_args(argv)
    os.environ["AILERON_PUBLISH_OPERATION"] = "config"
    workspace = args.workspace.resolve()
    return run_cli(lambda: check_config(workspace) if args.check else apply_settings(workspace, args.settings or []))


if __name__ == "__main__":
    raise SystemExit(main())
