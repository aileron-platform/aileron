from __future__ import annotations

import json
import os
from pathlib import Path
import re


class ValidationError(Exception):
    pass


SENSITIVE_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|\.docker/config\.json|"
    r"\.aws/credentials|.*\.(?:pem|key|p12|pfx|crt|cer|secret|token)|"
    r"\.git-credentials|id_(?:rsa|ed25519)(?:\..*)?|"
    r"(?:credential|credentials|secret|secrets)(?:\..*)?)$",
    re.IGNORECASE,
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValidationError(f"missing required pipeline variable: {name}")
    return value


def is_sensitive_path(path: Path) -> bool:
    return bool(SENSITIVE_PATH_PATTERN.search(path.as_posix()))


def main() -> int:
    branch = os.environ.get("CI_COMMIT_REF_NAME", "")
    if not branch.startswith("sites/") or branch.count("/") != 1:
        raise ValidationError("pipeline must run on one sites/<siteId> branch")
    if os.environ.get("CI_COMMIT_REF_PROTECTED") != "true":
        raise ValidationError("pipeline must run on a protected site branch")

    manifest_path = Path(".aileron/publishing/site-manifest.json")
    if not manifest_path.is_file():
        raise ValidationError("managed site manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("managed site manifest is invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValidationError("managed site manifest must be an object")

    site_id = required("AILERON_PUBLISH_SITE_ID")
    publication_id = required("AILERON_PUBLISH_PUBLICATION_ID")
    source_commit = required("AILERON_PUBLISH_SOURCE_COMMIT")
    build_type = required("AILERON_PUBLISH_BUILD_TYPE")
    if branch != f"sites/{site_id}":
        raise ValidationError("pipeline branch does not match the requested siteId")
    if os.environ.get("CI_COMMIT_SHA") != source_commit:
        raise ValidationError("pipeline source commit does not match CI_COMMIT_SHA")
    if not publication_id.startswith("pub-"):
        raise ValidationError("publicationId must start with pub-")
    if manifest.get("siteId") != site_id:
        raise ValidationError("manifest siteId does not match the pipeline variable")
    if manifest.get("buildType") != build_type:
        raise ValidationError("manifest buildType does not match the pipeline variable")
    if manifest.get("sourceRoot") != "source":
        raise ValidationError("managed sourceRoot must be source")
    source = Path("source")
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("managed source directory is missing")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValidationError("source contains a symlink")
        if is_sensitive_path(path):
            raise ValidationError("source contains a protected credential-like path")
    print(
        json.dumps(
            {"status": "ok", "siteId": site_id, "publicationId": publication_id},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
