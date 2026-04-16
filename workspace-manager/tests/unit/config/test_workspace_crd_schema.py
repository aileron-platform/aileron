from pathlib import Path

import yaml


def test_workspace_crd_schema_omits_port_mappings():
    current = Path(__file__).resolve()
    repo_root = next(
        parent for parent in current.parents if (parent / "helm" / "aileron" / "crds").exists()
    )
    crd_path = repo_root / "helm" / "aileron" / "crds" / "platform.aileron.io_workspaces.yaml"

    document = yaml.safe_load(crd_path.read_text(encoding="utf-8"))
    spec_properties = (
        document["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
    )

    assert "portMappings" not in spec_properties
