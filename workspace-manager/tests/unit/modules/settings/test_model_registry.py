from __future__ import annotations

import logging

import pytest

from app.config.model_registry import (
    GLOBAL_MODEL_REGISTRY,
    normalize_model_selection,
    selection_to_persisted,
)


def test_global_registry_defaults_are_valid() -> None:
    for tool_id, config in GLOBAL_MODEL_REGISTRY.items():
        assert config.default_model in config.models
        assert len(config.models) >= 1
        assert len(config.models) == len(set(config.models))


def test_read_mode_derives_available_models_from_global_and_custom() -> None:
    selection = normalize_model_selection(
        "codex",
        {
            "customModels": [" gpt-custom ", "gpt-custom", ""],
            "allowedModels": ["gpt-custom"],
            "defaultModel": "gpt-custom",
            "availableModels": ["stale-should-be-ignored"],
        },
        mode="read",
    )

    assert selection.custom_models == ["gpt-custom"]
    assert selection.available_models[0] == "gpt-5.6-sol"
    assert "gpt-custom" in selection.available_models
    assert "stale-should-be-ignored" not in selection.available_models
    assert selection.allowed_models == ["gpt-custom"]
    assert selection.default_model == "gpt-custom"


def test_update_mode_rejects_empty_allowed_models() -> None:
    with pytest.raises(ValueError, match="allowedModels must not be empty"):
        normalize_model_selection(
            "claude",
            {
                "customModels": [],
                "allowedModels": ["", "   "],
                "defaultModel": "",
            },
            mode="update",
        )


def test_update_mode_rejects_default_outside_allowed_models() -> None:
    with pytest.raises(ValueError, match="defaultModel must be one of allowedModels"):
        normalize_model_selection(
            "opencode",
            {
                "customModels": ["opencode-custom"],
                "allowedModels": ["opencode-custom"],
                "defaultModel": "opencode-oss",
            },
            mode="update",
        )


def test_read_mode_recovers_bad_persisted_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    app_logger = logging.getLogger("app")
    previous_propagate = app_logger.propagate
    app_logger.propagate = True

    try:
        selection = normalize_model_selection(
            "opencode",
            {
                "customModels": ["opencode-custom"],
                "allowedModels": [],
                "defaultModel": "missing",
            },
            mode="read",
        )
    finally:
        app_logger.propagate = previous_propagate

    assert selection.allowed_models == ["opencode-oss"]
    assert selection.default_model == "opencode-oss"
    assert "Recovered invalid model selection" in caplog.text


def test_selection_to_persisted_excludes_available_models() -> None:
    selection = normalize_model_selection(
        "codex",
        {
            "customModels": ["gpt-custom"],
            "allowedModels": ["gpt-5.6-sol", "gpt-custom"],
            "defaultModel": "gpt-custom",
        },
        mode="update",
    )

    persisted = selection_to_persisted(selection)

    assert persisted == {
        "customModels": ["gpt-custom"],
        "allowedModels": ["gpt-5.6-sol", "gpt-custom"],
        "defaultModel": "gpt-custom",
    }
    assert "availableModels" not in persisted
