from __future__ import annotations

import base64
import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by the image contract
    raise RuntimeError("YAML_RUNTIME_UNAVAILABLE") from exc


SKILL_ROOT = Path(__file__).resolve().parent.parent
RELEASE_SCHEMA_VERSION = 1
SCAFFOLD_VERSION = 2
DNS_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
IMAGE_BY_DIGEST_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
RESOURCE_QUANTITY_PATTERN = re.compile(
    r"^(?:0|[1-9][0-9]*)(?:m|Ki|Mi|Gi|Ti|Pi|Ei)?$"
)
BUILD_PROVIDERS = {"gitlab"}
DEPLOY_PROVIDERS = {"argocd"}
SITE_CHART_NAME = "aileron-site"
FIXED_EXCLUDES = {
    ".git",
    ".gitignore",
    ".aileronpublishignore",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    ".cache",
    ".turbo",
}
SENSITIVE_NAME_PATTERN = re.compile(
    r"(^|/)(?:\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|\.docker/config\.json|"
    r"\.aws/credentials|.*\.(?:pem|key|p12|pfx|crt|cer|secret|token)|"
    r"\.git-credentials|id_(?:rsa|ed25519)(?:\..*)?|"
    r"(?:credential|credentials|secret|secrets)(?:\..*)?)$",
    re.IGNORECASE,
)


class SkillError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        retryable: bool = False,
        next_operation: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = dict(details or {})
        self.retryable = retryable
        self.next_operation = next_operation
        self.exit_code = exit_code

    def payload(self, *, operation: str = "unknown") -> dict[str, Any]:
        return result_envelope(
            operation=operation,
            status="FAILED",
            phase="FAILED",
            error_code=self.error_code,
            retryable=self.retryable,
            next_operation=self.next_operation,
            details=self.details or None,
        )


def result_envelope(
    *,
    operation: str,
    status: str,
    phase: str,
    site_id: str | None = None,
    publication_id: str | None = None,
    deployment_action_id: str | None = None,
    evidence: Mapping[str, Any] | None = None,
    error_code: str | None = None,
    retryable: bool | None = None,
    next_operation: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": RELEASE_SCHEMA_VERSION,
        "operation": operation,
        "status": status,
        "phase": phase,
    }
    optional = {
        "siteId": site_id,
        "publicationId": publication_id,
        "deploymentActionId": deployment_action_id,
        "evidence": dict(evidence) if evidence is not None else None,
        "errorCode": error_code,
        "retryable": retryable,
        "nextOperation": next_operation,
        "details": dict(details) if details is not None else None,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    return payload


def emit_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def _operation_from_environment() -> str:
    return os.environ.get("AILERON_PUBLISH_OPERATION", "unknown")


def run_cli(action: Callable[[], Mapping[str, Any]]) -> int:
    operation = _operation_from_environment()
    try:
        emit_json(action())
        return 0
    except SkillError as exc:
        emit_json(exc.payload(operation=operation))
        return exc.exit_code
    except RuntimeError as exc:
        error_code = "YAML_RUNTIME_UNAVAILABLE" if str(exc) == "YAML_RUNTIME_UNAVAILABLE" else "UNEXPECTED_RUNTIME_ERROR"
        emit_json(
            result_envelope(
                operation=operation,
                status="FAILED",
                phase="FAILED",
                error_code=error_code,
                details=None,
            )
        )
        return 1
    except Exception:
        emit_json(
            result_envelope(
                operation=operation,
                status="FAILED",
                phase="FAILED",
                error_code="UNEXPECTED_ERROR",
            )
        )
        return 1


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_slug(value: str, *, field: str = "slug", max_length: int = 40) -> str:
    candidate = str(value).strip()
    if not candidate or len(candidate) > max_length or not DNS_LABEL_PATTERN.fullmatch(candidate):
        raise SkillError(
            "PUBLISHING_VALUE_INVALID",
            f"{field} must be a lowercase DNS label.",
            details={"field": field},
        )
    return candidate


def validate_kubernetes_name(value: str, *, field: str) -> str:
    return validate_slug(value, field=field, max_length=63)


def validate_resource_quantity(value: str, *, field: str) -> str:
    candidate = str(value).strip()
    if not RESOURCE_QUANTITY_PATTERN.fullmatch(candidate):
        raise SkillError(
            "PUBLISHING_VALUE_INVALID",
            f"{field} is not a supported Kubernetes resource quantity.",
            details={"field": field},
        )
    return candidate


def validate_image_by_digest(value: str, *, field: str) -> str:
    candidate = str(value).strip()
    if not IMAGE_BY_DIGEST_PATTERN.fullmatch(candidate):
        raise SkillError(
            "PUBLISHING_IMAGE_NOT_IMMUTABLE",
            f"{field} must use an immutable @sha256 digest.",
            details={"field": field},
        )
    return candidate


def validate_digest(value: str, *, field: str = "digest") -> str:
    candidate = str(value).strip()
    if not DIGEST_PATTERN.fullmatch(candidate):
        raise SkillError(
            "PUBLISHING_DIGEST_INVALID",
            f"{field} must be a lowercase sha256 digest.",
            details={"field": field},
        )
    return candidate


def site_id_hash(site_id: str) -> str:
    return hashlib.sha256(site_id.encode("utf-8")).hexdigest()[:12]


def validate_base_domain(value: str) -> str:
    domain = str(value).strip().strip(".").lower()
    labels = domain.split(".")
    if not domain or any(
        not label or len(label) > 63 or not DNS_LABEL_PATTERN.fullmatch(label)
        for label in labels
    ):
        raise SkillError("PUBLISHING_BASE_DOMAIN_INVALID", "base domain is invalid.")
    return domain


def site_hostname(slug: str, site_id: str, base_domain: str) -> str:
    safe_slug = validate_slug(slug)
    domain = validate_base_domain(base_domain)
    label = f"{safe_slug}-{site_id_hash(site_id)}"
    if len(label) > 63:
        raise SkillError("PUBLISHING_HOSTNAME_INVALID", "generated hostname label is too long.")
    hostname = f"{label}.{domain}"
    if len(hostname) > 253:
        raise SkillError("PUBLISHING_HOSTNAME_INVALID", "generated hostname is too long.")
    return hostname


def validate_hostname(value: str) -> str:
    hostname = str(value).strip().strip(".").lower()
    labels = hostname.split(".")
    if (
        not hostname
        or len(hostname) > 253
        or len(labels) < 2
        or any(
            not label
            or len(label) > 63
            or not DNS_LABEL_PATTERN.fullmatch(label)
            for label in labels
        )
    ):
        raise SkillError("PUBLISHING_HOSTNAME_INVALID", "hostname is invalid.")
    return hostname


def resource_name(site_id: str, *, prefix: str = "canvas-site") -> str:
    raw = f"{prefix}-{site_id_hash(site_id)}"
    return raw[:63].rstrip("-")


def build_publication_id(project_identity: str, site_id: str, source_commit: str) -> str:
    if not project_identity or not site_id or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise SkillError("PUBLICATION_ID_INPUT_INVALID", "publication identity inputs are invalid.")
    value = hashlib.sha256(
        f"{project_identity}\0{site_id}\0{source_commit}".encode("utf-8")
    ).hexdigest()[:32]
    return f"pub-{value}"


@dataclasses.dataclass(frozen=True)
class PublishingConfig:
    build_provider: str
    deploy_provider: str
    workspace_id: str
    gitlab_api: str
    gitlab_project_path: str
    gitlab_token: str = dataclasses.field(repr=False)
    argocd_url: str
    argocd_token: str = dataclasses.field(repr=False)
    argocd_project: str
    oci_registry: str
    oci_site_repository: str
    oci_chart_repository: str
    oci_push_username: str
    oci_push_password: str = dataclasses.field(repr=False)
    base_domain: str
    destination_namespace: str
    runtime_base: str
    nextjs_builder: str
    image_pull_secret_name: str
    tls_secret_name: str
    ingress_class_name: str
    release_version: str
    ca_pem: str = dataclasses.field(default="", repr=False)

    @property
    def project_identity(self) -> str:
        return self.gitlab_project_path

    @property
    def chart_repository_prefix(self) -> str:
        return f"{self.oci_registry.rstrip('/')}/{self.oci_chart_repository.strip('/')}"

    @property
    def image_repository_prefix(self) -> str:
        return f"{self.oci_registry.rstrip('/')}/{self.oci_site_repository.strip('/')}"

    def image_repository(self, site_id: str) -> str:
        return f"{self.image_repository_prefix}/{site_id_hash(site_id)}"

    def chart_repository(self, site_id: str) -> str:
        return f"{self.chart_repository_prefix}/{site_id_hash(site_id)}/{SITE_CHART_NAME}"

    def application_name(self, site_id: str) -> str:
        return resource_name(site_id)


_CONFIG_FIELDS: dict[str, tuple[str, str]] = {
    "build_provider": ("AILERON_PUBLISH_BUILD_PROVIDER", "build_provider"),
    "deploy_provider": ("AILERON_PUBLISH_DEPLOY_PROVIDER", "deploy_provider"),
    "workspace_id": ("AILERON_PUBLISH_WORKSPACE_ID", "workspace_id"),
    "gitlab_api": ("AILERON_PUBLISH_GITLAB_API", "gitlab_api"),
    "gitlab_project_path": (
        "AILERON_PUBLISH_GITLAB_PROJECT_PATH",
        "gitlab_project_path",
    ),
    "gitlab_token": ("AILERON_PUBLISH_GITLAB_TOKEN", "gitlab_token"),
    "argocd_url": ("AILERON_PUBLISH_ARGOCD_URL", "argocd_url"),
    "argocd_token": ("AILERON_PUBLISH_ARGOCD_TOKEN", "argocd_token"),
    "argocd_project": ("AILERON_PUBLISH_ARGOCD_PROJECT", "argocd_project"),
    "oci_registry": ("AILERON_PUBLISH_OCI_REGISTRY", "oci_registry"),
    "oci_site_repository": (
        "AILERON_PUBLISH_OCI_SITE_REPOSITORY",
        "oci_site_repository",
    ),
    "oci_chart_repository": (
        "AILERON_PUBLISH_OCI_CHART_REPOSITORY",
        "oci_chart_repository",
    ),
    "oci_push_username": (
        "AILERON_PUBLISH_OCI_PUSH_USERNAME",
        "oci_push_username",
    ),
    "oci_push_password": (
        "AILERON_PUBLISH_OCI_PUSH_PASSWORD",
        "oci_push_password",
    ),
    "base_domain": ("AILERON_PUBLISH_BASE_DOMAIN", "base_domain"),
    "destination_namespace": (
        "AILERON_PUBLISH_DESTINATION_NAMESPACE",
        "destination_namespace",
    ),
    "runtime_base": ("AILERON_PUBLISH_RUNTIME_BASE", "runtime_base"),
    "nextjs_builder": ("AILERON_PUBLISH_NEXTJS_BUILDER", "nextjs_builder"),
    "image_pull_secret_name": (
        "AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME",
        "image_pull_secret_name",
    ),
    "tls_secret_name": ("AILERON_PUBLISH_TLS_SECRET_NAME", "tls_secret_name"),
    "ingress_class_name": (
        "AILERON_PUBLISH_INGRESS_CLASS_NAME",
        "ingress_class_name",
    ),
    "release_version": ("AILERON_PUBLISH_RELEASE_VERSION", "release_version"),
    "ca_pem": ("AILERON_PUBLISH_CA_PEM", "ca_pem"),
}


def load_publishing_config() -> PublishingConfig:
    values = {
        field: os.environ.get(env_name, "").strip()
        for field, (env_name, _label) in _CONFIG_FIELDS.items()
    }
    missing = [field for field, value in values.items() if not value and field != "ca_pem"]
    if missing:
        raise SkillError(
            "PUBLISHING_CONFIG_MISSING",
            "Workspace publishing environment is incomplete.",
            details={"missing": missing},
            next_operation="check",
        )
    if values["build_provider"] not in BUILD_PROVIDERS or values["deploy_provider"] not in DEPLOY_PROVIDERS:
        raise SkillError(
            "PUBLISHING_PROVIDER_UNSUPPORTED",
            "Configured publishing provider is not supported by this Skill.",
            details={
                "buildProvider": values["build_provider"],
                "deployProvider": values["deploy_provider"],
            },
        )
    for field in (
        "workspace_id",
        "argocd_project",
        "destination_namespace",
        "image_pull_secret_name",
        "tls_secret_name",
        "ingress_class_name",
    ):
        validate_kubernetes_name(values[field], field=field)
    validate_base_domain(values["base_domain"])
    validate_image_by_digest(values["runtime_base"], field="runtime_base")
    validate_image_by_digest(values["nextjs_builder"], field="nextjs_builder")
    for field in ("gitlab_api", "argocd_url"):
        parsed = urllib.parse.urlsplit(values[field])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SkillError(
                "PUBLISHING_URL_INVALID",
                f"{field} must be an HTTP(S) URL.",
                details={"field": field},
            )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?::[0-9]{1,5})?", values["oci_registry"]):
        raise SkillError("PUBLISHING_REGISTRY_INVALID", "OCI registry host is invalid.")
    if any("@" in values[field] or any(char.isspace() for char in values[field]) for field in ("oci_site_repository", "oci_chart_repository")):
        raise SkillError("PUBLISHING_REGISTRY_INVALID", "OCI repository path is invalid.")
    return PublishingConfig(**values)


def load_yaml(path: Path, *, missing_ok: bool = False) -> dict[str, Any]:
    if not path.exists():
        if missing_ok:
            return {}
        raise SkillError("CONFIG_NOT_FOUND", f"Required YAML file does not exist: {path.name}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SkillError("CONFIG_PARSE_ERROR", f"Cannot parse YAML file: {path.name}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise SkillError("CONFIG_PARSE_ERROR", f"YAML file must contain an object: {path.name}")
    return loaded


def atomic_write_text(path: Path, content: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def dump_yaml(path: Path, payload: Mapping[str, Any], *, header: str | None = None) -> None:
    content = yaml.safe_dump(dict(payload), allow_unicode=True, default_flow_style=False, sort_keys=False)
    if header:
        content = f"{header.rstrip()}\n{content}"
    atomic_write_text(path, content)


def dump_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(path: Path, *, error_code: str = "JSON_PARSE_ERROR") -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillError(error_code, f"Cannot parse JSON file: {path.name}") from exc
    if not isinstance(value, dict):
        raise SkillError(error_code, f"JSON file must contain an object: {path.name}")
    return value


@contextlib.contextmanager
def materialized_ca(ca_pem: str) -> Iterator[str | None]:
    if not ca_pem:
        yield None
        return
    candidate = Path(ca_pem).expanduser()
    if "\n" not in ca_pem and candidate.is_file():
        yield str(candidate)
        return
    if "BEGIN CERTIFICATE" not in ca_pem:
        raise SkillError("PUBLISHING_CA_INVALID", "Configured CA must be a readable path or PEM certificate.")
    descriptor, name = tempfile.mkstemp(prefix="aileron-publish-ca-", suffix=".pem")
    path = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(ca_pem.rstrip() + "\n")
        path.chmod(0o600)
        yield str(path)
    finally:
        path.unlink(missing_ok=True)


def _ssl_context(ca_file: str | None) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()


class HttpClient:
    def __init__(self, base_url: str, *, headers: Mapping[str, str], ca_pem: str = "", error_code: str, secrets: Sequence[str] = ()) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers)
        self.ca_pem = ca_pem
        self.error_code = error_code
        self.secrets = tuple(secret for secret in secrets if secret)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | Sequence[Any] | None = None,
        expected: Sequence[int] = (200,),
        allow_not_found: bool = False,
        raw: bool = False,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Accept": "application/json", **self.headers}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        with materialized_ca(self.ca_pem) as ca_file:
            try:
                with urllib.request.urlopen(request, context=_ssl_context(ca_file), timeout=30) as response:
                    payload = response.read()
                    if response.status not in expected:
                        raise SkillError(self.error_code, "Remote API returned an unexpected status.", details={"status": response.status})
            except urllib.error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")
                if allow_not_found and exc.code == 404:
                    return None
                retryable = exc.code == 409 or exc.code == 429 or exc.code >= 500
                raise SkillError(
                    self.error_code,
                    "Remote API request failed.",
                    details={"status": exc.code, "response": redact_text(response_body[-1000:], *self.secrets)},
                    retryable=retryable,
                    next_operation="status" if retryable and exc.code != 409 else None,
                ) from exc
            except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
                raise SkillError(
                    self.error_code,
                    "Remote API is unreachable.",
                    details={"reason": redact_text(str(exc), *self.secrets)},
                    retryable=True,
                    next_operation="status",
                ) from exc
        if raw:
            return payload.decode("utf-8", errors="replace")
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SkillError(self.error_code, "Remote API returned invalid JSON.") from exc


class GitLabClient:
    def __init__(self, config: PublishingConfig) -> None:
        self.config = config
        self.http = HttpClient(
            config.gitlab_api,
            headers={"PRIVATE-TOKEN": config.gitlab_token},
            ca_pem=config.ca_pem,
            error_code="GITLAB_API_ERROR",
            secrets=(config.gitlab_token, config.oci_push_password),
        )

    def get_project(self, project_path: str) -> dict[str, Any] | None:
        encoded = urllib.parse.quote(project_path, safe="")
        return self.http.request("GET", f"projects/{encoded}", allow_not_found=True)

    def get_variable(
        self,
        project_id: int,
        key: str,
        *,
        environment_scope: str = "*",
    ) -> dict[str, Any] | None:
        encoded = urllib.parse.quote(key, safe="")
        scope = urllib.parse.quote(environment_scope, safe="")
        return self.http.request(
            "GET",
            f"projects/{project_id}/variables/{encoded}?filter[environment_scope]={scope}",
            allow_not_found=True,
        )

    def set_variable(
        self,
        project_id: int,
        key: str,
        value: str,
        *,
        masked: bool = False,
        environment_scope: str = "*",
    ) -> None:
        body = {
            "key": key,
            "value": value,
            "masked": masked,
            "protected": True,
            "raw": True,
            "environment_scope": environment_scope,
        }
        existing = self.get_variable(
            project_id,
            key,
            environment_scope=environment_scope,
        )
        scope = urllib.parse.quote(environment_scope, safe="")
        if existing:
            encoded = urllib.parse.quote(key, safe="")
            self.http.request(
                "PUT",
                f"projects/{project_id}/variables/{encoded}?filter[environment_scope]={scope}",
                body=body,
                expected=(200,),
            )
        else:
            self.http.request("POST", f"projects/{project_id}/variables", body=body, expected=(201,))

    def pipelines_for_sha(self, project_id: int, sha: str) -> list[dict[str, Any]]:
        encoded_sha = urllib.parse.quote(sha, safe="")
        return self.http.request(
            "GET",
            f"projects/{project_id}/pipelines?sha={encoded_sha}",
            expected=(200,),
        )

    def get_pipeline(self, project_id: int, pipeline_id: int) -> dict[str, Any]:
        return self.http.request("GET", f"projects/{project_id}/pipelines/{pipeline_id}")

    def pipeline_jobs(self, project_id: int, pipeline_id: int) -> list[dict[str, Any]]:
        return self.http.request("GET", f"projects/{project_id}/pipelines/{pipeline_id}/jobs")

    def pipeline_variables(self, project_id: int, pipeline_id: int) -> list[dict[str, Any]]:
        return self.http.request(
            "GET",
            f"projects/{project_id}/pipelines/{pipeline_id}/variables",
            expected=(200,),
        )

    def job_trace(self, project_id: int, job_id: int) -> str:
        return self.http.request("GET", f"projects/{project_id}/jobs/{job_id}/trace", raw=True)

    def trigger_pipeline(self, project_id: int, *, ref: str, variables: Mapping[str, str]) -> dict[str, Any]:
        return self.http.request(
            "POST",
            f"projects/{project_id}/pipeline",
            body={"ref": ref, "variables": [{"key": key, "value": value} for key, value in variables.items()]},
            expected=(201,),
        )


class ArgoCDClient:
    def __init__(self, config: PublishingConfig) -> None:
        self.config = config
        self.http = HttpClient(
            config.argocd_url,
            headers={"Authorization": f"Bearer {config.argocd_token}"},
            ca_pem=config.ca_pem,
            error_code="ARGOCD_API_ERROR",
            secrets=(config.argocd_token,),
        )

    def get_project(self, name: str) -> dict[str, Any] | None:
        return self.http.request("GET", f"api/v1/projects/{urllib.parse.quote(name, safe='')}", allow_not_found=True)

    def get_application(self, name: str) -> dict[str, Any] | None:
        return self.http.request("GET", f"api/v1/applications/{urllib.parse.quote(name, safe='')}", allow_not_found=True)

    def create_application(self, application: Mapping[str, Any]) -> dict[str, Any]:
        return self.http.request("POST", "api/v1/applications", body=application, expected=(200, 201))

    def update_application(self, name: str, application: Mapping[str, Any]) -> dict[str, Any]:
        return self.http.request("PUT", f"api/v1/applications/{urllib.parse.quote(name, safe='')}", body=application, expected=(200,))

    def delete_application(self, name: str, *, project: str | None = None) -> None:
        query = "cascade=true"
        if project:
            query += f"&project={urllib.parse.quote(project, safe='')}"
        self.http.request(
            "DELETE",
            f"api/v1/applications/{urllib.parse.quote(name, safe='')}?{query}",
            expected=(200, 202, 204),
        )


def redact_text(text: str, *secrets: str) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(r"(?i)(https?://[^/:\s]+):[^@/\s]+@", r"\1:[REDACTED]@", redacted)
    redacted = re.sub(
        r"(?i)([\"']?(?:password|token|secret|credential|authorization)[\"']?\s*[=:]\s*[\"']?)([^\"',}\s]+)",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def git_environment(token: str, ca_file: str | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_CONFIG_COUNT"] = "1"
    environment["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    encoded = base64.b64encode(f"oauth2:{token}".encode("utf-8")).decode("ascii")
    environment["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"
    if ca_file:
        environment["GIT_SSL_CAINFO"] = ca_file
    return environment


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    error_code: str = "COMMAND_FAILED",
    secrets: Sequence[str] = (),
) -> str:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise SkillError(
            error_code,
            "Command failed.",
            details={
                "command": command[0],
                "output": redact_text(completed.stderr[-1000:], *secrets),
            },
        )
    return completed.stdout.strip()


def configure_git_identity(repo: Path) -> None:
    run_command(["git", "config", "user.name", "Aileron Canvas Publishing"], cwd=repo)
    run_command(["git", "config", "user.email", "canvas-publishing@aileron.local"], cwd=repo)


@contextlib.contextmanager
def temporary_directory(prefix: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=prefix) as name:
        yield Path(name)


@contextlib.contextmanager
def workspace_operation_lock(workspace: Path) -> Iterator[None]:
    lock_path = workspace / ".aileron" / ".canvas-publish.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SkillError(
                "PUBLISHING_OPERATION_CONFLICT",
                "another Canvas publishing operation is already running for this Workspace.",
                retryable=True,
                next_operation="status",
            ) from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def clone_repository(repo_url: str, destination: Path, *, token: str, ca_pem: str = "", allow_empty: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with materialized_ca(ca_pem) as ca_file:
        completed = subprocess.run(["git", "clone", repo_url, str(destination)], env=git_environment(token, ca_file), check=False, capture_output=True, text=True)
    if completed.returncode:
        output = redact_text(completed.stderr, token)
        if allow_empty and "empty repository" in output.lower():
            destination.mkdir(parents=True, exist_ok=True)
            run_command(["git", "init", "--initial-branch=main"], cwd=destination, error_code="GIT_OPERATION_FAILED")
            run_command(["git", "remote", "add", "origin", repo_url], cwd=destination, error_code="GIT_OPERATION_FAILED")
            configure_git_identity(destination)
            return
        raise SkillError("GIT_OPERATION_FAILED", "Cannot clone publishing repository.", details={"output": output})
    configure_git_identity(destination)


def git_remote_head(repo: Path, *, branch: str, token: str, ca_pem: str = "") -> str | None:
    with materialized_ca(ca_pem) as ca_file:
        output = run_command(["git", "ls-remote", "origin", f"refs/heads/{branch}"], cwd=repo, env=git_environment(token, ca_file), error_code="GIT_OPERATION_FAILED")
    return output.split()[0] if output else None


def checkout_branch(repo: Path, branch: str, *, start_point: str = "main") -> None:
    existing = subprocess.run(["git", "show-ref", "--verify", f"refs/heads/{branch}"], cwd=repo, check=False, capture_output=True)
    if existing.returncode == 0:
        run_command(["git", "checkout", branch], cwd=repo, error_code="GIT_OPERATION_FAILED")
    else:
        run_command(["git", "checkout", "-b", branch, start_point], cwd=repo, error_code="GIT_OPERATION_FAILED")


def git_push(repo: Path, *, token: str, ca_pem: str, branch: str, expected_head: str | None) -> str:
    actual_head = git_remote_head(repo, branch=branch, token=token, ca_pem=ca_pem)
    if actual_head != expected_head:
        raise SkillError(
            "PUBLISHING_SOURCE_CONFLICT",
            "Site Source Branch changed while the publication was prepared.",
            details={"branch": branch, "expectedHead": expected_head, "actualHead": actual_head},
            retryable=False,
            next_operation="publish",
        )
    with materialized_ca(ca_pem) as ca_file:
        try:
            run_command(
                ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
                cwd=repo,
                env=git_environment(token, ca_file),
                error_code="GIT_OPERATION_FAILED",
                secrets=(token,),
            )
        except SkillError as exc:
            if "non-fast-forward" in str(exc).lower() or "rejected" in str(exc).lower():
                raise SkillError("PUBLISHING_SOURCE_CONFLICT", "Site Source Branch rejected the update.") from exc
            raise
    return run_command(["git", "rev-parse", "HEAD"], cwd=repo, error_code="GIT_OPERATION_FAILED")


def git_head(repo: Path) -> str:
    return run_command(["git", "rev-parse", "HEAD"], cwd=repo, error_code="GIT_OPERATION_FAILED")


def git_has_changes(repo: Path) -> bool:
    return bool(run_command(["git", "status", "--porcelain"], cwd=repo, error_code="GIT_OPERATION_FAILED"))


def ensure_within(root: Path, candidate: Path, *, error_code: str) -> Path:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise SkillError(error_code, "Resolved path escapes the allowed root.") from exc
    return resolved_candidate


def _read_ignore_file(source: Path) -> set[str]:
    path = source / ".aileronpublishignore"
    if not path.is_file():
        return set()
    return {line.strip().lstrip("/") for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


def copy_content_tree(source: Path, destination: Path) -> None:
    ignores = _read_ignore_file(source)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for current, directories, files in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(source)
        filtered_directories: list[str] = []
        for name in sorted(directories):
            relative = (relative_dir / name).as_posix()
            candidate = current_path / name
            if candidate.is_symlink():
                raise SkillError("PUBLISHING_SOURCE_SYMLINK", "Site source cannot contain symlinks.", details={"path": relative})
            if is_sensitive_path(relative):
                raise SkillError("PUBLISHING_SOURCE_SECRET", "Site source contains a protected credential-like path.", details={"path": relative})
            if name in FIXED_EXCLUDES or relative in ignores or any(relative == item or relative.startswith(f"{item}/") for item in ignores):
                continue
            filtered_directories.append(name)
        directories[:] = filtered_directories
        target_dir = destination / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            source_path = current_path / name
            relative = (relative_dir / name).as_posix()
            if source_path.is_symlink() or not source_path.is_file():
                raise SkillError("PUBLISHING_SOURCE_FILE_INVALID", "Site source only accepts regular files.", details={"path": relative})
            if name in FIXED_EXCLUDES or relative in ignores or any(relative == item or relative.startswith(f"{item}/") for item in ignores):
                continue
            if is_sensitive_path(relative):
                raise SkillError("PUBLISHING_SOURCE_SECRET", "Site source contains a protected credential-like path.", details={"path": relative})
            shutil.copy2(source_path, target_dir / name)


def is_sensitive_path(relative: str) -> bool:
    return bool(SENSITIVE_NAME_PATTERN.search(relative))
