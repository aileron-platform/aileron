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
    """Volume mount configuration"""
    source: str          # Source (HostPath or volume name)
    target: str         # Target (path inside container)
    read_only: bool = False    # Only
    propagation: str = "rprivate"    # Propagation mode (rprivate/rslave/rshared)

@dataclass
class PortMapping:
    """Port mapping configuration"""
    container_port: int      # Container port
    host_port: Optional[int] = None # Host port (auto-assign if None)
    protocol: str = "tcp"          # Protocol (tcp/udp)

@dataclass
class ResourceRequirements:
    """Resource requirements"""
    cpu: str            # CPU limit (e.g., "1", "500m")
    memory: str         # Memory limit (e.g., "512M", "1G")
    storage: str = "10G"       # Storage requirement (e.g., "10G")

@dataclass
class NetworkConfig:
    """Network configuration"""
    network_name: str              # Network name
    network_mode: str = "bridge"            # Mode (bridge/host/none)
    dns_servers: List[str] = field(default_factory=list)        # DNS Server
    hostname: Optional[str] = None       # Container hostname
    expose_ports: List[int] = field(default_factory=list)       # Exposed ports

@dataclass
class RuntimeContext:
    """Runtime context"""
    environment: Dict[str, str] = field(default_factory=dict)      # EnvironmentVariable
    volumes: List[VolumeMount] = field(default_factory=list)       # Volume mounts
    ports: List[PortMapping] = field(default_factory=list)         # Port mappings
    resources: Optional[ResourceRequirements] = None  # Resource requirements
    network: Optional[NetworkConfig] = None           # Network configuration
    labels: Dict[str, str] = field(default_factory=dict)          # Labels
    restart_policy: str = "unless-stopped"             # Restart policy

@dataclass
class RuntimeInfo:
    """Runtime information (returned after successful creation)"""
    identifier: str              # Orchestrator-specific identifier (container_id / pod_name)
    workspace_id: str           # Workspace ID
    status: str                 # Status (running/stopped/error)
    internal_url: str           # Internal access URL
    created_at: datetime        # Creation time
    updated_at: datetime        # Update time
    platform: str               # Running platform (docker/kubernetes)
    external_url: Optional[str] = None # External access URL
    message: Optional[str] = None      # Status information (on error)
    extra_info: Dict[str, Any] = field(default_factory=dict)  # Extended information (e.g., K8s namespace)

@dataclass
class RuntimeStatus:
    """Runtime Status"""
    workspace_id: str
    status: str                 # running/stopped/paused/error/unknown
    container_id: str          # Container/Pod ID
    uptime: int = 0               # Running time (seconds)
    restart_count: int = 0         # Restart count
    cpu_usage: Optional[float] = None # CPU usage percentage (0-100)
    memory_usage: Optional[int] = None # Memory usage (bytes)
    memory_limit: Optional[int] = None # Memory limit (bytes)
    last_error: Optional[str] = None  # Last error information
    health_status: Optional[str] = None # Health status (healthy/unhealthy/none)
