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
    return _core_workload(
        "DaemonSet",
        "workspace-firewall-attestor",
        cpu="10m",
        memory="32Mi",
        tolerations=[{"operator": "Exists"}],
    )


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
    taints: list[dict] | None = None,
    labels: dict[str, str] | None = None,
) -> dict:
    node_labels = {"kubernetes.io/arch": "amd64", **(labels or {})}
    return {
        "metadata": {
            "name": name,
            "labels": node_labels,
        },
        "spec": {
            "taints": taints
            if taints is not None
            else (
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
        "namespace": "workspace-system",
        "labels": {
            "app.kubernetes.io/instance": "aileron",
            "app.kubernetes.io/component": "workspace-firewall-attestor",
        },
    }
    return pod


def _core_workload(
    kind: str,
    component: str,
    *,
    cpu: str,
    memory: str,
    replicas: int = 1,
    node_selector: dict[str, str] | None = None,
    tolerations: list[dict] | None = None,
    strategy: dict | None = None,
) -> dict:
    selector = {
        "app.kubernetes.io/instance": "aileron",
        "app.kubernetes.io/component": component,
    }
    workload = {
        "kind": kind,
        "metadata": {"name": f"aileron-{component}"},
        "spec": {
            "selector": {"matchLabels": selector},
            "template": {
                "metadata": {"labels": selector},
                "spec": {
                    "nodeSelector": node_selector or {},
                    "tolerations": tolerations or [],
                    "containers": [
                        {
                            "name": component,
                            "resources": {
                                "requests": {"cpu": cpu, "memory": memory}
                            },
                        }
                    ],
                },
            },
        },
    }
    if kind != "DaemonSet":
        workload["spec"]["replicas"] = replicas
    if strategy is not None:
        strategy_key = "updateStrategy" if kind == "StatefulSet" else "strategy"
        workload["spec"][strategy_key] = strategy
    return workload


def _hook_job(
    component: str,
    *,
    cpu: str,
    memory: str,
    node_selector: dict[str, str] | None = None,
    tolerations: list[dict] | None = None,
) -> dict:
    labels = {
        "app.kubernetes.io/instance": "aileron",
        "app.kubernetes.io/component": component,
    }
    return {
        "kind": "Job",
        "metadata": {
            "name": f"aileron-{component}",
            "annotations": {"helm.sh/hook": "post-install,post-upgrade"},
        },
        "spec": {
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "nodeSelector": node_selector or {},
                    "tolerations": tolerations or [],
                    "containers": [
                        {
                            "name": component,
                            "resources": {
                                "requests": {"cpu": cpu, "memory": memory}
                            },
                        }
                    ],
                },
            }
        },
    }


def _representative_core_manifest() -> list[dict]:
    return [
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="400m",
            memory="512Mi",
        ),
        _core_workload(
            "Deployment",
            "frontend",
            cpu="100m",
            memory="128Mi",
            replicas=2,
        ),
        _core_workload(
            "Deployment",
            "workspace-operator",
            cpu="200m",
            memory="256Mi",
        ),
        _core_workload(
            "StatefulSet",
            "postgres",
            cpu="300m",
            memory="512Mi",
        ),
        _core_workload(
            "StatefulSet",
            "redis",
            cpu="100m",
            memory="128Mi",
        ),
        _core_workload(
            "DaemonSet",
            "workspace-runtime-prepuller",
            cpu="50m",
            memory="64Mi",
        ),
        _core_workload(
            "DaemonSet",
            "connectivity-external-agent",
            cpu="30m",
            memory="32Mi",
            node_selector={"node-role.aileron.dev/agent": "true"},
        ),
    ]


def _current_core_pod(
    component: str,
    node_name: str,
    *,
    cpu: str,
    memory: str,
    terminating: bool = False,
) -> dict:
    pod = _pod(node_name, cpu=cpu, memory=memory)
    pod["metadata"] = {
        "namespace": "workspace-system",
        "labels": {
            "app.kubernetes.io/instance": "aileron",
            "app.kubernetes.io/component": component,
        },
    }
    if terminating:
        pod["metadata"]["deletionTimestamp"] = "2026-08-09T00:00:00Z"
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


def test_named_inventory_merges_core_and_identity_release_manifests() -> None:
    digest = "a" * 64
    documents = [
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                "RUNTIME_K8S_IMAGE": f"registry/workspace-runtime@sha256:{digest}",
                "RUNTIME_K8S_BROWSER_IMAGE": f"registry/workspace-chrome@sha256:{digest}",
                "RUNTIME_K8S_CANVAS_IMAGE": f"registry/workspace-canvas@sha256:{digest}",
            },
        }
    ]
    for component in (
        "workspace-ui",
        "workspace-manager",
        "workspace-operator",
        "platform-postgres",
        "platform-redis",
        "platform-coturn",
        "platform-keycloak",
    ):
        documents.append(
            {
                "kind": "Deployment",
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {"image": f"registry/{component}@sha256:{digest}"}
                            ]
                        }
                    }
                },
            }
        )

    assert MODULE.named_workload_image_inventory(
        documents, identity_mode="bundledKeycloak"
    ) == {
        component: f"registry/{component}@sha256:{digest}"
        for component in MODULE.REQUIRED_WORKLOAD_IMAGE_COMPONENTS
    }


def test_named_inventory_rejects_same_component_with_different_refs() -> None:
    documents = [
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                "RUNTIME_K8S_IMAGE": "registry/workspace-runtime@sha256:a",
                "RUNTIME_K8S_BROWSER_IMAGE": "registry/workspace-chrome@sha256:b",
                "RUNTIME_K8S_CANVAS_IMAGE": "registry/workspace-canvas@sha256:c",
            },
        },
        {
            "kind": "Deployment",
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"image": "registry/workspace-runtime@sha256:d"}
                        ]
                    }
                }
            },
        },
    ]

    with pytest.raises(ValueError, match="multiple immutable references"):
        MODULE.named_workload_image_inventory(
            documents, identity_mode="bundledKeycloak"
        )


def test_named_inventory_external_oidc_requires_only_core_workloads() -> None:
    digest = "a" * 64
    documents = [
        {
            "kind": "ConfigMap",
            "metadata": {"name": "aileron-platform-config"},
            "data": {
                "RUNTIME_K8S_IMAGE": f"registry/workspace-runtime@sha256:{digest}",
                "RUNTIME_K8S_BROWSER_IMAGE": f"registry/workspace-chrome@sha256:{digest}",
                "RUNTIME_K8S_CANVAS_IMAGE": f"registry/workspace-canvas@sha256:{digest}",
            },
        }
    ]
    for component in (
        set(MODULE.REQUIRED_WORKLOAD_IMAGE_COMPONENTS) - {"platform-keycloak"}
    ) - {"workspace-runtime", "workspace-chrome", "workspace-canvas"}:
        documents.append(
            {
                "kind": "Deployment",
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {"image": f"registry/{component}@sha256:{digest}"}
                            ]
                        }
                    }
                },
            }
        )

    result = MODULE.named_workload_image_inventory(
        documents, identity_mode="externalOidc"
    )

    assert "platform-keycloak" not in result
    assert set(result) == set(MODULE.REQUIRED_WORKLOAD_IMAGE_COMPONENTS) - {
        "platform-keycloak"
    }


def test_named_inventory_rejects_unknown_identity_mode() -> None:
    with pytest.raises(ValueError, match="identity mode"):
        MODULE.named_workload_image_inventory([], identity_mode="disabled")


def test_privileged_namespace_evidence_requires_installer_owner_and_psa() -> None:
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "aileron-turn-system",
            "labels": {
                "platform.aileron.dev/namespace-owner": "aileron-installer",
                "pod-security.kubernetes.io/enforce": "privileged",
            },
        },
    }

    MODULE.validate_privileged_namespace_evidence(
        [namespace],
        namespace="aileron-turn-system",
        owner_marker="aileron-installer",
    )

    for label in (
        "platform.aileron.dev/namespace-owner",
        "pod-security.kubernetes.io/enforce",
    ):
        invalid = json.loads(json.dumps(namespace))
        invalid["metadata"]["labels"].pop(label)
        with pytest.raises(ValueError, match="namespace evidence"):
            MODULE.validate_privileged_namespace_evidence(
                [invalid],
                namespace="aileron-turn-system",
                owner_marker="aileron-installer",
            )


def test_privileged_namespace_evidence_rejects_unrelated_documents() -> None:
    with pytest.raises(ValueError, match="exactly one Namespace"):
        MODULE.validate_privileged_namespace_evidence(
            [],
            namespace="aileron-turn-system",
            owner_marker="aileron-installer",
        )


@pytest.mark.parametrize(
    ("identity_mode", "manifest_count", "error"),
    [
        ("bundledKeycloak", 0, "requires exactly one"),
        ("bundledKeycloak", 2, "requires exactly one"),
        ("externalOidc", 1, "must not include"),
    ],
)
def test_named_inventory_rejects_identity_manifest_mode_conflicts(
    identity_mode: str,
    manifest_count: int,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        MODULE.validate_identity_manifest_selection(
            identity_mode=identity_mode,
            additional_manifest_count=manifest_count,
        )


def test_execution_plane_component_requests_use_helm_injected_resources() -> None:
    assert MODULE.execution_plane_component_requests(_execution_plane_manifest()) == [
        ("runtime", 500, 1024**3),
        ("browser", 500, 1024**3),
        ("canvas", 100, 1024**3),
    ]


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
        "available=worker-1=1500m/4Gi"
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

    assert result.startswith(
        "assignment=runtime:node-1,browser:node-2,canvas:node-2 "
        "required=1100m/3Gi "
        "components=runtime=500m/1Gi,browser=500m/1Gi,canvas=100m/1Gi "
        "available=node-1=2320m/1200Mi,node-2=2445m/2741Mi,"
        "node-3=2370m/2277Mi"
    )
    assert "planned-core-required=30m/96Mi" in result
    assert (
        "DaemonSet/default/aileron-workspace-firewall-attestor="
        "each(3)x10m/32Mi"
    ) in result


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

    result = MODULE.validate_execution_plane_capacity(
        manifest,
        nodes,
        pods,
        default_namespace="workspace-system",
        deployment_mode="upgrade",
    )

    assert result.startswith("assignment=runtime:node-1,browser:node-2,canvas:node-3 ")
    assert "planned-core-required=30m/96Mi" in result
    assert (
        "DaemonSet/workspace-system/aileron-workspace-firewall-attestor="
        "each(3)x10m/32Mi"
    ) in result


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


def test_execution_plane_capacity_rejects_tainted_nodes_for_untolerated_workloads() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "available=worker-tainted=4000m/8Gi.*unplaceable="
            "runtime=500m/1Gi,browser=500m/1Gi,canvas=100m/1Gi"
        ),
    ):
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


def test_clean_install_capacity_counts_complete_rendered_core_footprint() -> None:
    manifest = _execution_plane_manifest() + _representative_core_manifest()

    result = MODULE.validate_execution_plane_capacity(
        manifest,
        {
            "items": [
                _node(
                    "worker-1",
                    cpu="3",
                    memory="6Gi",
                    labels={"node-role.aileron.dev/agent": "true"},
                ),
                _node(
                    "worker-2",
                    cpu="3",
                    memory="6Gi",
                    labels={"node-role.aileron.dev/agent": "true"},
                ),
                _node("worker-3", cpu="3", memory="6Gi"),
            ]
        },
        {"items": []},
        default_namespace="workspace-system",
    )

    assert "planned-core-required=1410m/1920Mi" in result
    assert (
        "Deployment/workspace-system/aileron-workspace-manager=1x400m/512Mi"
        in result
    )
    assert "Deployment/workspace-system/aileron-frontend=2x100m/128Mi" in result
    assert "StatefulSet/workspace-system/aileron-postgres=1x300m/512Mi" in result
    assert "StatefulSet/workspace-system/aileron-redis=1x100m/128Mi" in result
    assert (
        "Deployment/workspace-system/aileron-workspace-operator=1x200m/256Mi"
        in result
    )
    assert (
        "DaemonSet/workspace-system/aileron-workspace-runtime-prepuller="
        "each(3)x50m/64Mi"
    ) in result
    assert (
        "DaemonSet/workspace-system/aileron-connectivity-external-agent="
        "each(2)x30m/32Mi"
    ) in result


def test_upgrade_capacity_replaces_current_core_pod_with_planned_footprint() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="512Mi",
        )
    )
    result = MODULE.validate_execution_plane_capacity(
        manifest,
        {"items": [_node("worker-1", cpu="3", memory="5Gi")]},
        {
            "items": [
                _current_core_pod(
                    "workspace-manager",
                    "worker-1",
                    cpu="900m",
                    memory="1Gi",
                ),
                _pod("worker-1", cpu="100m", memory="256Mi"),
            ]
        },
        default_namespace="workspace-system",
        deployment_mode="upgrade",
    )

    assert "available=worker-1=2900m/4864Mi" in result
    assert "planned-core-required=1000m/1Gi" in result
    assert (
        "Deployment/workspace-system/aileron-workspace-manager="
        "peak(1+1)x500m/512Mi"
    ) in result


def test_upgrade_capacity_rejects_deployment_rollout_surge_false_pass() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="512Mi",
            replicas=3,
            strategy={
                "type": "RollingUpdate",
                "rollingUpdate": {"maxSurge": "50%", "maxUnavailable": 0},
            },
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "aileron-workspace-manager=2x"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="3", memory="6Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "workspace-manager",
                        "worker-1",
                        cpu="500m",
                        memory="512Mi",
                    )
                    for _ in range(3)
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_rejects_large_old_deployment_plus_new_surge() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="100m",
            memory="1Gi",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "available=worker-1=1100m/4Gi.*"
            "aileron-workspace-manager=1x"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1600m", memory="7Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "workspace-manager",
                        "worker-1",
                        cpu="500m",
                        memory="3Gi",
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_does_not_count_terminating_deployment_as_active() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="100m",
            memory="256Mi",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "aileron-workspace-manager=2x"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1700m", memory="4Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "workspace-manager",
                        "worker-1",
                        cpu="500m",
                        memory="512Mi",
                        terminating=True,
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_does_not_count_terminating_statefulset_as_active() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "StatefulSet",
            "postgres",
            cpu="400m",
            memory="1Gi",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "StatefulSet/workspace-system/aileron-postgres=1x"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1500m", memory="5Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "postgres",
                        "worker-1",
                        cpu="100m",
                        memory="512Mi",
                        terminating=True,
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_counts_hook_job_with_live_old_core() -> None:
    manifest = _execution_plane_manifest()
    manifest.extend(
        [
            _core_workload(
                "Deployment",
                "workspace-manager",
                cpu="100m",
                memory="256Mi",
            ),
            _hook_job(
                "admin-bootstrap",
                cpu="400m",
                memory="512Mi",
            ),
        ]
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "Job/workspace-system/aileron-admin-bootstrap=1x"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1800m", memory="6Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "workspace-manager",
                        "worker-1",
                        cpu="500m",
                        memory="1Gi",
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_counts_daemonset_on_newly_selected_node() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "DaemonSet",
            "workspace-runtime-prepuller",
            cpu="500m",
            memory="1Gi",
            node_selector={"node-role.aileron.dev/prepull": "true"},
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            r"aileron-workspace-runtime-prepuller=nodes\(new-node\)"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {
                "items": [
                    _node("old-node", cpu="1100m", memory="2560Mi"),
                    _node(
                        "new-node",
                        cpu="1100m",
                        memory="2560Mi",
                        labels={"node-role.aileron.dev/prepull": "true"},
                    ),
                ]
            },
            {
                "items": [
                    _current_core_pod(
                        "workspace-runtime-prepuller",
                        "old-node",
                        cpu="500m",
                        memory="1Gi",
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


@pytest.mark.parametrize(
    ("kind", "strategy"),
    [
        ("StatefulSet", {"type": "RollingUpdate"}),
        ("Deployment", {"type": "Recreate"}),
    ],
)
def test_upgrade_capacity_rejects_large_old_non_surge_phase(
    kind: str,
    strategy: dict,
) -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            kind,
            "postgres",
            cpu="100m",
            memory="256Mi",
            strategy=strategy,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "upgrade existing-Core-plus-surge phase.*"
            "available=worker-1=1050m/3Gi.*transition-additional=none"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1850m", memory="5Gi")]},
            {
                "items": [
                    _current_core_pod(
                        "postgres",
                        "worker-1",
                        cpu="800m",
                        memory="2Gi",
                    )
                ]
            },
            default_namespace="workspace-system",
            deployment_mode="upgrade",
        )


def test_upgrade_capacity_does_not_invent_recreate_or_statefulset_surge() -> None:
    manifest = [
        _core_workload(
            "Deployment",
            "frontend",
            cpu="100m",
            memory="128Mi",
            replicas=2,
            strategy={"type": "Recreate"},
        ),
        _core_workload(
            "StatefulSet",
            "postgres",
            cpu="500m",
            memory="512Mi",
            replicas=3,
            strategy={"type": "RollingUpdate"},
        ),
    ]

    workloads = MODULE.planned_core_workloads(
        manifest,
        default_namespace="workspace-system",
        deployment_mode="upgrade",
    )

    assert [(workload.kind, workload.capacity_replicas) for workload in workloads] == [
        ("Deployment", 2),
        ("StatefulSet", 3),
    ]


def test_capacity_counts_admin_bootstrap_hook_job_request() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _hook_job(
            "admin-bootstrap",
            cpu="25m",
            memory="64Mi",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "no feasible cross-node assignment.*"
            "planned-core-required=25m/64Mi.*"
            "Job/workspace-system/aileron-admin-bootstrap=1x25m/64Mi"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="1100m", memory="4Gi")]},
            {"items": []},
            default_namespace="workspace-system",
        )


def test_capacity_places_tolerated_workload_on_selected_tainted_node() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="512Mi",
            node_selector={"node-role.aileron.dev/core": "true"},
            tolerations=[
                {
                    "key": "dedicated",
                    "operator": "Equal",
                    "value": "core",
                    "effect": "NoSchedule",
                }
            ],
        )
    )
    nodes = {
        "items": [
            _node("workspace-node", cpu="1200m", memory="4Gi"),
            _node(
                "core-node",
                cpu="500m",
                memory="512Mi",
                labels={"node-role.aileron.dev/core": "true"},
                taints=[
                    {
                        "key": "dedicated",
                        "value": "core",
                        "effect": "NoSchedule",
                    }
                ],
            ),
        ]
    }

    result = MODULE.validate_execution_plane_capacity(
        manifest,
        nodes,
        {"items": []},
        default_namespace="workspace-system",
    )

    assert result.startswith(
        "assignment=runtime:workspace-node,browser:workspace-node,"
        "canvas:workspace-node "
    )
    assert "Deployment/workspace-system/aileron-workspace-manager=1x500m/512Mi" in result


def test_capacity_rejects_selected_tainted_node_without_matching_toleration() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="512Mi",
            node_selector={"node-role.aileron.dev/core": "true"},
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "planned-unplaceable=.*core:Deployment/workspace-system/"
            "aileron-workspace-manager:0"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {
                "items": [
                    _node("workspace-node", cpu="1200m", memory="4Gi"),
                    _node(
                        "core-node",
                        cpu="500m",
                        memory="512Mi",
                        labels={"node-role.aileron.dev/core": "true"},
                        taints=[
                            {
                                "key": "dedicated",
                                "value": "core",
                                "effect": "NoSchedule",
                            }
                        ],
                    ),
                ]
            },
            {"items": []},
            default_namespace="workspace-system",
        )


def test_capacity_rejects_finite_noexecute_toleration_for_steady_placement() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="512Mi",
            node_selector={"node-role.aileron.dev/core": "true"},
            tolerations=[
                {
                    "key": "dedicated",
                    "operator": "Equal",
                    "value": "core",
                    "effect": "NoExecute",
                    "tolerationSeconds": 300,
                }
            ],
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "planned-unplaceable=.*core:Deployment/workspace-system/"
            "aileron-workspace-manager:0"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {
                "items": [
                    _node("workspace-node", cpu="1200m", memory="4Gi"),
                    _node(
                        "core-node",
                        cpu="500m",
                        memory="512Mi",
                        labels={"node-role.aileron.dev/core": "true"},
                        taints=[
                            {
                                "key": "dedicated",
                                "value": "core",
                                "effect": "NoExecute",
                            }
                        ],
                    ),
                ]
            },
            {"items": []},
            default_namespace="workspace-system",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "affinity",
            {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "node-pool",
                                        "operator": "In",
                                        "values": ["core"],
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
        ),
        (
            "topologySpreadConstraints",
            [
                {
                    "maxSkew": 1,
                    "topologyKey": "kubernetes.io/hostname",
                    "whenUnsatisfiable": "DoNotSchedule",
                    "labelSelector": {"matchLabels": {"app": "manager"}},
                }
            ],
        ),
        ("nodeName", "worker-1"),
        ("schedulerName", "custom-scheduler"),
        ("schedulingGates", [{"name": "platform.aileron.dev/ready"}]),
        ("runtimeClassName", "kata"),
    ],
)
def test_capacity_rejects_unmodeled_scheduling_constraints(
    field: str,
    value: object,
) -> None:
    workload = _core_workload(
        "Deployment",
        "workspace-manager",
        cpu="500m",
        memory="512Mi",
    )
    workload["spec"]["template"]["spec"][field] = value

    with pytest.raises(
        ValueError,
        match=f"unsupported scheduling constraints: .*:{field}",
    ):
        MODULE.validate_execution_plane_capacity(
            _execution_plane_manifest() + [workload],
            {"items": [_node("worker-1")]},
            {"items": []},
            default_namespace="workspace-system",
        )


def test_capacity_rejects_firewall_attestor_shortfall_on_tolerated_tainted_node() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(_firewall_attestor_daemonset())

    with pytest.raises(
        ValueError,
        match=(
            "planned-unplaceable=.*DaemonSet/workspace-system/"
            "aileron-workspace-firewall-attestor@tainted-node"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {
                "items": [
                    _node("workspace-node", cpu="1200m", memory="4Gi"),
                    _node(
                        "tainted-node",
                        cpu="5m",
                        memory="16Mi",
                        taints=[
                            {
                                "key": "dedicated",
                                "value": "core",
                                "effect": "NoExecute",
                            }
                        ],
                    ),
                ]
            },
            {"items": []},
            default_namespace="workspace-system",
        )


def test_capacity_solver_preserves_selectors_for_equal_capacity_nodes() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "Deployment",
            "workspace-manager",
            cpu="500m",
            memory="1Gi",
            node_selector={"node-role.aileron.dev/stateful": "true"},
        )
    )

    result = MODULE.validate_execution_plane_capacity(
        manifest,
        {
            "items": [
                _node(
                    "node-1",
                    cpu="800m",
                    memory="2Gi",
                    labels={"node-role.aileron.dev/stateful": "true"},
                ),
                _node("node-2", cpu="800m", memory="2Gi"),
                _node("node-3", cpu="800m", memory="2Gi"),
            ]
        },
        {"items": []},
        default_namespace="workspace-system",
    )

    assert result.startswith(
        "assignment=runtime:node-2,browser:node-3,canvas:node-1 "
    )


def test_clean_install_capacity_rejects_core_plus_workspace_shortfall() -> None:
    manifest = _execution_plane_manifest() + _representative_core_manifest()

    with pytest.raises(
        ValueError,
        match=(
            "no feasible cross-node assignment.*"
            "planned-core-required=1280m/1760Mi"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {
                "items": [
                    _node(
                        "worker-1",
                        cpu="2",
                        memory="4Gi",
                        labels={"node-role.aileron.dev/agent": "true"},
                    )
                ]
            },
            {"items": []},
            default_namespace="workspace-system",
        )


def test_capacity_rejects_daemonset_with_no_eligible_node() -> None:
    manifest = _execution_plane_manifest()
    manifest.append(
        _core_workload(
            "DaemonSet",
            "connectivity-external-agent",
            cpu="30m",
            memory="32Mi",
            node_selector={"node-role.aileron.dev/agent": "true"},
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "planned-unplaceable=.*DaemonSet/workspace-system/"
            "aileron-connectivity-external-agent@no-eligible-node"
        ),
    ):
        MODULE.validate_execution_plane_capacity(
            manifest,
            {"items": [_node("worker-1", cpu="4", memory="8Gi")]},
            {"items": []},
            default_namespace="workspace-system",
        )


def test_execution_plane_capacity_rejects_request_above_limit() -> None:
    manifest = _execution_plane_manifest()
    resources = json.loads(manifest[0]["data"]["RUNTIME_K8S_CANVAS_RESOURCES"])
    resources["limits"]["cpu"] = "50m"
    manifest[0]["data"]["RUNTIME_K8S_CANVAS_RESOURCES"] = json.dumps(resources)

    with pytest.raises(ValueError, match="request exceeds limit"):
        MODULE.execution_plane_component_requests(manifest)


def test_manifest_attestation_accepts_semantically_equal_yaml(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.yaml"
    live = tmp_path / "live.yaml"
    candidate.write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: identity\n"
        "data:\n  alpha: one\n  beta: two\n---\n"
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: identity\n",
        encoding="utf-8",
    )
    live.write_text(
        "kind: Service\nmetadata: {name: identity}\napiVersion: v1\n---\n"
        "kind: ConfigMap\ndata: {beta: two, alpha: one}\n"
        "metadata: {name: identity}\napiVersion: v1\n",
        encoding="utf-8",
    )

    MODULE.assert_equivalent_manifests(candidate, live)


def test_manifest_attestation_rejects_single_field_drift(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.yaml"
    live = tmp_path / "live.yaml"
    candidate.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: identity}\n"
        "spec: {replicas: 1}\n",
        encoding="utf-8",
    )
    live.write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: identity}\n"
        "spec: {replicas: 2}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match"):
        MODULE.assert_equivalent_manifests(candidate, live)


@pytest.mark.parametrize(
    ("document_class", "live_document"),
    [
        (
            "release",
            "apiVersion: v1\nkind: Service\nmetadata: {name: identity}\n",
        ),
        (
            "hooks",
            (
                "apiVersion: batch/v1\nkind: Job\nmetadata:\n"
                "  name: identity-bootstrap\n  annotations:\n"
                "    helm.sh/hook: post-install,post-upgrade\n"
            ),
        ),
    ],
)
def test_manifest_attestation_compares_release_resources_and_hooks_separately(
    tmp_path: Path,
    document_class: str,
    live_document: str,
) -> None:
    candidate = tmp_path / "candidate.yaml"
    live = tmp_path / "live.yaml"
    candidate.write_text(
        "apiVersion: v1\nkind: Service\nmetadata: {name: identity}\n---\n"
        "apiVersion: batch/v1\nkind: Job\nmetadata:\n"
        "  name: identity-bootstrap\n  annotations:\n"
        "    helm.sh/hook: post-install,post-upgrade\n",
        encoding="utf-8",
    )
    live.write_text(live_document, encoding="utf-8")

    MODULE.assert_equivalent_manifests(
        candidate,
        live,
        document_class=document_class,
    )
