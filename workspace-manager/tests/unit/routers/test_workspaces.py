from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.workspaces import _reject_removed_port_configuration


def _translate(key: str, **params: object) -> str:
    return key.format(**params) if params else key


@pytest.mark.unit
def test_reject_removed_port_configuration_blocks_removed_fields() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _reject_removed_port_configuration(_translate, {"portMappings": []})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "workspace.port_mappings_removed"


@pytest.mark.unit
def test_reject_removed_port_configuration_blocks_system_port_fields() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _reject_removed_port_configuration(_translate, {"systemPortMappings": []})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "workspace.port_mappings_removed"


@pytest.mark.unit
def test_reject_removed_port_configuration_allows_empty_payload() -> None:
    _reject_removed_port_configuration(_translate, {"name": "workspace"})
