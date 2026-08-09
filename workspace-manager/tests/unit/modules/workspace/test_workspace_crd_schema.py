from pathlib import Path

import yaml


def _workspace_crd_path() -> Path:
    container_chart_root = Path("/helm/aileron")
    if container_chart_root.exists():
        return container_chart_root / "crds" / "platform.aileron.io_workspaces.yaml"

    current = Path(__file__).resolve()
    repo_root = next(
        parent
        for parent in current.parents
        if (parent / "helm" / "aileron" / "crds").exists()
    )
    return (
        repo_root / "helm" / "aileron" / "crds" / "platform.aileron.io_workspaces.yaml"
    )


def test_workspace_crd_schema_omits_port_mappings():
    crd_path = _workspace_crd_path()

    document = yaml.safe_load(crd_path.read_text(encoding="utf-8"))
    spec_properties = document["spec"]["versions"][0]["schema"]["openAPIV3Schema"][
        "properties"
    ]["spec"]["properties"]

    assert "portMappings" not in spec_properties


def test_workspace_crd_schema_keeps_runtime_secret_reference_and_worktree_subdir():
    document = yaml.safe_load(_workspace_crd_path().read_text(encoding="utf-8"))
    spec_schema = document["spec"]["versions"][0]["schema"]["openAPIV3Schema"][
        "properties"
    ]["spec"]
    runtime_schema = spec_schema["properties"]["runtime"]

    assert "worktreeSubdir" in spec_schema["required"]
    assert spec_schema["properties"]["worktreeSubdir"]["minLength"] == 1
    assert "runtimeSecretName" in runtime_schema["required"]
    assert runtime_schema["properties"]["runtimeSecretName"]["minLength"] == 1
    assert "controlAssertion" not in runtime_schema["properties"]
    assert "stateDatabaseSecretName" not in runtime_schema["properties"]


def test_workspace_crd_schema_contains_no_runtime_credential_material_fields():
    document = yaml.safe_load(_workspace_crd_path().read_text(encoding="utf-8"))
    runtime_properties = document["spec"]["versions"][0]["schema"]["openAPIV3Schema"][
        "properties"
    ]["spec"]["properties"]["runtime"]["properties"]

    forbidden_fragments = ("token", "password", "assertion", "databaseurl")
    allowed = {"assertion"}
    for field_name in runtime_properties:
        if field_name in allowed:
            continue
        normalized = field_name.lower()
        assert all(fragment not in normalized for fragment in forbidden_fragments)
