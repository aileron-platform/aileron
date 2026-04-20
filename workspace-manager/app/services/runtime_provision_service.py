"""Workspace Runtime 佈建服務與策略實作"""

from __future__ import annotations

import logging
import random
import socket
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.services.script_template_engine import ScriptTemplateEngine
from app.services.orchestrator import (
    OrchestratorFactory,
    RuntimeContext,
    RuntimeInfo,
    VolumeMount,
    PortMapping,
    NetworkConfig,
    ResourceRequirements
)
from app.utils.path_resolver import PathResolver

logger = logging.getLogger(__name__)

# Port 分配範圍
PORT_RANGE_MIN = 30000
PORT_RANGE_MAX = 60000

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "jinja_templates" / "runtime"

class RuntimeProvisionService:
    """負責調度 Workspace Runtime 佈建的服務。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.template_engine = ScriptTemplateEngine(TEMPLATE_ROOT)
        # 動態獲取 settings，確保在測試環境中使用正確的配置
        self.settings = get_settings()
        self.script_output_root = Path(self.settings.RUNTIME_SCRIPT_ROOT)

    # -- 背景任務主流程 --------------------------------------------------
    def execute_runtime_provision(self, workspace_id: str) -> None:
        workspace = self._get_workspace(workspace_id)
        if not workspace:
            logger.error("Workspace %s 不存在，無法佈建", workspace_id)
            return

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation="provision",
            strategy=self.settings.RUNTIME_PROVISIONER,
            status="queued",
            retries=0,
            scheduled_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()

        self._log_event(workspace.id, "queued", "已排入 runtime 佈建", {"jobId": job.id})
        workspace.runtime_status = "starting"
        self.db.commit()

        try:
            self._perform_job(workspace, job)
        except Exception as exc:  # pragma: no cover - 實際錯誤需紀錄
            logger.exception("佈建 Workspace %s 失敗", workspace.id)
            self.db.rollback()
            workspace = self._get_workspace(workspace_id)
            job = self._get_runtime_job(job.id)
            if not workspace or not job:
                logger.error("回滾後找不到 Workspace 或 Job，無法更新失敗狀態")
                return
            self._handle_failure(workspace, job, exc)
        finally:
            self.db.commit()

    def _perform_job(self, workspace: db_models.Workspace, job: db_models.WorkspaceRuntimeJob) -> None:
        job.status = "provisioning"
        job.started_at = datetime.utcnow()
        self._log_event(workspace.id, "provisioning", "開始建立 Workspace Runtime")
        self.db.commit()

        # 1. 準備 Runtime Context
        context = self._build_runtime_context(workspace)

        self._log_event(
            workspace.id,
            "preparing",
            "已產生佈建腳本與環境設定",
            {
                "environment": {k: v for k, v in context.environment.items() if "KEY" not in k}, # Hide sensitive keys
                "ports": [p.__dict__ for p in context.ports],
            },
        )
        self.db.commit()

        # 2. 獲取 Orchestrator
        orchestrator = OrchestratorFactory.get_orchestrator()

        # 3. 執行佈建
        result = orchestrator.create_workspace_runtime(workspace, context)

        self._log_event(
            workspace.id,
            "provisioned",
            "策略執行完成，更新 runtime 狀態",
            {"identifier": result.identifier},
        )

        # 4. 更新 Workspace 狀態
        self._update_workspace_runtime(workspace, result)

        # 5. 啟動 Browser 容器
        try:
            self._log_event(workspace.id, "browser_starting", "開始建立 Browser 容器")
            browser_context = self._build_browser_runtime_context(workspace)
            browser_result = orchestrator.create_chrome_runtime(workspace, browser_context)
            self._update_browser_runtime(workspace, browser_result)
            self._log_event(
                workspace.id,
                "browser_ready",
                "Browser 容器已就緒",
                {"browser_identifier": browser_result.identifier, "browser_webrtc_port": workspace.browser_webrtc_external_port},
            )
        except Exception as exc:
            # Browser 容器啟動失敗不應影響主 runtime
            logger.error(f"Workspace {workspace.id}: Browser 容器啟動失敗: {exc}", exc_info=True)
            workspace.browser_status = "error"
            self._log_event(
                workspace.id,
                "browser_error",
                f"Browser 容器啟動失敗: {exc}",
            )

        # 6. 啟動 Next.js 容器
        try:
            self._log_event(workspace.id, "nextjs_starting", "開始建立 Next.js 容器")
            nextjs_context = self._build_nextjs_runtime_context(workspace)
            nextjs_result = orchestrator.create_nextjs_runtime(workspace, nextjs_context)
            self._update_nextjs_runtime(workspace, nextjs_result)
            self._log_event(
                workspace.id,
                "nextjs_ready",
                "Next.js 容器已就緒",
                {"nextjs_identifier": nextjs_result.identifier, "nextjs_port": workspace.nextjs_external_port},
            )
        except Exception as exc:
            # Next.js 容器啟動失敗不應影響主 runtime
            logger.error(f"Workspace {workspace.id}: Next.js 容器啟動失敗: {exc}", exc_info=True)
            workspace.nextjs_status = "error"
            self._log_event(
                workspace.id,
                "nextjs_error",
                f"Next.js 容器啟動失敗: {exc}",
            )

        job.status = "completed"
        job.finished_at = datetime.utcnow()
        self._log_event(workspace.id, "completed", "Workspace Runtime 已就緒")

    def _build_runtime_context(self, workspace: db_models.Workspace) -> RuntimeContext:
        """構建 RuntimeContext"""

        # 0. 分配固定的 port（解決 docker restart 後 port 變更的問題）
        self._allocate_ports_if_needed(workspace)

        # 1. 準備腳本 (Startup Script)
        workspace_dir = self.script_output_root / workspace.id
        environment = self._build_environment(workspace)

        # 端口配置（現在使用固定分配的 port）
        ports_config = self._build_ports_config(workspace)
        
        # 渲染 startup.sh
        self.template_engine.render_to_file(
            "docker/startup.sh.j2",
            workspace_dir / "startup.sh",
            {
                "workspace": {"id": workspace.id, "name": workspace.name},
                "environment": environment,
                "ports": ports_config, # 傳遞給模板的端口配置
                "git": {"url": workspace.git_url, "branch": workspace.branch},
            },
            executable=True,
        )

        # 2. 構建 Volume Mounts
        volumes = self._build_volumes(workspace)
        
        # 3. 構建 Port Mappings
        port_mappings = []
        for p in ports_config["mappings"]:
            port_mappings.append(PortMapping(
                container_port=p["container_port"],
                host_port=p["host_port"],
                protocol=p["protocol"]
            ))
            
        # 添加預設端口
        port_mappings.append(PortMapping(
            container_port=ports_config["default_internal_port"],
            host_port=workspace.runtime_external_port # 如果已有，則使用
        ))
        # 注意: web_preview (3003) 已移至獨立的 workspace-nextjs 容器
        port_mappings.append(PortMapping(
            container_port=ports_config["terminal_internal_port"],
            host_port=workspace.terminal_external_port
        ))

        # 4. 構建 Network Config
        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK,
            network_mode="bridge"
        )
        
        # 5. 獲取 Image
        from app.services.container_image_service import get_container_image_service
        image_service = get_container_image_service()
        docker_image = image_service.get_docker_image_name(workspace.runtime)
        
        return RuntimeContext(
            environment=environment,
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": docker_image,
                "command": "/start_services.sh",
                "working_dir": "/workspace-runtime"
            }
        )

    def _build_environment(self, workspace: db_models.Workspace) -> dict[str, str]:
        # Browser container 連接資訊（用於服務發現）
        browser_container_name = f"workspace-browser-{workspace.id}"

        env = {
            "WORKSPACE_ID": workspace.id,
            "WORKSPACE_NAME": workspace.name,
            "WORKSPACE_RUNTIME_PORT": str(workspace.runtime_internal_port or 3002),
            "NODE_ENV": self.settings.ENV,
            "ENV": self.settings.ENV,
            "ALLOWED_ORIGINS": '["*"]',
            "DATABASE_URL": self.settings.DATABASE_URL,
            "REDIS_URL": self.settings.REDIS_URL,
            "MANAGER_URL": f"http://workspace-manager:{self.settings.PORT}",
            "INTERNAL_API_TOKEN": self.settings.INTERNAL_API_TOKEN,
            # Browser container 連接資訊
            "BROWSER_CONTAINER_NAME": browser_container_name,
            "BROWSER_WEBRTC_INTERNAL_URL": workspace.browser_webrtc_internal_url or f"http://{browser_container_name}:6080",
            "BROWSER_CDP_URL": f"http://{browser_container_name}:9223",
            # Keycloak JWT 認證（workspace-runtime 需要驗證前端傳來的 access token）
            "KEYCLOAK_SERVER_URL": self.settings.KEYCLOAK_SERVER_URL,
            "KEYCLOAK_REALM": self.settings.KEYCLOAK_REALM,
            "KEYCLOAK_CLIENT_ID": self.settings.KEYCLOAK_CLIENT_ID,
            # Next.js container 連接資訊（用於服務發現）
            "NEXTJS_CONTAINER_NAME": f"workspace-nextjs-{workspace.id}",
            "NEXTJS_INTERNAL_URL": workspace.nextjs_internal_url or f"http://workspace-nextjs-{workspace.id}:3003",
            "NEXTJS_API_URL": f"http://workspace-nextjs-{workspace.id}:3013",
        }

        if workspace.git_url:
            env["GIT_REPO_URL"] = workspace.git_url
            env["GIT_BRANCH"] = workspace.branch or "main"

        try:
            # 獲取工作區擁有者的用戶設置
            user_settings = self.db.scalar(
                select(db_models.UserSetting).where(
                    db_models.UserSetting.user_id == workspace.owner_id
                )
            )

            if user_settings:
                if user_settings.ssh_private_key:
                    env["SSH_PRIVATE_KEY"] = user_settings.ssh_private_key
                if user_settings.ssh_public_key:
                    env["SSH_PUBLIC_KEY"] = user_settings.ssh_public_key
                if user_settings.git_user_name:
                    env["GIT_USER_NAME"] = user_settings.git_user_name
                if user_settings.git_user_email:
                    env["GIT_USER_EMAIL"] = user_settings.git_user_email
        except Exception as e:
            logger.warning(f"無法獲取用戶設置: {e}")

        for item in workspace.env_vars or []:
            key = item.get("key")
            value = item.get("value")
            if key and value:
                env[key] = str(value)
        return env

    def _build_ports_config(self, workspace: db_models.Workspace) -> dict[str, Any]:
        """構建端口配置字典 (用於模板渲染)"""
        default_port = workspace.runtime_internal_port or 3002
        web_preview_port = workspace.web_preview_internal_port or 3003
        terminal_port = 3004

        mappings = []
        for mapping in workspace.port_mappings or []:
            container_port = int(mapping.get("container_port", default_port))
            if container_port in [default_port, web_preview_port, terminal_port]:
                continue
            mappings.append({
                "container_port": container_port,
                "host_port": mapping.get("host_port"),
                "protocol": mapping.get("protocol", "tcp")
            })

        return {
            "default_internal_port": default_port,
            "web_preview_internal_port": web_preview_port,
            "terminal_internal_port": terminal_port,
            "mappings": mappings,
        }

    def _build_volumes(self, workspace: db_models.Workspace) -> list[VolumeMount]:
        safe_workspace_id = workspace.id.replace('-', '_')

        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id
        host_scripts = Path(self.settings.HOST_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id
        host_claude = Path(self.settings.HOST_CLAUDE_DATA_DIR) / safe_workspace_id
        manager_workspace = Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id
        manager_scripts = Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id
        manager_claude = Path(self.settings.MANAGER_CLAUDE_DATA_DIR) / safe_workspace_id

        manager_workspace.mkdir(parents=True, exist_ok=True)
        manager_scripts.mkdir(parents=True, exist_ok=True)
        manager_claude.mkdir(parents=True, exist_ok=True)

        if workspace.setup_script:
            custom_setup_file = manager_scripts / "custom-setup.sh"
            custom_setup_file.write_text(workspace.setup_script, encoding="utf-8")
            custom_setup_file.chmod(0o755)

        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
            VolumeMount(source=str(host_scripts), target="/scripts"),
            # 持久化 ~/.claude（Claude Code session files、設定等），避免容器重啟後 --resume 失效
            VolumeMount(source=str(host_claude), target="/home/developer/.claude"),
            # Docker socket
            VolumeMount(source="/var/run/docker.sock", target="/var/run/docker.sock"),
        ]
        
        # Development mode volumes
        node_env = os.environ.get("NODE_ENV", "production")
        if node_env.lower() in ["development", "dev"]:
            host_workspace_runtime_dir = os.environ.get("HOST_WORKSPACE_RUNTIME_DIR")
            if host_workspace_runtime_dir:
                volumes.append(VolumeMount(source=f"{host_workspace_runtime_dir}/app", target="/workspace-runtime/app"))
                volumes.append(VolumeMount(source=f"{host_workspace_runtime_dir}/scripts", target="/workspace-runtime/scripts"))
                volumes.append(VolumeMount(source=f"{host_workspace_runtime_dir}/tests", target="/workspace-runtime/tests"))
                volumes.append(VolumeMount(source=f"{host_workspace_runtime_dir}/pyproject.toml", target="/workspace-runtime/pyproject.toml"))
                volumes.append(VolumeMount(source=f"{host_workspace_runtime_dir}/uv.lock", target="/workspace-runtime/uv.lock"))
                
                host_project_root = os.environ.get("HOST_PROJECT_ROOT")
                if host_project_root:
                    volumes.append(VolumeMount(source=f"{host_project_root}/workspace-terminal", target="/workspace-terminal"))

        return volumes

    def _allocate_ports_if_needed(self, workspace: db_models.Workspace) -> None:
        """為 workspace 分配固定的 port（如果尚未分配）"""
        allocated = []

        # Runtime port
        if not workspace.runtime_external_port:
            workspace.runtime_external_port = self._find_available_port()
            allocated.append(workspace.runtime_external_port)

        # Web preview port
        if not workspace.web_preview_external_port:
            workspace.web_preview_external_port = self._find_available_port(
                exclude={workspace.runtime_external_port}
            )
            allocated.append(workspace.web_preview_external_port)

        # Terminal port
        if not workspace.terminal_external_port:
            workspace.terminal_external_port = self._find_available_port(
                exclude={workspace.runtime_external_port, workspace.web_preview_external_port}
            )
            allocated.append(workspace.terminal_external_port)

        # Browser WebRTC (neko) port
        if not workspace.browser_webrtc_external_port:
            workspace.browser_webrtc_external_port = self._find_available_port(
                exclude={workspace.runtime_external_port, workspace.web_preview_external_port,
                         workspace.terminal_external_port}
            )
            allocated.append(workspace.browser_webrtc_external_port)

        # Browser CDP port
        if not workspace.browser_cdp_external_port:
            workspace.browser_cdp_external_port = self._find_available_port(
                exclude={workspace.runtime_external_port, workspace.web_preview_external_port,
                         workspace.terminal_external_port, workspace.browser_webrtc_external_port}
            )
            allocated.append(workspace.browser_cdp_external_port)

        # 收集已分配的 port 以避免衝突
        all_allocated = {workspace.runtime_external_port, workspace.web_preview_external_port,
                         workspace.terminal_external_port, workspace.browser_webrtc_external_port,
                         workspace.browser_cdp_external_port}

        # Next.js container port (dev server)
        if not workspace.nextjs_external_port:
            workspace.nextjs_external_port = self._find_available_port(exclude=all_allocated)
            allocated.append(workspace.nextjs_external_port)
            all_allocated.add(workspace.nextjs_external_port)

        # Next.js management API port
        if not workspace.nextjs_api_external_port:
            workspace.nextjs_api_external_port = self._find_available_port(exclude=all_allocated)
            allocated.append(workspace.nextjs_api_external_port)

        # 更新 URL
        workspace.runtime_external_url = f"http://localhost:{workspace.runtime_external_port}"
        workspace.web_preview_external_url = f"http://localhost:{workspace.web_preview_external_port}"
        workspace.terminal_external_url = f"http://localhost:{workspace.terminal_external_port}"
        workspace.browser_webrtc_external_url = f"http://localhost:{workspace.browser_webrtc_external_port}"
        workspace.nextjs_external_url = f"http://localhost:{workspace.nextjs_external_port}"

        if allocated:
            logger.info(f"Workspace {workspace.id}: 分配固定 ports: runtime={workspace.runtime_external_port}, "
                       f"web_preview={workspace.web_preview_external_port}, terminal={workspace.terminal_external_port}, "
                       f"browser_webrtc={workspace.browser_webrtc_external_port}, browser_cdp={workspace.browser_cdp_external_port}, "
                       f"nextjs={workspace.nextjs_external_port}, nextjs_api={workspace.nextjs_api_external_port}")
            self.db.flush()

    def _find_available_port(self, exclude: set[int] = None, protocol: str = "tcp") -> int:
        """隨機找一個可用的 port"""
        exclude = exclude or set()
        socket_type = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM

        for _ in range(100):
            port = random.randint(PORT_RANGE_MIN, PORT_RANGE_MAX)
            if port in exclude:
                continue
            try:
                with socket.socket(socket.AF_INET, socket_type) as s:
                    s.bind(("0.0.0.0", port))
                    return port
            except OSError:
                continue

        raise RuntimeError(f"無法在 {PORT_RANGE_MIN}-{PORT_RANGE_MAX} 範圍內找到可用的 port")

    def _handle_failure(
        self,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        exc: Exception,
    ) -> None:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.utcnow()
        workspace.runtime_status = "error"
        workspace.runtime_last_seen = datetime.utcnow()
        self._log_event(
            workspace.id,
            "failed",
            "佈建失敗，請檢視錯誤並重新嘗試",
            {"error": str(exc)},
        )

    # -- 查詢介面 --------------------------------------------------------
    def get_runtime_logs(
        self,
        workspace_id: str,
        *,
        limit: int = 100,
        stage: Optional[str] = None,
    ) -> list[db_models.WorkspaceRuntimeLog]:
        stmt: Select[tuple[db_models.WorkspaceRuntimeLog]] = select(db_models.WorkspaceRuntimeLog).where(
            db_models.WorkspaceRuntimeLog.workspace_id == workspace_id
        )
        if stage:
            stmt = stmt.where(db_models.WorkspaceRuntimeLog.stage == stage)
        stmt = stmt.order_by(db_models.WorkspaceRuntimeLog.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_job(self, workspace_id: str) -> Optional[db_models.WorkspaceRuntimeJob]:
        stmt = (
            select(db_models.WorkspaceRuntimeJob)
            .where(db_models.WorkspaceRuntimeJob.workspace_id == workspace_id)
            .order_by(db_models.WorkspaceRuntimeJob.scheduled_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    # -- 私有輔助方法 ----------------------------------------------------
    def _get_workspace(self, workspace_id: str) -> Optional[db_models.Workspace]:
        return self.db.get(db_models.Workspace, workspace_id)

    def _get_runtime_job(self, job_id: str) -> Optional[db_models.WorkspaceRuntimeJob]:
        return self.db.get(db_models.WorkspaceRuntimeJob, job_id)

    def _log_event(self, workspace_id: str, stage: str, message: str, metadata: Optional[dict[str, Any]] = None) -> None:
        log_entry = db_models.WorkspaceRuntimeLog(
            id=str(uuid4()),
            workspace_id=workspace_id,
            stage=stage,
            message=message,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        self.db.add(log_entry)
        logger.info("[workspace:%s][%s] %s", workspace_id, stage, message)

    def _update_workspace_runtime(self, workspace: db_models.Workspace, runtime_info: RuntimeInfo) -> None:
        workspace.runtime_id = runtime_info.identifier
        workspace.runtime_internal_url = runtime_info.internal_url

        # 保持已分配的固定 port，不要用 container 實際的 port 覆蓋
        # 這樣可以避免 container 重啟後 port 變更的問題
        if not workspace.runtime_external_url:
            workspace.runtime_external_url = runtime_info.external_url

        # 從 extra_info 中提取端口信息（僅用於驗證，不覆蓋已分配的 port）
        ports_mapping = runtime_info.extra_info.get("ports", {})

        # 只在尚未分配 port 時才從 container.ports 中獲取
        # （這樣可以保持 port 的一致性）
        default_port = workspace.runtime_internal_port or 3002
        default_key = f"{default_port}/tcp"

        # 驗證 container 是否使用了正確的 port
        if default_key in ports_mapping:
            actual_port = ports_mapping[default_key]
            if workspace.runtime_external_port != actual_port:
                logger.warning(
                    f"Workspace {workspace.id}: Container 實際 port ({actual_port}) "
                    f"與分配的固定 port ({workspace.runtime_external_port}) 不符。"
                    f"使用固定 port 以保持一致性。"
                )

        # Web Preview - 只在尚未分配時更新
        web_preview_port = workspace.web_preview_internal_port or 3003
        web_key = f"{web_preview_port}/tcp"
        if web_key in ports_mapping:
            if not workspace.web_preview_external_url:
                workspace.web_preview_external_url = f"http://localhost:{workspace.web_preview_external_port}"
            workspace.web_preview_internal_url = f"http://{runtime_info.extra_info.get('container_name')}:{web_preview_port}"

        # Terminal - 只在尚未分配時更新
        terminal_port = 3004
        term_key = f"{terminal_port}/tcp"
        if term_key in ports_mapping and not workspace.terminal_external_url:
            workspace.terminal_external_url = f"http://localhost:{workspace.terminal_external_port}"

        workspace.runtime_status = "running"
        workspace.runtime_last_seen = datetime.utcnow()

    def _build_browser_runtime_context(self, workspace: db_models.Workspace) -> RuntimeContext:
        """構建 Browser Runtime Context"""
        from app.services.container_image_service import get_container_image_service
        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace('-', '_')
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # 確保 workspace 目錄存在
        host_workspace.mkdir(parents=True, exist_ok=True)

        # Browser 容器名稱（用於服務發現）
        browser_container_name = f"workspace-browser-{workspace.id}"

        # 為 WebRTC media 分配唯一的 UDP port
        udp_port = self._find_available_port(
            exclude={workspace.runtime_external_port, workspace.web_preview_external_port,
                     workspace.terminal_external_port, workspace.browser_webrtc_external_port,
                     workspace.browser_cdp_external_port},
            protocol="udp",
        )

        # Port mappings for Browser (neko WebRTC + CDP + UDP media)
        port_mappings = [
            PortMapping(container_port=6080, host_port=workspace.browser_webrtc_external_port, protocol="tcp"),  # neko WebRTC (HTTP + WS signaling)
            PortMapping(container_port=9223, host_port=workspace.browser_cdp_external_port, protocol="tcp"),  # CDP proxy
            PortMapping(container_port=udp_port, host_port=udp_port, protocol="udp"),  # WebRTC media (UDPMUX)
        ]

        # Browser 容器掛載相同的 WORKSPACE 目錄
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK,
            network_mode="bridge"
        )

        return RuntimeContext(
            environment={
                "WORKSPACE_ID": workspace.id,
                "CONTAINER_NAME": browser_container_name,
                # neko 設定
                "NEKO_SERVER_BIND": ":6080",
                "NEKO_DESKTOP_SCREEN": "1440x900@30",
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD": "neko",
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD": "admin",
                "NEKO_WEBRTC_ICELITE": "1",
                "NEKO_WEBRTC_UDPMUX": str(udp_port),
                "NEKO_WEBRTC_NAT1TO1": "127.0.0.1",
                "NEKO_SESSION_IMPLICIT_HOSTING": "true",
            },
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": image_service.get_browser_image_name(),
                "command": None,
                "working_dir": "/workspace"
            }
        )

    def _update_browser_runtime(self, workspace: db_models.Workspace, runtime_info: RuntimeInfo) -> None:
        """更新 Browser Runtime 狀態"""
        workspace.browser_container_id = runtime_info.identifier
        workspace.browser_webrtc_internal_url = runtime_info.internal_url
        workspace.browser_webrtc_external_url = runtime_info.external_url
        workspace.browser_status = "running"
        workspace.browser_last_seen = datetime.utcnow()

    def _build_nextjs_runtime_context(self, workspace: db_models.Workspace) -> RuntimeContext:
        """構建 Next.js Runtime Context"""
        from app.services.container_image_service import get_container_image_service
        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace('-', '_')
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # 確保 workspace 目錄存在
        host_workspace.mkdir(parents=True, exist_ok=True)

        nextjs_container_name = f"workspace-nextjs-{workspace.id}"

        # Port mappings: 3003 (dev server) + 3013 (management API)
        port_mappings = [
            PortMapping(container_port=3003, host_port=workspace.nextjs_external_port, protocol="tcp"),
            PortMapping(container_port=3013, host_port=workspace.nextjs_api_external_port, protocol="tcp"),
        ]

        # 掛載相同的 workspace 目錄
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(
            network_name=self.settings.DOCKER_NETWORK,
            network_mode="bridge"
        )

        return RuntimeContext(
            environment={
                "WORKSPACE_ID": workspace.id,
                "PORT": "3003",
                "API_PORT": "3013",
                "WORKSPACE_DIR": "/workspace",
                "NODE_ENV": "development",
            },
            volumes=volumes,
            ports=port_mappings,
            network=network,
            labels={
                "image": image_service.get_nextjs_image_name(),
                "command": None,
                "working_dir": "/workspace"
            }
        )

    def _update_nextjs_runtime(self, workspace: db_models.Workspace, runtime_info: RuntimeInfo) -> None:
        """更新 Next.js Runtime 狀態"""
        workspace.nextjs_container_id = runtime_info.identifier
        workspace.nextjs_internal_url = runtime_info.internal_url
        workspace.nextjs_external_url = runtime_info.external_url or f"http://localhost:{workspace.nextjs_external_port}"
        workspace.nextjs_status = "running"
        workspace.nextjs_last_seen = datetime.utcnow()
        workspace.nextjs_created_at = datetime.utcnow()

        # 更新 web_preview URL 指向 nextjs 容器（向後相容）
        workspace.web_preview_external_url = workspace.nextjs_external_url
        workspace.web_preview_internal_url = workspace.nextjs_internal_url


def run_runtime_provision_task(workspace_id: str) -> None:
    """背景任務入口：開啟新的資料庫連線並執行佈建。"""

    from app.db.database import SessionLocal  # 避免循環匯入

    db = SessionLocal()
    try:
        service = RuntimeProvisionService(db)
        service.execute_runtime_provision(workspace_id)
    finally:
        db.close()


__all__ = [
    "RuntimeProvisionService",
    "run_runtime_provision_task",
]
