"""工作區服務"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.models import (
    FirewallConfig,
    Pagination,
    RuntimeStatus,
    WorkspaceComponents,
    WorkspaceComponentStatus,
    WorkspaceCreateRequest,
    WorkspaceDetail,
    WorkspaceEnvVar,
    WorkspaceListResponse,
    WorkspaceOwner,
    WorkspacePortMapping,
    WorkspaceSystemPortMapping,
    WorkspaceResourceRequirements,
    WorkspaceRuntimeJobSummary,
    WorkspaceSummary,
    WorkspaceUpdateRequest,
)
from app.utils.string_utils import snake_case
from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService


class WorkspaceService:
    """負責管理工作區資料"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    # -- 資料查詢 ---------------------------------------------------------

    def list(
        self,
        *,
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> WorkspaceListResponse:
        query = select(db_models.Workspace).join(db_models.User)

        if owner_id:
            query = query.where(db_models.Workspace.owner_id == owner_id)
        if status:
            query = query.where(db_models.Workspace.runtime_status == status)
        if search:
            like_pattern = f"%{search}%"
            query = query.where(db_models.Workspace.name.ilike(like_pattern))

        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0

        records = (
            self.db.execute(
                query.order_by(db_models.Workspace.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        self._sync_kubernetes_workspace_records(records)

        items = [self._to_summary(workspace) for workspace in records]
        pagination = Pagination(page=page, page_size=page_size, total=total)
        return WorkspaceListResponse(items=items, pagination=pagination)

    def get(self, workspace_id: str) -> Optional[WorkspaceDetail]:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return None
        self._sync_kubernetes_workspace_record(workspace)
        return self._to_detail(workspace)

    # -- 資料寫入 ---------------------------------------------------------

    def create(self, payload: WorkspaceCreateRequest) -> WorkspaceDetail:
        owner = self.db.get(db_models.User, payload.owner_id)
        if not owner:
            raise ValueError("Owner not found")

        provisioner = self._resolve_workspace_provisioner()
        self._ensure_port_mappings_supported(
            provisioner=provisioner,
            port_mappings=payload.port_mappings,
        )
        if payload.firewall is not None:
            self._ensure_firewall_available(provisioner=provisioner)
        target_namespace = self._resolve_target_namespace(
            provisioner=provisioner,
            target_namespace=payload.target_namespace,
        )
        runtime_resources = self._resolve_runtime_resources_for_write(
            provisioner=provisioner,
            runtime_resources=payload.runtime_resources,
        )

        default_internal_port = 3002
        external_port = None

        for mapping in payload.port_mappings:
            if mapping.container_port == default_internal_port and mapping.host_port:
                external_port = mapping.host_port

        workspace = db_models.Workspace(
            id=str(uuid4()),
            owner_id=payload.owner_id,
            name=payload.name,
            description=payload.description,
            git_url=payload.git_url,
            branch=payload.branch or "main",
            runtime=payload.runtime,
            provisioner=provisioner,
            target_namespace=target_namespace,
            runtime_resources=runtime_resources,
            cli_type=payload.cli_type or "claude-code",
            setup_script=payload.setup_script,
            env_vars=[env.model_dump() for env in payload.env_vars],
            port_mappings=[mapping.model_dump() for mapping in payload.port_mappings],
            workspace_firewall_network_access_enabled=(
                payload.firewall.workspace.network_access_enabled
                if payload.firewall
                else True
            ),
            workspace_firewall_domain_access_mode=(
                payload.firewall.workspace.domain_access_mode
                if payload.firewall
                else "all"
            ),
            workspace_firewall_allowed_domains=(
                payload.firewall.workspace.allowed_domains
                if payload.firewall
                else []
            ),
            browser_firewall_network_access_enabled=(
                payload.firewall.browser.network_access_enabled
                if payload.firewall
                else True
            ),
            browser_firewall_domain_access_mode=(
                payload.firewall.browser.domain_access_mode
                if payload.firewall
                else "all"
            ),
            browser_firewall_allowed_domains=(
                payload.firewall.browser.allowed_domains
                if payload.firewall
                else []
            ),
            preferred_cli=payload.preferred_cli or "claude-code",
            fallback_enabled=payload.fallback_enabled if payload.fallback_enabled is not None else True,
            workspace_path=payload.workspace_path or "/workspace",
            acp_cli_args=payload.acp_cli_args or [],
            runtime_status="starting",
            runtime_internal_port=default_internal_port,
            runtime_external_port=external_port,
            runtime_last_seen=None,
        )

        self.db.add(workspace)
        self.db.commit()
        self.db.refresh(workspace)

        return self._to_detail(workspace)

    def _resolve_workspace_provisioner(self) -> str:
        runtime_provisioner = self.settings.RUNTIME_PROVISIONER
        if runtime_provisioner == "kubernetes":
            return "kubernetes"
        return "docker"

    def update(self, workspace_id: str, payload: WorkspaceUpdateRequest) -> Optional[WorkspaceDetail]:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return None

        data = payload.model_dump(exclude_unset=True, by_alias=True)

        if "envVars" in data:
            workspace.env_vars = [WorkspaceEnvVar(**item).model_dump() for item in data.pop("envVars", [])]
        if "runtimeResources" in data:
            requested_runtime_resources = data.pop("runtimeResources")
            workspace.runtime_resources = self._resolve_runtime_resources_for_write(
                provisioner=data.get("provisioner", workspace.provisioner),
                runtime_resources=(
                    WorkspaceResourceRequirements(**requested_runtime_resources)
                    if requested_runtime_resources is not None
                    else None
                ),
            )
        if "portMappings" in data:
            next_provisioner = data.get("provisioner", workspace.provisioner)
            incoming_port_mappings = [
                WorkspacePortMapping(**item) for item in data["portMappings"] or []
            ]
            self._ensure_port_mappings_supported(
                provisioner=next_provisioner,
                port_mappings=incoming_port_mappings,
            )
            workspace.port_mappings = [
                mapping.model_dump() for mapping in incoming_port_mappings
            ]
            data.pop("portMappings", None)
        if "runtimeStatus" in data:
            status = RuntimeStatus(**data.pop("runtimeStatus"))
            workspace.runtime_status = status.status
            workspace.runtime_container_id = status.container_id
            workspace.runtime_internal_url = status.internal_url
            workspace.runtime_external_url = status.external_url
            workspace.runtime_internal_port = status.internal_port
            workspace.runtime_external_port = status.external_port
            workspace.runtime_last_seen = status.last_seen
        if "firewall" in data:
            self._ensure_firewall_available(
                provisioner=data.get("provisioner", workspace.provisioner)
            )
            firewall = FirewallConfig(**data.pop("firewall"))
            workspace.workspace_firewall_network_access_enabled = (
                firewall.workspace.network_access_enabled
            )
            workspace.workspace_firewall_domain_access_mode = (
                firewall.workspace.domain_access_mode
            )
            workspace.workspace_firewall_allowed_domains = (
                firewall.workspace.allowed_domains
            )
            workspace.browser_firewall_network_access_enabled = (
                firewall.browser.network_access_enabled
            )
            workspace.browser_firewall_domain_access_mode = (
                firewall.browser.domain_access_mode
            )
            workspace.browser_firewall_allowed_domains = (
                firewall.browser.allowed_domains
            )

        if "provisioner" in data or "targetNamespace" in data:
            next_provisioner = data.get("provisioner", workspace.provisioner)
            next_target_namespace = data.get("targetNamespace", workspace.target_namespace)
            workspace.target_namespace = self._resolve_target_namespace(
                provisioner=next_provisioner,
                target_namespace=next_target_namespace,
            )
            if next_provisioner != "kubernetes":
                workspace.runtime_resources = None

        for attr, value in data.items():
            if attr == "targetNamespace":
                continue
            setattr(workspace, snake_case(attr), value)

        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(workspace)
        return self._to_detail(workspace)

    # -- 轉換函式 ---------------------------------------------------------

    def _to_owner(self, user: db_models.User) -> WorkspaceOwner:
        return WorkspaceOwner(
            id=user.id,
            display_name=user.display_name or user.username,
            avatar_url=user.avatar_url,
            username=user.username,
            email=user.email,
        )

    def _to_summary(self, workspace: db_models.Workspace) -> WorkspaceSummary:
        owner = self._to_owner(workspace.owner)
        return WorkspaceSummary(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            owner=owner,
            git_url=workspace.git_url,
            branch=workspace.branch,
            runtime=workspace.runtime,
            provisioner=workspace.provisioner,
            target_namespace=workspace.target_namespace,
            overall_phase=workspace.runtime_status,
            cli_type=workspace.cli_type,
            runtime_status=workspace.runtime_status,
            runtime_external_url=workspace.runtime_external_url,
            runtime_last_seen=workspace.runtime_last_seen,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    def _to_detail(self, workspace: db_models.Workspace) -> WorkspaceDetail:
        owner = self._to_owner(workspace.owner)
        runtime_status = RuntimeStatus(
            status=workspace.runtime_status,
            container_id=workspace.runtime_container_id,
            internal_url=workspace.runtime_internal_url,
            external_url=workspace.runtime_external_url,
            internal_port=workspace.runtime_internal_port,
            external_port=workspace.runtime_external_port,
            last_seen=workspace.runtime_last_seen,
            web_preview_internal_port=workspace.web_preview_internal_port,
            web_preview_external_port=workspace.web_preview_external_port,
            web_preview_internal_url=workspace.web_preview_internal_url,
            web_preview_external_url=workspace.web_preview_external_url,
            terminal_external_port=workspace.terminal_external_port,
            terminal_external_url=workspace.terminal_external_url,
            # Browser 相關欄位
            browser_container_id=workspace.browser_container_id,
            browser_status=workspace.browser_status,
            browser_created_at=workspace.browser_created_at,
            browser_last_seen=workspace.browser_last_seen,
            # Browser WebRTC (neko) 欄位
            browser_webrtc_internal_url=workspace.browser_webrtc_internal_url,
            browser_webrtc_external_url=workspace.browser_webrtc_external_url,
            browser_webrtc_internal_port=workspace.browser_webrtc_internal_port,
            browser_webrtc_external_port=workspace.browser_webrtc_external_port,
            # Browser CDP 欄位
            browser_cdp_internal_port=workspace.browser_cdp_internal_port,
            browser_cdp_external_port=workspace.browser_cdp_external_port,
            # Next.js 容器欄位
            nextjs_container_id=workspace.nextjs_container_id,
            nextjs_status=workspace.nextjs_status,
            nextjs_created_at=workspace.nextjs_created_at,
            nextjs_last_seen=workspace.nextjs_last_seen,
            nextjs_internal_url=workspace.nextjs_internal_url,
            nextjs_external_url=workspace.nextjs_external_url,
            nextjs_internal_port=workspace.nextjs_internal_port,
            nextjs_external_port=workspace.nextjs_external_port,
            nextjs_api_internal_port=workspace.nextjs_api_internal_port,
            nextjs_api_external_port=workspace.nextjs_api_external_port,
        )
        # Keep both firewall groups in the API response because the manager stores a
        # symmetric configuration surface across provisioners. Verified enforcement
        # still differs by provisioner: Docker currently enforces the workspace
        # runtime scope through workspace-runtime, while Kubernetes delegates both
        # groups through the custom resource / policy-controller path.
        firewall = FirewallConfig(
            workspace={
                "networkAccessEnabled": workspace.workspace_firewall_network_access_enabled,
                "domainAccessMode": workspace.workspace_firewall_domain_access_mode,
                "allowedDomains": workspace.workspace_firewall_allowed_domains or [],
                "effectiveAllowedDomains": self._effective_allowed_domains(
                    self.settings.FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS,
                    workspace.workspace_firewall_allowed_domains or [],
                    enabled=self._is_firewall_available_for_provisioner(workspace.provisioner),
                ),
            },
            browser={
                "networkAccessEnabled": workspace.browser_firewall_network_access_enabled,
                "domainAccessMode": workspace.browser_firewall_domain_access_mode,
                "allowedDomains": workspace.browser_firewall_allowed_domains or [],
                "effectiveAllowedDomains": self._effective_allowed_domains(
                    self.settings.FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS,
                    workspace.browser_firewall_allowed_domains or [],
                    enabled=self._is_firewall_available_for_provisioner(workspace.provisioner),
                ),
            },
        )

        env_vars = [WorkspaceEnvVar(**item) for item in workspace.env_vars or []]
        system_port_mappings = self._build_system_port_mappings(workspace)
        port_mappings = [WorkspacePortMapping(**item) for item in workspace.port_mappings or []]
        components = self._to_components(workspace)

        runtime_job = None
        if workspace.runtime_jobs:
            runtime_job = self._to_runtime_job(workspace.runtime_jobs[0])

        return WorkspaceDetail(
            id=workspace.id,
            owner=owner,
            name=workspace.name,
            description=workspace.description,
            template_id=None,
            git_url=workspace.git_url,
            branch=workspace.branch,
            runtime=workspace.runtime,
            provisioner=workspace.provisioner,
            target_namespace=workspace.target_namespace,
            overall_phase=workspace.runtime_status,
            cli_type=workspace.cli_type,
            setup_script=workspace.setup_script,
            env_vars=env_vars,
            runtime_resources=self._effective_runtime_resources(workspace),
            system_port_mappings=system_port_mappings,
            port_mappings=port_mappings,
            runtime_status=runtime_status,
            components=components,
            firewall_available=self._is_firewall_available_for_provisioner(workspace.provisioner),
            firewall_unavailable_reason=self._firewall_unavailable_reason_for_provisioner(
                workspace.provisioner
            ),
            firewall=firewall,
            preferred_cli=workspace.preferred_cli,
            fallback_enabled=workspace.fallback_enabled,
            workspace_path=workspace.workspace_path,
            acp_cli_args=workspace.acp_cli_args or [],
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            runtime_job=runtime_job,
        )

    def _is_firewall_available_for_provisioner(self, provisioner: Optional[str]) -> bool:
        if provisioner == "kubernetes":
            return self.settings.CILIUM_ENABLED
        return True

    def _firewall_unavailable_reason_for_provisioner(
        self, provisioner: Optional[str]
    ) -> Optional[str]:
        if self._is_firewall_available_for_provisioner(provisioner):
            return None
        return "CILIUM_NOT_ENABLED"

    def _resolve_target_namespace(
        self,
        *,
        provisioner: str,
        target_namespace: Optional[str],
    ) -> Optional[str]:
        if provisioner != "kubernetes":
            return None

        namespace = target_namespace or self.settings.RUNTIME_K8S_NAMESPACE
        if namespace not in self.settings.RUNTIME_K8S_ALLOWED_NAMESPACES:
            raise ValueError(f"Invalid Kubernetes namespace: {namespace}")
        return namespace

    def _resolve_runtime_resources_for_write(
        self,
        *,
        provisioner: str,
        runtime_resources: Optional[WorkspaceResourceRequirements],
    ) -> Optional[dict]:
        if runtime_resources is None:
            return None
        if provisioner != "kubernetes":
            raise ValueError("runtimeResources is only supported for Kubernetes workspaces")
        return runtime_resources.model_dump(by_alias=True)

    def _ensure_port_mappings_supported(
        self,
        *,
        provisioner: str,
        port_mappings: list[WorkspacePortMapping],
    ) -> None:
        if provisioner == "kubernetes" and port_mappings:
            raise ValueError("portMappings is only supported for Docker workspaces")

    def _build_system_port_mappings(
        self,
        workspace: db_models.Workspace,
    ) -> list[WorkspaceSystemPortMapping]:
        if workspace.provisioner != "docker":
            return []

        rows = [
            (
                "runtime",
                workspace.runtime_internal_port,
                workspace.runtime_external_port,
                "tcp",
                "Workspace runtime API",
            ),
            (
                "terminal",
                3004,
                workspace.terminal_external_port,
                "tcp",
                "Workspace terminal websocket",
            ),
            (
                "browser-webrtc",
                workspace.browser_webrtc_internal_port,
                workspace.browser_webrtc_external_port,
                "tcp",
                "Browser WebRTC signaling",
            ),
            (
                "browser-cdp",
                workspace.browser_cdp_internal_port,
                workspace.browser_cdp_external_port,
                "tcp",
                "Browser CDP proxy",
            ),
            (
                "nextjs",
                workspace.nextjs_internal_port,
                workspace.nextjs_external_port,
                "tcp",
                "Next.js preview",
            ),
            (
                "nextjs-api",
                workspace.nextjs_api_internal_port,
                workspace.nextjs_api_external_port,
                "tcp",
                "Next.js management API",
            ),
        ]

        return [
            WorkspaceSystemPortMapping(
                name=name,
                container_port=container_port,
                host_port=host_port,
                protocol=protocol,
                description=description,
                editable=False,
            )
            for name, container_port, host_port, protocol, description in rows
            if container_port
        ]

    def _effective_runtime_resources(
        self,
        workspace: db_models.Workspace,
    ) -> Optional[WorkspaceResourceRequirements]:
        if workspace.provisioner != "kubernetes":
            return None

        resources = (
            workspace.runtime_resources
            or self.settings.RUNTIME_K8S_RUNTIME_RESOURCES
        )
        return WorkspaceResourceRequirements.model_validate(resources)

    def _sync_kubernetes_workspace_records(
        self,
        workspaces: list[db_models.Workspace],
    ) -> None:
        kubernetes_workspaces = [
            workspace for workspace in workspaces if workspace.provisioner == "kubernetes"
        ]
        if not kubernetes_workspaces:
            return

        sync_service = WorkspaceCustomResourceService(self.db)
        for workspace in kubernetes_workspaces:
            sync_service.sync_workspace_record_status(workspace)

    def _sync_kubernetes_workspace_record(self, workspace: db_models.Workspace) -> None:
        if workspace.provisioner != "kubernetes":
            return
        WorkspaceCustomResourceService(self.db).sync_workspace_record_status(workspace)

    def _to_runtime_job(self, job: db_models.WorkspaceRuntimeJob) -> WorkspaceRuntimeJobSummary:
        return WorkspaceRuntimeJobSummary(
            id=job.id,
            operation=job.operation,
            strategy=job.strategy,
            status=job.status,
            retries=job.retries,
            scheduled_at=job.scheduled_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error_message=job.error_message,
        )

    def _ensure_firewall_available(self, *, provisioner: Optional[str]) -> None:
        if not self._is_firewall_available_for_provisioner(provisioner):
            raise ValueError(
                self._firewall_unavailable_reason_for_provisioner(provisioner)
            )

    def _to_components(self, workspace: db_models.Workspace) -> WorkspaceComponents:
        restart_metadata = self._collect_restart_metadata(workspace)
        return WorkspaceComponents(
            runtime=WorkspaceComponentStatus(
                phase=workspace.runtime_status,
                internal_url=workspace.runtime_internal_url,
                external_url=workspace.runtime_external_url,
                last_seen=workspace.runtime_last_seen,
                last_restart_requested_at=restart_metadata["runtime"],
            ),
            browser=WorkspaceComponentStatus(
                phase=workspace.browser_status,
                internal_url=workspace.browser_webrtc_internal_url,
                external_url=workspace.browser_webrtc_external_url,
                last_seen=workspace.browser_last_seen,
                last_restart_requested_at=restart_metadata["browser"],
            ),
            nextjs=WorkspaceComponentStatus(
                phase=workspace.nextjs_status,
                internal_url=workspace.nextjs_internal_url,
                external_url=workspace.nextjs_external_url,
                last_seen=workspace.nextjs_last_seen,
                last_restart_requested_at=restart_metadata["nextjs"],
            ),
        )

    def _collect_restart_metadata(
        self,
        workspace: db_models.Workspace,
    ) -> dict[str, Optional[datetime]]:
        restart_metadata: dict[str, Optional[datetime]] = {
            "runtime": None,
            "browser": None,
            "nextjs": None,
        }

        for job in workspace.runtime_jobs or []:
            if job.operation == "restart_workspace_custom_resource":
                restart_metadata["runtime"] = restart_metadata["runtime"] or job.scheduled_at
                restart_metadata["browser"] = restart_metadata["browser"] or job.scheduled_at
                restart_metadata["nextjs"] = restart_metadata["nextjs"] or job.scheduled_at
            elif job.operation == "restart_runtime_custom_resource":
                restart_metadata["runtime"] = restart_metadata["runtime"] or job.scheduled_at
            elif job.operation == "restart_browser_custom_resource":
                restart_metadata["browser"] = restart_metadata["browser"] or job.scheduled_at
            elif job.operation == "restart_nextjs_custom_resource":
                restart_metadata["nextjs"] = restart_metadata["nextjs"] or job.scheduled_at

        for log in workspace.runtime_logs or []:
            if log.stage == "restarting" and restart_metadata["runtime"] is None:
                restart_metadata["runtime"] = log.created_at
            elif log.stage == "browser_restarting" and restart_metadata["browser"] is None:
                restart_metadata["browser"] = log.created_at
            elif log.stage == "nextjs_restarting" and restart_metadata["nextjs"] is None:
                restart_metadata["nextjs"] = log.created_at

        return restart_metadata

    def _effective_allowed_domains(
        self,
        defaults: list[str],
        workspace_domains: list[str],
        *,
        enabled: bool = True,
    ) -> list[str]:
        if not enabled:
            return []
        merged: list[str] = []
        seen: set[str] = set()

        for domain in [*defaults, *workspace_domains]:
            normalized = domain.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)

        return merged

    # -- 生命週期管理 ------------------------------------------------------

    def mark_workspace_deleting(self, workspace_id: str) -> bool:
        """標記 workspace 為刪除中狀態

        Args:
            workspace_id: Workspace ID

        Returns:
            bool: 是否成功標記
        """
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return False

        workspace.runtime_status = "deleting"
        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_workspace_rebuilding(self, workspace_id: str) -> bool:
        """標記 workspace 為重啟中狀態

        Args:
            workspace_id: Workspace ID

        Returns:
            bool: 是否成功標記
        """
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return False

        workspace.runtime_status = "restarting"
        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_browser_restarting(self, workspace_id: str) -> bool:
        """標記 Browser 容器為重啟中狀態

        Args:
            workspace_id: Workspace ID

        Returns:
            bool: 是否成功標記
        """
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return False

        workspace.browser_status = "restarting"
        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_nextjs_restarting(self, workspace_id: str) -> bool:
        """標記 Next.js 容器為重啟中狀態"""
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return False

        workspace.nextjs_status = "restarting"
        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True


__all__ = ["WorkspaceService"]
