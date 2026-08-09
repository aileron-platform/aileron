import pytest
from pydantic import ValidationError

from app.modules.workspace.models import WorkspaceCreateRequest, WorkspaceUpdateRequest


@pytest.mark.parametrize(
    ("model", "payload"),
    (
        (
            WorkspaceCreateRequest,
            {
                "name": "Workspace",
                "runtime": "universal",
                "runtimeResources": {
                    "requests": {"cpu": "750m", "memory": "2Gi"},
                    "limits": {"cpu": "2500m", "memory": "6Gi"},
                },
            },
        ),
        (
            WorkspaceUpdateRequest,
            {
                "runtimeResources": {
                    "requests": {"cpu": "750m", "memory": "2Gi"},
                    "limits": {"cpu": "2500m", "memory": "6Gi"},
                },
            },
        ),
    ),
)
def test_workspace_mutations_reject_runtime_resource_overrides(
    model: type[WorkspaceCreateRequest] | type[WorkspaceUpdateRequest],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"
