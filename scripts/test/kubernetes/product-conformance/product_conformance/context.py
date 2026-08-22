"""Shared state and real service adapters for product conformance."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from kubernetes import client

from .api import ExternalOidcFixtureClient, ManagerClient, OidcTestUser, require_status
from .cluster import ProductCluster
from .database import ProductDatabase


@dataclass(frozen=True)
class ProductConfig:
    namespace: str
    run_id: str
    release: str
    manager_url: str
    platform_public_origin: str
    oidc_adapter_url: str
    oidc_issuer_url: str
    oidc_discovery_url: str
    postgres_dsn: str
    report_path: Path
    driver_image: str
    image_pull_policy: str
    storage_class: str
    storage_mode: str
    nfs_server: str | None
    storage_gid: int
    runtime_image: str
    browser_image: str
    canvas_image: str
    image_pull_secret_name: str | None = None
    oidc_client_id: str = "aileron-frontend"

    @classmethod
    def from_environment(cls) -> "ProductConfig":
        storage_mode = _required_env("E2E_STORAGE_MODE")
        if storage_mode not in {"static-nfs", "dynamic"}:
            raise RuntimeError("E2E_STORAGE_MODE must be static-nfs or dynamic")
        nfs_server = os.getenv("NFS_SERVER")
        if storage_mode == "static-nfs" and not nfs_server:
            raise RuntimeError("NFS_SERVER is required for static-nfs storage")
        if storage_mode == "dynamic":
            nfs_server = None
        oidc_issuer_url = _required_env("PRODUCT_OIDC_ISSUER_URL").rstrip("/")
        return cls(
            namespace=_required_env("E2E_NAMESPACE"),
            run_id=_required_env("E2E_RUN_ID"),
            release=os.getenv("PRODUCT_HELM_RELEASE", "product"),
            manager_url=_required_env("PRODUCT_MANAGER_URL").rstrip("/"),
            platform_public_origin=_required_env("PRODUCT_PLATFORM_PUBLIC_ORIGIN"),
            oidc_adapter_url=_required_env("PRODUCT_OIDC_ADAPTER_URL").rstrip("/"),
            oidc_issuer_url=oidc_issuer_url,
            oidc_discovery_url=(f"{oidc_issuer_url}/.well-known/openid-configuration"),
            postgres_dsn=_required_env("PRODUCT_POSTGRES_DSN"),
            report_path=Path(
                os.getenv("PRODUCT_REPORT_PATH", "/evidence/product-report.json")
            ),
            driver_image=_required_env("PRODUCT_DRIVER_IMAGE"),
            image_pull_policy=os.getenv("IMAGE_PULL_POLICY", "Never"),
            storage_class=_required_env("RWX_STORAGE_CLASS"),
            storage_mode=storage_mode,
            nfs_server=nfs_server,
            storage_gid=int(os.getenv("PLATFORM_STORAGE_GID", "2000")),
            runtime_image=_required_env("RUNTIME_IMAGE"),
            browser_image=_required_env("BROWSER_IMAGE"),
            canvas_image=_required_env("CANVAS_IMAGE"),
            image_pull_secret_name=os.getenv("IMAGE_PULL_SECRET_NAME") or None,
            oidc_client_id=os.getenv("PRODUCT_OIDC_CLIENT_ID", "aileron-frontend"),
        )


class ProductContext:
    """State shared by ordered, evidence-producing product scenarios."""

    def __init__(
        self,
        settings: ProductConfig,
        *,
        core: client.CoreV1Api,
        apps: client.AppsV1Api,
        custom: client.CustomObjectsApi,
        discovery: client.DiscoveryV1Api,
    ) -> None:
        self.settings = settings
        self.http = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
        self.db = ProductDatabase(settings.postgres_dsn)
        self.cluster = ProductCluster(
            namespace=settings.namespace,
            release=settings.release,
            run_id=settings.run_id,
            driver_image=settings.driver_image,
            image_pull_policy=settings.image_pull_policy,
            storage_class=settings.storage_class,
            storage_mode=settings.storage_mode,
            nfs_server=settings.nfs_server,
            storage_gid=settings.storage_gid,
            core=core,
            apps=apps,
            custom=custom,
            discovery=discovery,
        )
        self.oidc_adapter = ExternalOidcFixtureClient(
            self.http,
            base_url=settings.oidc_adapter_url,
            client_id=settings.oidc_client_id,
        )
        self.sessions: dict[str, tuple[str, str]] = {}
        self.users: dict[str, OidcTestUser] = {}
        self.manager = ManagerClient(
            self.http,
            base_url=settings.manager_url,
            public_origin=settings.platform_public_origin,
            sessions=self.sessions,
        )
        self.workspace_id = ""
        self.workspace_name = ""
        self.knowledge_base_ids: dict[str, str] = {}
        self.share_ids: dict[str, str] = {}
        self.runtime_instance_id = ""
        self.workspace_service_urls: dict[str, str] = {}
        self.lifecycle_start_job_id = ""
        self.workspace_lifetime_uids: dict[str, str] = {}
        self.workspace_storage_markers: dict[str, str] = {}
        self.external_oidc_observation: dict[str, Any] = {}

    def close(self) -> None:
        self.http.close()

    def verify_logout(self) -> None:
        session = self.sessions.get("owner")
        if session is None:
            raise AssertionError("Owner BFF session is unavailable for logout proof")
        response = self._retry_transport(
            lambda: self.manager.request(
                "owner",
                "POST",
                "/api/v1/oauth2/logout",
            )
        )
        require_status(response, 200, operation="Manager BFF logout")
        provider_url = response.json().get("provider_logout_url")
        if not isinstance(provider_url, str) or not provider_url.startswith(
            self.settings.oidc_issuer_url
        ):
            raise AssertionError(
                "Manager logout did not return the external provider endpoint"
            )
        require_status(
            self._retry_transport(lambda: self.http.get(provider_url)),
            204,
            operation="external provider logout",
        )
        expired = self._retry_transport(
            lambda: self.http.get(
                f"{self.settings.manager_url}/api/v1/oauth2/session",
                headers={"Cookie": f"aileron_session={session[0]}"},
            )
        )
        require_status(expired, 401, operation="revoked Manager session")

    @staticmethod
    def _retry_transport(
        operation: Callable[[], Any],
        *,
        timeout_seconds: float = 120,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                return operation()
            except httpx.TransportError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)

    def assert_prerequisites(self) -> None:
        manager_response = self.http.get(f"{self.settings.manager_url}/health")
        require_status(manager_response, 200, operation="Manager health")
        manager_health = manager_response.json()
        if manager_health.get("status") not in {"healthy", "ok"}:
            raise AssertionError(f"Manager health is not ready: {manager_health!r}")

        discovery = require_status(
            self.http.get(self.settings.oidc_discovery_url),
            200,
            operation="external OIDC fixture discovery",
        ).json()
        if discovery.get("aileron_test_provider") != "provider-neutral-non-keycloak":
            raise AssertionError(
                "product conformance is not connected to the disposable non-Keycloak provider"
            )
        authorization_endpoint = discovery.get("authorization_endpoint")
        if not isinstance(authorization_endpoint, str) or not authorization_endpoint:
            raise AssertionError("external OIDC fixture has no authorization endpoint")

        self.db.ping()
        self.cluster.core.read_namespace(self.settings.namespace)
        self.cluster.list_endpoint_slices(limit=1)
        self.cluster.wait_supervisor_processes(
            {
                "fastapi": "RUNNING",
                "celery-worker": "RUNNING",
                "celery-beat": "RUNNING",
            }
        )
        self._provision_test_actors()
        self.external_oidc_observation = {
            "fixture": discovery["aileron_test_provider"],
            "issuer": discovery.get("issuer"),
            "authorizationEndpoint": authorization_endpoint,
            "callbackPath": "/api/v1/oauth2/callback",
            "actors": {
                actor: {
                    "subject": user.id,
                    "sessionIssued": actor in self.sessions,
                    "jitWorkspaceListAccepted": True,
                }
                for actor, user in self.users.items()
            },
        }

    def request_owner(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._request_manager("owner", method, path, **kwargs)

    def request_actor(
        self,
        actor: str,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._request_manager(actor, method, path, **kwargs)

    def _request_manager(
        self,
        actor: str,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        response = self.manager.request(actor, method, path, **kwargs)
        if response.status_code != 401:
            return response

        credential_actor = "editor" if actor == "collaborator" else actor
        user = self.users.get(credential_actor)
        if user is None:
            return response
        self._wait_actor_reconciliation(
            actor=credential_actor,
            username=user.username,
        )
        self.sessions[actor] = self.sessions[credential_actor]
        return self.manager.request(actor, method, path, **kwargs)

    def establish_workspace_shares(self) -> dict[str, str]:
        if not self.workspace_id:
            raise AssertionError("Workspace must exist before shares are created")
        for actor, role in (("editor", "manager"), ("reader", "reader")):
            candidate_response = self.request_owner(
                "GET",
                f"/workspaces/{self.workspace_id}/share-candidate-users",
                params={"query": self.users[actor].email, "limit": 8},
            )
            require_status(
                candidate_response,
                200,
                operation=f"resolve {actor} workspace share candidate",
            )
            candidates = candidate_response.json().get("items")
            if not isinstance(candidates, list) or len(candidates) != 1:
                raise AssertionError(
                    f"Expected one workspace share candidate for {actor}"
                )
            target_id = candidates[0].get("id")
            if not isinstance(target_id, str) or not target_id:
                raise AssertionError(
                    f"Workspace share candidate id is missing for {actor}"
                )
            response = self.request_owner(
                "POST",
                f"/workspaces/{self.workspace_id}/shares",
                json={"targetType": "user", "targetId": target_id, "role": role},
            )
            require_status(
                response,
                201,
                operation=f"create {actor} workspace share",
            )
            share_id = response.json().get("id")
            if not isinstance(share_id, str) or not share_id:
                raise AssertionError(f"Workspace share id is missing for {actor}")
            self.share_ids[actor] = share_id
        self.share_ids["collaborator"] = self.share_ids["editor"]
        self.sessions["collaborator"] = self.sessions["editor"]
        return dict(self.share_ids)

    def refresh_generation(self) -> dict[str, Any]:
        self.cluster.wait_workspace_ready(self.workspace_id)
        generation = self.cluster.get_generation(self.workspace_id)
        runtime_instance_id = generation.get("runtimeInstanceId")
        if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
            raise AssertionError("Ready Workspace CR has no runtime instance id")
        self.runtime_instance_id = runtime_instance_id
        self.workspace_service_urls = self.cluster.workspace_urls(self.workspace_id)
        return generation

    def execution_grant(
        self,
        actor: str,
        *,
        audience: str,
        actions: list[str],
    ) -> str:
        self.refresh_generation()
        response = self.request_actor(
            actor,
            "POST",
            f"/workspaces/{self.workspace_id}/execution-grants",
            json={
                "runtimeInstanceId": self.runtime_instance_id,
                "audience": audience,
                "actions": actions,
            },
        )
        require_status(response, 200, operation=f"issue {audience} grant for {actor}")
        grant = response.json().get("grant")
        if not isinstance(grant, str) or not grant:
            raise AssertionError(f"Manager returned no {audience} grant for {actor}")
        return grant

    def _provision_test_actors(self) -> None:
        suffix = re.sub(r"[^a-z0-9]+", "-", self.settings.run_id.lower()).strip("-")
        suffix = suffix[-24:] or "run"
        password = "ProductE2e123!"
        actor_specs = {
            "owner": "admin",
            "editor": "developer",
            "reader": "reader",
        }
        for actor, realm_role in actor_specs.items():
            username = f"e2e-{actor}-{suffix}"
            user = self.oidc_adapter.create_realm_user(
                username=username,
                email=f"{username}@example.test",
                password=password,
                realm_role=realm_role,
            )
            self.users[actor] = user
            self._wait_actor_reconciliation(
                actor=actor,
                username=username,
            )

    def _wait_actor_reconciliation(
        self,
        *,
        actor: str,
        username: str,
        timeout_seconds: float = 120,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_status: int | None = None
        last_body = ""
        while time.monotonic() < deadline:
            self.sessions[actor] = self.oidc_adapter.login(
                manager_url=self.settings.manager_url,
                username=username,
            )
            response = self.manager.request(actor, "GET", "/workspaces")
            if response.status_code == 200:
                return
            last_status = response.status_code
            last_body = response.text[:500]
            if response.status_code not in {401, 403, 409, 429, 503}:
                require_status(
                    response,
                    200,
                    operation=f"reconcile Manager user {actor}",
                )
            time.sleep(1)
        raise AssertionError(
            f"Manager user reconciliation timed out for {actor}: "
            f"status={last_status}, body={last_body!r}"
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
