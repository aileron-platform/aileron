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
    "openldap": [(389, "tcp")],
}


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


def render(
    source: Path,
    output: Path,
    network_name: str,
    source_root: str,
    state_root: str,
) -> None:
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("source Compose document must be a mapping")

    services = document.get("services")
    if not isinstance(services, dict):
        raise ValueError("source Compose document must define services")

    for name, configuration in services.items():
        if not isinstance(configuration, dict):
            raise ValueError(f"invalid Compose service: {name}")
        configuration.pop("container_name", None)

    for name, entries in EPHEMERAL_PORTS.items():
        require_service(document, name)["ports"] = ephemeral_ports(entries)
    require_service(document, "coturn").pop("ports", None)

    external_agent = require_service(document, "connectivity-external-agent")
    external_agent.pop("network_mode", None)
    external_agent["networks"] = ["aileron-network-dev"]
    external_agent.setdefault("environment", {})[
        "CONNECTIVITY_EVIDENCE_GATEWAY_URL"
    ] = "http://connectivity-evidence-gateway:8083/api/v1/connectivity-evidence"

    manager = require_service(document, "workspace-manager")
    manager.setdefault("environment", {})["DOCKER_NETWORK"] = network_name
    require_service(document, "keycloak").setdefault("environment", {})[
        "KC_HOSTNAME"
    ] = "http://workspace-manager:8080"

    services["e2e-runner"] = {
        "profiles": ["compose-e2e"],
        "image": "python:3.12-alpine",
        "pull_policy": "never",
        "restart": "no",
        "network_mode": "service:frontend",
        "environment": {
            "COMPOSE_E2E_BASE_URL": "http://127.0.0.1:8082",
            "COMPOSE_E2E_PLATFORM_ORIGIN": "http://127.0.0.1:8082",
            "COMPOSE_E2E_USERNAME": "admin",
            "COMPOSE_E2E_RESULT_FILE": "/results/workspace-id",
        },
        "command": ["python", "/e2e/e2e.py"],
        "volumes": [
            f"{source_root}/scripts/test/compose-e2e:/e2e:ro",
            f"{state_root}/results:/results",
        ],
        "secrets": ["local-admin-password"],
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
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--network-name", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--state-root", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    render(
        arguments.source,
        arguments.output,
        arguments.network_name,
        arguments.source_root,
        arguments.state_root,
    )


if __name__ == "__main__":
    main()
