from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.agent_session.schemas.agent_session import PermissionConfigCreate


def test_permission_config_create_rejects_invalid_gemini_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PermissionConfigCreate(gemini="invalid-mode")

    errors = exc_info.value.errors()
    assert errors[0]["ctx"]["code"] == "INVALID_GEMINI_PERMISSION_MODE"

