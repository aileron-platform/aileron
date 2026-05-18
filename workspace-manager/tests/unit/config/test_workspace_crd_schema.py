from pathlib import Path

import yaml


def _workspace_crd_path() -> Path:
    container_chart_root = Path("/helm/aileron")
    if container_chart_root.exists():
        return container_chart_root / "crds" / "platform.aileron.io_workspaces.yaml"

    current = Path(__file__).resolve()
    repo_root = next(
        parent for parent in current.parents if (parent / "helm" / "aileron" / "crds").exists()
    )
    return repo_root / "helm" / "aileron" / "crds" / "platform.aileron.io_workspaces.yaml"


def test_workspace_crd_schema_omits_port_mappings():
    crd_path = _workspace_crd_path()

    document = yaml.safe_load(crd_path.read_text(encoding="utf-8"))
    spec_properties = (
        document["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
    )

    assert "portMappings" not in spec_properties


def test_workspace_crd_schema_includes_runtime_agent_state_contract():
    crd_path = _workspace_crd_path()

    document = yaml.safe_load(crd_path.read_text(encoding="utf-8"))
    runtime_properties = (
        document["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]["runtime"]["properties"]
    )

    agent_state = runtime_properties["agentState"]
    assert agent_state["required"] == ["pvcName", "subPathRoot", "mounts"]
    mount_properties = agent_state["properties"]["mounts"]["items"]["properties"]
    assert set(mount_properties) == {"provider", "sourceSubPath", "mountPath"}
