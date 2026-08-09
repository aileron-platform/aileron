from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VolumeSourceIdentity:
    """Manager-side identity used to fence a host bind source."""

    validation_path: str
    device: int
    inode: int


@dataclass
class VolumeMount:
    """Volume mount configuration"""

    source: str  # Source (HostPath or volume name)
    target: str  # Target (path inside container)
    read_only: bool = False  # Only
    source_identity: Optional[VolumeSourceIdentity] = None


@dataclass
class NetworkConfig:
    """Network configuration"""

    network_name: str  # Network name


@dataclass
class RuntimeContext:
    """Runtime context"""

    environment: Dict[str, str] = field(default_factory=dict)  # EnvironmentVariable
    volumes: List[VolumeMount] = field(default_factory=list)  # Volume mounts
    network: Optional[NetworkConfig] = None  # Network configuration
    labels: Dict[str, str] = field(default_factory=dict)  # Labels
    container_labels: Dict[str, str] = field(default_factory=dict)
    restart_policy: str = "unless-stopped"  # Restart policy


@dataclass
class RuntimeInfo:
    """Runtime information (returned after successful creation)"""

    identifier: str  # Orchestrator-specific identifier (container_id / pod_name)
    internal_url: str  # Internal access URL
    component_instance_id: Optional[str] = None
    extra_info: Dict[str, Any] = field(
        default_factory=dict
    )  # Extended information (e.g., K8s namespace)


@dataclass
class ExecutionPlaneInfo:
    """Identifiers created for one fenced Workspace generation."""

    runtime_instance_id: str
    runtime: RuntimeInfo
    browser: RuntimeInfo
    canvas: RuntimeInfo
    browser_probe: Optional[RuntimeInfo] = None
