from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class RuntimeStatusType(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"
    PENDING = "pending"
    UNKNOWN = "unknown"

@dataclass
class VolumeMount:
    """Volume 掛載配置"""
    source: str          # 源 (主機路徑或 volume 名稱)
    target: str         # 目標 (容器內路徑)
    read_only: bool = False    # 只讀
    propagation: str = "rprivate"    # 傳播模式 (rprivate/rslave/rshared)

@dataclass
class PortMapping:
    """端口映射配置"""
    container_port: int      # 容器端口
    host_port: Optional[int] = None # 主機端口 (None 時自動分配)
    protocol: str = "tcp"          # 協議 (tcp/udp)

@dataclass
class ResourceRequirements:
    """資源需求"""
    cpu: str            # CPU 限制 (e.g., "1", "500m")
    memory: str         # 內存限制 (e.g., "512M", "1G")
    storage: str = "10G"       # 存儲需求 (e.g., "10G")

@dataclass
class NetworkConfig:
    """網絡配置"""
    network_name: str              # 網絡名稱
    network_mode: str = "bridge"            # 模式 (bridge/host/none)
    dns_servers: List[str] = field(default_factory=list)        # DNS 伺服器
    hostname: Optional[str] = None       # 容器主機名
    expose_ports: List[int] = field(default_factory=list)       # 暴露端口

@dataclass
class RuntimeContext:
    """Runtime 上下文"""
    environment: Dict[str, str] = field(default_factory=dict)      # 環境變數
    volumes: List[VolumeMount] = field(default_factory=list)       # Volume 掛載
    ports: List[PortMapping] = field(default_factory=list)         # 端口映射
    resources: Optional[ResourceRequirements] = None  # 資源需求
    network: Optional[NetworkConfig] = None           # 網絡配置
    labels: Dict[str, str] = field(default_factory=dict)          # 標籤
    restart_policy: str = "unless-stopped"             # 重啟策略

@dataclass
class RuntimeInfo:
    """Runtime 信息 (創建成功後返回)"""
    identifier: str              # 編排器特定的標識符 (container_id / pod_name)
    workspace_id: str           # 工作區 ID
    status: str                 # 狀態 (running/stopped/error)
    internal_url: str           # 內部訪問 URL
    created_at: datetime        # 創建時間
    updated_at: datetime        # 更新時間
    platform: str               # 運行平台 (docker/kubernetes)
    external_url: Optional[str] = None # 外部訪問 URL
    message: Optional[str] = None      # 狀態信息 (错误時)
    extra_info: Dict[str, Any] = field(default_factory=dict)  # 擴展信息 (e.g. K8s namespace)

@dataclass
class RuntimeStatus:
    """Runtime 狀態"""
    workspace_id: str
    status: str                 # running/stopped/paused/error/unknown
    container_id: str          # 容器/Pod ID
    uptime: int = 0               # 運行時間 (秒)
    restart_count: int = 0         # 重啟次數
    cpu_usage: Optional[float] = None # CPU 使用百分比 (0-100)
    memory_usage: Optional[int] = None # 內存使用量 (字節)
    memory_limit: Optional[int] = None # 內存限制 (字節)
    last_error: Optional[str] = None  # 最後的錯誤信息
    health_status: Optional[str] = None # 健康狀態 (healthy/unhealthy/none)
