#!/usr/bin/env python3
"""Render an isolated, standard-YAML Compose model outside the repository."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

EPHEMERAL_PORTS: dict[str, list[tuple[int, str]]] = {
    "postgres": [(5432, "tcp")],
    "redis": [(6379, "tcp")],
    "connectivity-evidence-gateway": [(8083, "tcp")],
    "frontend": [(8082, "tcp")],
}
PINNED_SERVICE_IMAGES = {
    "postgres": "postgres:15-alpine@sha256:cae15a3b718f23497a60b7cafdcf205216d7949680972da0584db00fb68bf3e6",
    "redis": "redis:7-alpine@sha256:9702d01c1f10c3ea9f48211b4362e44f154ff02d063e6f7268eba804059f53bf",
    "platform-schema-bootstrap": "postgres:15-alpine@sha256:cae15a3b718f23497a60b7cafdcf205216d7949680972da0584db00fb68bf3e6",
    "local-oidc-config": "python:3.12-alpine@sha256:aa679aa4eed6eb56c1dc6ad3f1b98b7d2d788fd961596779d188fdedad97fb38",
}
E2E_RUNNER_IMAGE = "python:3.12-alpine@sha256:aa679aa4eed6eb56c1dc6ad3f1b98b7d2d788fd961596779d188fdedad97fb38"
MANAGER_IMAGE_SERVICES = (
    "turn-readiness-preflight",
    "runtime-assertion-key-init",
    "data-service-preflight",
    "identity-bootstrap",
    "workspace-manager",
)


def ephemeral_ports(entries: list[tuple[int, str]]) -> list[dict[str, Any]]:
    return [
        {
            "target": target,
            "published": "0",
            "host_ip": "127.0.0.1",
            "protocol": protocol,
        }
        for target, protocol in entries
    ]


def require_service(document: dict[str, Any], name: str) -> dict[str, Any]:
    services = document.get("services")
    if not isinstance(services, dict) or not isinstance(services.get(name), dict):
        raise ValueError(f"required Compose service is missing: {name}")
    return services[name]


def volume_target(volume: Any) -> str | None:
    if isinstance(volume, dict):
        target = volume.get("target")
        return target if isinstance(target, str) else None
    if not isinstance(volume, str):
        return None
    delimiter = volume.rfind(":/")
    if delimiter == -1:
        return volume if volume.startswith("/") else None
    target = volume[delimiter + 1 :]
    if target.endswith((":ro", ":rw")):
        target = target.rsplit(":", 1)[0]
    return target


def remove_development_mounts(
    service: dict[str, Any], *, targets: frozenset[str]
) -> None:
    volumes = service.get("volumes")
    if not isinstance(volumes, list):
        return
    service["volumes"] = [
        volume for volume in volumes if volume_target(volume) not in targets
    ]


def render(
    source: Path,
    overlay: Path,
    output: Path,
    network_name: str,
    source_root: str,
    state_root: str,
) -> None:
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    overlay_document = yaml.safe_load(overlay.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("source Compose document must be a mapping")
    if not isinstance(overlay_document, dict):
        raise ValueError("Compose overlay document must be a mapping")

    def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if isinstance(base.get(key), dict) and isinstance(value, dict):
                merge(base[key], value)
            else:
                base[key] = value
        return base

    document = merge(document, overlay_document)

    services = document.get("services")
    if not isinstance(services, dict):
        raise ValueError("source Compose document must define services")

    for name, configuration in services.items():
        if not isinstance(configuration, dict):
            raise ValueError(f"invalid Compose service: {name}")
        configuration.pop("container_name", None)
        configuration["platform"] = "linux/amd64"

    for name, image in PINNED_SERVICE_IMAGES.items():
        require_service(document, name)["image"] = image

    for name, entries in EPHEMERAL_PORTS.items():
        require_service(document, name)["ports"] = ephemeral_ports(entries)
    require_service(document, "coturn").pop("ports", None)

    external_agent = require_service(document, "connectivity-external-agent")
    external_agent.pop("network_mode", None)
    external_agent["networks"] = ["aileron-network-dev"]
    external_agent.setdefault("environment", {})[
        "CONNECTIVITY_EVIDENCE_GATEWAY_URL"
    ] = "http://connectivity-evidence-gateway:8083/api/v1/connectivity-evidence"

    for name in MANAGER_IMAGE_SERVICES:
        remove_development_mounts(
            require_service(document, name),
            targets=frozenset({"/workspace-manager", "/workspace-manager/.venv"}),
        )
    remove_development_mounts(
        require_service(document, "frontend"),
        targets=frozenset({"/app", "/app/node_modules"}),
    )

    manager = require_service(document, "workspace-manager")
    manager_environment = manager.setdefault("environment", {})
    manager_environment["DOCKER_NETWORK"] = network_name
    manager_environment.pop("HOST_WORKSPACE_RUNTIME_DIR", None)
    require_service(document, "keycloak").setdefault("environment", {})[
        "KEYCLOAK_PUBLIC_HOSTNAME"
    ] = "http://workspace-manager:8080"

    services["e2e-runner"] = {
        "profiles": ["compose-e2e"],
        "image": E2E_RUNNER_IMAGE,
        "platform": "linux/amd64",
        "pull_policy": "never",
        "restart": "no",
        "network_mode": "service:frontend",
        "environment": {
            "COMPOSE_E2E_BASE_URL": "http://127.0.0.1:8082",
            "COMPOSE_E2E_PLATFORM_ORIGIN": "http://127.0.0.1:8082",
            "COMPOSE_E2E_USERNAME": "admin",
            "COMPOSE_E2E_KEYCLOAK_ADMIN_USERNAME": "keycloak-admin",
            "COMPOSE_E2E_RESULT_FILE": "/results/workspace-id",
        },
        "command": ["python", "/e2e/e2e.py"],
        "volumes": [
            f"{source_root}/scripts/test/compose-e2e:/e2e:ro",
            f"{state_root}/results:/results",
        ],
        "secrets": [
            "local-oidc-platform-admin-password",
            "keycloak-bootstrap-admin-password",
        ],
    }

    document["networks"] = {
        "aileron-network-dev": {"name": network_name, "driver": "bridge"}
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    yaml.safe_load(rendered)
    output.write_text(rendered, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--network-name", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--state-root", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    render(
        arguments.source,
        arguments.overlay,
        arguments.output,
        arguments.network_name,
        arguments.source_root,
        arguments.state_root,
    )


if __name__ == "__main__":
    main()
