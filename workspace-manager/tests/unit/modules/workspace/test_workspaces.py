from __future__ import annotations

import inspect

import pytest

from app.modules.workspace.router import (
    _translate_workspace_share_message,
    _translate_workspace_value_error,
    create_workspace,
    delete_workspace,
    restart_workspace_component,
    start_workspace,
    stop_workspace,
)


def _translation_key(key: str, **_params: object) -> str:
    return key


@pytest.mark.unit
@pytest.mark.parametrize(
    "translator",
    [
        _translate_workspace_share_message,
        _translate_workspace_value_error,
    ],
)
def test_workspace_error_translation_fallback_uses_workspace_key(translator) -> None:
    assert translator(_translation_key, "WORKSPACE_UNKNOWN_ERROR") == (
        "workspace.invalid_request"
    )


@pytest.mark.unit
def test_lifecycle_handlers_do_not_accept_background_tasks() -> None:
    for handler in (
        create_workspace,
        start_workspace,
        stop_workspace,
        restart_workspace_component,
        delete_workspace,
    ):
        signature = inspect.signature(handler)
        assert "background_tasks" not in signature.parameters
