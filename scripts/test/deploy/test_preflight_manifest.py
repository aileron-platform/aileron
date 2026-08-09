from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "preflight_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("preflight_manifest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _execution_plane_manifest() -> list[dict]:
    resources = {
        "RUNTIME_K8S_RUNTIME_RESOURCES": {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "3Gi"},
        },
        "RUNTIME_K8S_BROWSER_RESOURCES": {
            "requests": {"cpu": "500m", "memory": "1Gi"},
            "limits": {"cpu": "2000m", "memory": "2Gi"},
        },
        "RUNTIME_K8S_CANVAS_RESOURCES": {
            "requests": {"cpu": "100m", "memory": "1Gi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
    }
    return [
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                key: json.dumps(value, separators=(",", ":"))
                for key, value in resources.items()
            },
        }
    ]


def _firewall_attestor_daemonset() -> dict:
    return {
        "kind": "DaemonSet",
        "metadata": {
            "name": "aileron-workspace-firewall-attestor",
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "firewall-attestor",
                            "resources": {
                                "requests": {
                                    "cpu": "10m",
                                    "memory": "32Mi",
                                }
                            },
                        }
                    ]
                }
            }
        },
    }


def test_execution_plane_component_requests_rejects_inconsistent_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        MODULE,
        "DYNAMIC_RESOURCE_KEYS",
        MODULE.DYNAMIC_RESOURCE_KEYS[:-1],
    )

    with pytest.raises(
        ValueError,
        match="execution plane component resource keys are inconsistent",
    ):
        MODULE.execution_plane_component_requests(_execution_plane_manifest())


def _node(
    name: str,
    *,
    cpu: str = "4",
    memory: str = "8Gi",
    ready: bool = True,
    tainted: bool = False,
) -> dict:
    return {
        "metadata": {
            "name": name,
            "labels": {"kubernetes.io/arch": "amd64"},
        },
        "spec": {
            "taints": (
                [{"key": "dedicated", "value": "other", "effect": "NoSchedule"}]
                if tainted
                else []
            )
        },
        "status": {
            "allocatable": {"cpu": cpu, "memory": memory},
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True" if ready else "False",
                }
            ],
        },
    }


def _pod(node_name: str, *, cpu: str, memory: str) -> dict:
    return {
        "spec": {
            "nodeName": node_name,
            "containers": [{"resources": {"requests": {"cpu": cpu, "memory": memory}}}],
        },
        "status": {"phase": "Running"},
    }


def _attestor_pod(node_name: str) -> dict:
    pod = _pod(node_name, cpu="10m", memory="32Mi")
    pod["metadata"] = {
        "labels": {"app.kubernetes.io/component": "workspace-firewall-attestor"}
    }
    return pod


def test_inventory_includes_platform_and_dynamic_images() -> None:
    documents = [
        {
            "kind": "Deployment",
            "metadata": {"name": "aileron-workspace-manager"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"image": "harbor/aileron/workspace-manager@sha256:a"}
                        ]
                    }
                }
            },
        },
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                "RUNTIME_K8S_IMAGE": "harbor/aileron/runtime@sha256:b",
                "RUNTIME_K8S_BROWSER_IMAGE": "harbor/aileron/browser@sha256:c",
                "RUNTIME_K8S_CANVAS_IMAGE": "harbor/aileron/canvas@sha256:d",
            },
        },
    ]

    assert MODULE.image_inventory(documents) == [
        "harbor/aileron/browser@sha256:c",
        "harbor/aileron/canvas@sha256:d",
        "harbor/aileron/runtime@sha256:b",
        "harbor/aileron/workspace-manager@sha256:a",
    ]


def test_turn_enabled_reads_operator_environment() -> None:
    documents = [
        {
            "kind": "Deployment",
            "metadata": {"name": "aileron-workspace-operator"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "env": [
                                    {
                                        "name": "TURN_ICE_SERVERS_SECRET_NAME",
                                        "value": "external-turn",
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
        }
    ]

    assert MODULE.turn_enabled(documents) is True


def test_inventory_includes_init_ephemeral_and_cronjob_images() -> None:
    documents = [
        {
            "kind": "Deployment",
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"image": "registry/app@sha256:a"}],
                        "initContainers": [{"image": "registry/init@sha256:b"}],
                        "ephemeralContainers": [{"image": "registry/debug@sha256:c"}],
                    }
                }
            },
        },
        {
            "kind": "CronJob",
            "spec": {
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [{"image": "registry/cron@sha256:d"}]
                            }
                        }
                    }
                }
            },
        },
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                "RUNTIME_K8S_IMAGE": "registry/runtime@sha256:e",
                "RUNTIME_K8S_BROWSER_IMAGE": "registry/browser@sha256:f",
                "RUNTIME_K8S_CANVAS_IMAGE": "registry/canvas@sha256:0",
            },
        },
    ]

    assert MODULE.image_inventory(documents) == [
        "registry/app@sha256:a",
        "registry/browser@sha256:f",
        "registry/canvas@sha256:0",
        "registry/cron@sha256:d",
        "registry/debug@sha256:c",
        "registry/init@sha256:b",
        "registry/runtime@sha256:e",
    ]


def test_inventory_requires_every_dynamic_image() -> None:
    documents = [
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {"RUNTIME_K8S_IMAGE": "registry/runtime@sha256:a"},
        }
    ]

    with pytest.raises(ValueError, match="RUNTIME_K8S_BROWSER_IMAGE"):
        MODULE.image_inventory(documents)


def test_inventory_requires_platform_config() -> None:
    with pytest.raises(ValueError, match="platform config"):
        MODULE.image_inventory(
            [
                {
                    "kind": "Deployment",
                    "spec": {
                        "template": {
                            "spec": {"containers": [{"image": "registry/app@sha256:a"}]}
                        }
                    },
                }
            ]
        )


def test_execution_plane_component_requests_use_helm_injected_resources() -> None:
    assert MODULE.execution_plane_component_requests(_execution_plane_manifest()) == [
        ("runtime", 500, 1024**3),
        ("browser", 500, 1024**3),
        ("canvas", 100, 1024**3),
    ]


def test_firewall_attestor_request_is_per_node_overhead() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(_firewall_attestor_daemonset())

    assert MODULE.firewall_attestor_request(manifest) == (
        10,
        32 * 1024**2,
    )


def test_firewall_attestor_preflight_requires_exact_socket_and_freshness() -> None:
    manifest = [
        {
            "kind": "DaemonSet",
            "metadata": {
                "name": "aileron-workspace-firewall-attestor",
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "firewall-attestor",
                                "args": [
                                    "--cilium-socket-path=/var/run/cilium/cilium.sock",
                                    "--firewall-attestor-poll-interval=5s",
                                    "--firewall-attestation-max-age=30s",
                                ],
                                "resources": {
                                    "requests": {
                                        "cpu": "10m",
                                        "memory": "32Mi",
                                    },
                                    "limits": {
                                        "cpu": "100m",
                                        "memory": "64Mi",
                                    },
                                },
                                "volumeMounts": [
                                    {
                                        "name": "cilium-run",
                                        "mountPath": "/var/run/cilium/cilium.sock",
                                        "readOnly": True,
                                    }
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "cilium-run",
                                "hostPath": {
                                    "path": "/var/run/cilium/cilium.sock",
                                    "type": "Socket",
                                },
                            }
                        ],
                    }
                }
            },
        }
    ]

    MODULE.validate_firewall_attestor(manifest)
    manifest[0]["spec"]["template"]["spec"]["containers"][0]["args"][
        2
    ] = "--firewall-attestation-max-age=5s"
    with pytest.raises(ValueError, match="max age"):
        MODULE.validate_firewall_attestor(manifest)


def test_execution_plane_capacity_accounts_for_current_pod_requests() -> None:
    result = MODULE.validate_execution_plane_capacity(
        _execution_plane_manifest(),
        {"items": [_node("worker-1")]},
        {"items": [_pod("worker-1", cpu="2500m", memory="4Gi")]},
    )

    assert result == (
        "assignment=runtime:worker-1,browser:worker-1,canvas:worker-1 "
        "required=1100m/3Gi "
        "components=runtime=500m/1Gi,browser=500m/1Gi,canvas=100m/1Gi "
        "per-node-reserve=none available=worker-1=1500m/4Gi"
    )


def test_execution_plane_capacity_assigns_components_across_live_nodes() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(_firewall_attestor_daemonset())

    result = MODULE.validate_execution_plane_capacity(
        manifest,
        {
            "items": [
                _node("node-1", cpu="2320m", memory="1200Mi"),
                _node("node-2", cpu="2445m", memory="2741Mi"),
                _node("node-3", cpu="2370m", memory="2277Mi"),
            ]
        },
        {"items": []},
    )

    assert result == (
        "assignment=runtime:node-1,browser:node-2,canvas:node-2 "
        "required=1100m/3Gi "
        "components=runtime=500m/1Gi,browser=500m/1Gi,canvas=100m/1Gi "
        "per-node-reserve=firewall-attestor=10m/32Mi "
        "available=node-1=2320m/1200Mi,node-2=2445m/2741Mi,"
        "node-3=2370m/2277Mi"
    )


def test_execution_plane_capacity_allows_multiple_components_per_node() -> None:
    result = MODULE.validate_execution_plane_capacity(
        _execution_plane_manifest(),
        {
            "items": [
                _node("node-1", cpu="600m", memory="2Gi"),
                _node("node-2", cpu="600m", memory="2Gi"),
            ]
        },
        {"items": []},
    )

    assert result.startswith("assignment=runtime:node-1,browser:node-2,canvas:node-1 ")


def test_execution_plane_capacity_does_not_double_count_running_attestors() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(_firewall_attestor_daemonset())
    nodes = {
        "items": [
            _node("node-1", cpu="510m", memory="1056Mi"),
            _node("node-2", cpu="510m", memory="1056Mi"),
            _node("node-3", cpu="110m", memory="1056Mi"),
        ]
    }
    pods = {
        "items": [
            _attestor_pod("node-1"),
            _attestor_pod("node-2"),
            _attestor_pod("node-3"),
        ]
    }

    result = MODULE.validate_execution_plane_capacity(manifest, nodes, pods)

    assert result.startswith("assignment=runtime:node-1,browser:node-2,canvas:node-3 ")
    assert "per-node-reserve=firewall-attestor=10m/32Mi" in result


def test_pod_requests_include_init_maximum_and_runtime_overhead() -> None:
    pod = {
        "spec": {
            "containers": [
                {"resources": {"requests": {"cpu": "200m", "memory": "256Mi"}}},
                {"resources": {"requests": {"cpu": "300m", "memory": "256Mi"}}},
            ],
            "initContainers": [
                {"resources": {"requests": {"cpu": "700m", "memory": "1Gi"}}},
                {"resources": {"requests": {"cpu": "400m", "memory": "2Gi"}}},
            ],
            "overhead": {"cpu": "100m", "memory": "128Mi"},
        }
    }

    assert MODULE._pod_requests(pod) == (
        800,
        (2 * 1024**3) + (128 * 1024**2),
    )


def test_execution_plane_capacity_fails_before_deploy_when_no_node_fits() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "required=1100m/3Gi.*unplaceable="
            "runtime=500m/1Gi,browser=500m/1Gi,canvas=100m/1Gi"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            _execution_plane_manifest(),
            {"items": [_node("worker-1")]},
            {"items": [_pod("worker-1", cpu="3950m", memory="6Gi")]},
        )


def test_execution_plane_capacity_rejects_fragmented_memory() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "no feasible cross-node assignment.*available="
            "node-1=600m/1536Mi,node-2=600m/1536Mi.*unplaceable=none"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            _execution_plane_manifest(),
            {
                "items": [
                    _node("node-2", cpu="600m", memory="1536Mi"),
                    _node("node-1", cpu="600m", memory="1536Mi"),
                ]
            },
            {"items": []},
        )


def test_execution_plane_capacity_ignores_unready_and_tainted_nodes() -> None:
    with pytest.raises(ValueError, match="available=none"):
        MODULE.validate_execution_plane_capacity(
            _execution_plane_manifest(),
            {
                "items": [
                    _node("worker-unready", ready=False),
                    _node("worker-tainted", tainted=True),
                ]
            },
            {"items": []},
        )


def test_execution_plane_capacity_rejects_request_above_limit() -> None:
    manifest = _execution_plane_manifest()
    resources = json.loads(manifest[0]["data"]["RUNTIME_K8S_CANVAS_RESOURCES"])
    resources["limits"]["cpu"] = "50m"
    manifest[0]["data"]["RUNTIME_K8S_CANVAS_RESOURCES"] = json.dumps(resources)

    with pytest.raises(ValueError, match="request exceeds limit"):
        MODULE.execution_plane_component_requests(manifest)
