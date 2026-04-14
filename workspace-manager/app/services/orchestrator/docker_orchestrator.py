import docker
import logging
from typing import Optional, Any, Dict
from datetime import datetime
from .base import (
    ContainerOrchestrator,
    ContainerCreationError,
    ContainerNotFoundError,
    ContainerDeletionError,
    OrchestratorException
)
from .models import RuntimeInfo, RuntimeStatus, RuntimeContext, ResourceRequirements, RuntimeStatusType

logger = logging.getLogger(__name__)

class DockerOrchestrator(ContainerOrchestrator):
    """Docker 容器編排器"""

    def __init__(self, settings):
        self.settings = settings
        try:
            # 使用 settings 中的 DOCKER_HOST (如果有的話)
            # 這裡假設 settings 可能有 DOCKER_HOST，如果沒有則依賴環境變數
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise OrchestratorException(f"Failed to initialize Docker client: {e}")

    def create_workspace_runtime(self, workspace: Any, context: RuntimeContext) -> RuntimeInfo:
        try:
            container_name = f"workspace-runtime-{workspace.id}"
            
            # 1. 準備端口配置
            ports_config = {}
            for port_mapping in context.ports:
                key = f"{port_mapping.container_port}/{port_mapping.protocol}"
                # 如果 host_port 為 None，Docker 會自動分配
                ports_config[key] = port_mapping.host_port

            # 2. 準備 Volume 配置
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "ro" if volume.read_only else "rw",
                    # propagation? Docker py sdk uses 'bind' and 'mode', propagation is separate or part of bind options?
                    # standard docker-py bind mount dict: {'bind': '/mnt/vol1', 'mode': 'rw'}
                }

            # 3. 準備環境變數
            environment = context.environment.copy()

            # 4. 準備資源限制 (如果有)
            # Docker SDK run parameters for resources:
            # nano_cpus, mem_limit, etc.
            # 這裡暫時簡化，僅傳遞基本配置
            
            # 5. 網絡配置
            network_mode = context.network.network_mode if context.network else "bridge"
            network = context.network.network_name if context.network else None

            # 6. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={'max-size': '10m', 'max-file': '3'}
            )

            # 7. 清理舊容器
            try:
                old_container = self.client.containers.get(container_name)
                logger.info(f"Removing existing container {container_name}")
                old_container.remove(force=True)
            except docker.errors.NotFound:
                pass

            # 8. 啟動容器
            logger.info(f"Starting container {container_name} with image {context.labels.get('image', 'unknown')}")
            
            # 提取 image，如果 context.labels 中沒有，則需要從其他地方獲取
            # 這裡假設調用者會把 image 放在 labels 中，或者我們需要一個明確的 image 參數?
            # RuntimeContext 沒有 image 字段? 
            # 檢查 models.py -> RuntimeContext 沒有 image。
            # 但 RuntimeSpec (in plan) had it. 
            # 讓我們檢查 models.py again.
            # models.py: RuntimeContext definition does NOT have image.
            # But the caller (RuntimeProvisionService) knows the image.
            # We should probably add image to RuntimeContext or pass it separately?
            # Base class signature: create_workspace_runtime(self, workspace, context)
            # Maybe put image in context.labels['image'] or context.environment?
            # Or add image to RuntimeContext?
            # Let's add image to RuntimeContext in models.py later or use a convention.
            # For now, let's assume it's passed in context.labels['image'] or we use a default from settings if missing.
            
            image = context.labels.get('image')
            if not image:
                # Fallback or error?
                # For now, let's assume it's required in labels
                raise ContainerCreationError("Image not specified in context labels")

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                ports=ports_config,
                volumes=volumes_config,
                environment=environment,
                network=network,
                # network_mode=network_mode, # network and network_mode can conflict
                log_config=log_config,
                cap_add=["NET_ADMIN"], # 保留原有的 cap_add
                command=context.labels.get("command"), # Optional command override
                working_dir=context.labels.get("working_dir"),
            )

            # 9. 獲取運行時信息
            container.reload()
            
            # 解析映射後的端口
            # container.ports example: {'3002/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '32768'}]}
            
            # 構建 internal_url (使用容器名和默認端口)
            # 假設第一個端口是主服務端口
            default_port = context.ports[0].container_port if context.ports else 80
            internal_url = f"http://{container_name}:{default_port}"
            
            # 構建 external_url
            external_url = None
            ports_mapping = {}
            
            if context.ports:
                # 遍歷所有端口映射
                for port_mapping in context.ports:
                    port_key = f"{port_mapping.container_port}/{port_mapping.protocol}"
                    bindings = container.ports.get(port_key)
                    if bindings:
                        host_port = int(bindings[0]['HostPort'])
                        ports_mapping[port_key] = host_port
                        
                        # 如果是默認端口，設置 external_url
                        if port_mapping.container_port == default_port:
                            external_url = f"http://localhost:{host_port}"

            return RuntimeInfo(
                identifier=container.id,
                workspace_id=workspace.id,
                status=RuntimeStatusType.RUNNING,
                internal_url=internal_url,
                external_url=external_url,
                created_at=datetime.utcnow(), # Should parse container.attrs['Created']
                updated_at=datetime.utcnow(),
                platform="docker",
                extra_info={
                    "container_name": container_name,
                    "ports": ports_mapping
                }
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def delete_workspace_runtime(self, workspace_id: str) -> bool:
        container_name = f"workspace-runtime-{workspace_id}"
        try:
            container = self.client.containers.get(container_name)
            container.remove(force=True)
        except docker.errors.NotFound:
            pass  # 視為成功
        except Exception as e:
            logger.error(f"Failed to delete container {container_name}: {e}")
            raise ContainerDeletionError(f"Failed to delete container: {e}")

        # 同時刪除 Browser 容器
        browser_container_name = f"workspace-browser-{workspace_id}"
        try:
            browser_container = self.client.containers.get(browser_container_name)
            browser_container.remove(force=True)
            logger.info(f"Deleted Browser container {browser_container_name}")
        except docker.errors.NotFound:
            pass  # Browser 容器不存在，視為成功
        except Exception as e:
            logger.error(f"Failed to delete Browser container {browser_container_name}: {e}", exc_info=True)
            # 不拋出異常，因為主容器已刪除成功

        # 同時刪除 Next.js 容器
        nextjs_container_name = f"workspace-nextjs-{workspace_id}"
        try:
            nextjs_container = self.client.containers.get(nextjs_container_name)
            nextjs_container.remove(force=True)
            logger.info(f"Deleted Next.js container {nextjs_container_name}")
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.error(f"Failed to delete Next.js container {nextjs_container_name}: {e}", exc_info=True)

        return True

    def create_chrome_runtime(self, workspace: Any, context: RuntimeContext) -> RuntimeInfo:
        """建立 Browser 容器"""
        try:
            container_name = f"workspace-browser-{workspace.id}"

            # 1. 準備端口配置
            ports_config = {}
            for port_mapping in context.ports:
                key = f"{port_mapping.container_port}/{port_mapping.protocol}"
                ports_config[key] = port_mapping.host_port

            # 2. 準備 Volume 配置
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "rw" if not volume.read_only else "ro",
                }

            # 3. 準備環境變數
            environment = context.environment.copy()

            # 4. 網絡配置
            network = context.network.network_name if context.network else None

            # 5. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={'max-size': '10m', 'max-file': '3'}
            )

            # 6. 清理舊容器
            try:
                old_container = self.client.containers.get(container_name)
                logger.info(f"Removing existing Browser container {container_name}")
                old_container.remove(force=True)
            except docker.errors.NotFound:
                pass

            # 7. 獲取 image
            image = context.labels.get('image')
            if not image:
                raise ContainerCreationError("Browser image not specified in context labels")

            # 8. 啟動容器
            logger.info(f"Starting Browser container {container_name} with image {image}")

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                ports=ports_config,
                volumes=volumes_config,
                environment=environment,
                network=network,
                log_config=log_config,
                shm_size='2147483648',  # 2GB，Chrome 需要足夠的 /dev/shm 空間
            )

            # 9. 獲取運行時信息
            container.reload()

            # 構建 internal_url 和 external_url
            default_port = 6080  # neko WebRTC
            internal_url = f"http://{container_name}:{default_port}"
            external_url = f"http://localhost:{context.ports[0].host_port}"

            return RuntimeInfo(
                identifier=container.id,
                workspace_id=workspace.id,
                status=RuntimeStatusType.RUNNING,
                internal_url=internal_url,
                external_url=external_url,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                platform="docker",
                extra_info={
                    "container_name": container_name,
                    "ports": {f"{default_port}/tcp": context.ports[0].host_port}
                }
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating Browser container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def create_nextjs_runtime(self, workspace: Any, context: RuntimeContext) -> RuntimeInfo:
        """建立 Next.js 容器"""
        try:
            container_name = f"workspace-nextjs-{workspace.id}"

            # 1. 準備端口配置
            ports_config = {}
            for port_mapping in context.ports:
                key = f"{port_mapping.container_port}/{port_mapping.protocol}"
                ports_config[key] = port_mapping.host_port

            # 2. 準備 Volume 配置
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "rw" if not volume.read_only else "ro",
                }

            # 3. 準備環境變數
            environment = context.environment.copy()

            # 4. 網絡配置
            network = context.network.network_name if context.network else None

            # 5. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={'max-size': '10m', 'max-file': '3'}
            )

            # 6. 清理舊容器
            try:
                old_container = self.client.containers.get(container_name)
                logger.info(f"Removing existing Next.js container {container_name}")
                old_container.remove(force=True)
            except docker.errors.NotFound:
                pass

            # 7. 獲取 image
            image = context.labels.get('image')
            if not image:
                raise ContainerCreationError("Next.js image not specified in context labels")

            # 8. 啟動容器
            logger.info(f"Starting Next.js container {container_name} with image {image}")

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                ports=ports_config,
                volumes=volumes_config,
                environment=environment,
                network=network,
                log_config=log_config,
            )

            # 9. 獲取運行時信息
            container.reload()

            # 構建 internal_url 和 external_url（使用 Next.js dev server 端口 3003）
            default_port = 3003
            internal_url = f"http://{container_name}:{default_port}"

            # 從 port mappings 中找到 3003 的 external port
            external_url = None
            ports_mapping = {}
            for port_mapping in context.ports:
                port_key = f"{port_mapping.container_port}/{port_mapping.protocol}"
                bindings = container.ports.get(port_key)
                if bindings:
                    host_port = int(bindings[0]['HostPort'])
                    ports_mapping[port_key] = host_port
                    if port_mapping.container_port == default_port:
                        external_url = f"http://localhost:{host_port}"

            return RuntimeInfo(
                identifier=container.id,
                workspace_id=workspace.id,
                status=RuntimeStatusType.RUNNING,
                internal_url=internal_url,
                external_url=external_url,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                platform="docker",
                extra_info={
                    "container_name": container_name,
                    "ports": ports_mapping
                }
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating Next.js container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def get_runtime_status(self, workspace_id: str) -> RuntimeStatus:
        container_name = f"workspace-runtime-{workspace_id}"
        try:
            container = self.client.containers.get(container_name)
            status_str = container.status # 'running', 'exited', etc.
            
            # Map docker status to RuntimeStatusType
            status_map = {
                'running': RuntimeStatusType.RUNNING,
                'exited': RuntimeStatusType.STOPPED,
                'paused': RuntimeStatusType.PAUSED,
                'restarting': RuntimeStatusType.PENDING,
                'dead': RuntimeStatusType.ERROR
            }
            status = status_map.get(status_str, RuntimeStatusType.UNKNOWN)
            
            # Stats (optional, might be slow)
            # stats = container.stats(stream=False)
            
            return RuntimeStatus(
                workspace_id=workspace_id,
                status=status,
                container_id=container.id,
                # uptime calculation...
            )
        except docker.errors.NotFound:
            return RuntimeStatus(
                workspace_id=workspace_id,
                status=RuntimeStatusType.STOPPED, # Or unknown?
                container_id="",
                last_error="Container not found"
            )

    def get_runtime_logs(self, workspace_id: str, container: Optional[str] = None, tail: int = 100, timestamps: bool = False) -> str:
        container_name = f"workspace-runtime-{workspace_id}"
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=tail, timestamps=timestamps)
            return logs.decode('utf-8') if isinstance(logs, bytes) else logs
        except docker.errors.NotFound:
            raise ContainerNotFoundError(f"Container {container_name} not found")
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return ""

    def update_runtime_resources(self, workspace_id: str, resources: ResourceRequirements) -> bool:
        # Docker update command
        container_name = f"workspace-runtime-{workspace_id}"
        try:
            container = self.client.containers.get(container_name)
            # container.update(...)
            # cpu_quota, mem_limit etc.
            # Need to parse ResourceRequirements strings (e.g. "1G") to bytes
            # For now, just pass
            return True
        except Exception as e:
            logger.error(f"Failed to update resources: {e}")
            return False
