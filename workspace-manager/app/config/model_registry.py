"""Global AI model registry and per-user model selection normalization."""

from __future__ import annotations

import logging
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, model_validator

AgenticToolId = Literal["claude", "codex", "opencode"]
NormalizeMode = Literal["read", "update"]

logger = logging.getLogger(__name__)


class GlobalToolModelConfig(BaseModel):
    models: list[str] = Field(min_length=1)
    default_model: str = Field(alias="defaultModel")

    @model_validator(mode="after")
    def _default_must_be_available(self) -> "GlobalToolModelConfig":
        if self.default_model not in self.models:
            raise ValueError("defaultModel must be one of models")
        if len(self.models) != len(set(self.models)):
            raise ValueError("models must not contain duplicates")
        return self


class NormalizedToolModelSelection(BaseModel):
    custom_models: list[str] = Field(alias="customModels")
    available_models: list[str] = Field(alias="availableModels")
    allowed_models: list[str] = Field(alias="allowedModels")
    default_model: str = Field(alias="defaultModel")


GLOBAL_MODEL_REGISTRY: dict[AgenticToolId, GlobalToolModelConfig] = {
    "claude": GlobalToolModelConfig(
        defaultModel="claude-opus-4-8",
        models=[
            "claude-fable-5",
            "claude-opus-4-8",
            "claude-sonnet-5",
            "claude-haiku-4-5",
        ],
    ),
    "codex": GlobalToolModelConfig(
        defaultModel="gpt-5.6-sol",
        models=[
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
            "gpt-5.5",
            "gpt-5.3-codex-spark",
            "gpt-5.4",
            "gpt-5.4-mini",
        ],
    ),
    "opencode": GlobalToolModelConfig(
        defaultModel="opencode-oss",
        models=["opencode-oss"],
    ),
}


def _clean_model_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        model = item.strip()
        if not model or model in seen:
            continue
        cleaned.append(model)
        seen.add(model)
    return cleaned


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def get_global_model_config(tool_id: AgenticToolId) -> GlobalToolModelConfig:
    return GLOBAL_MODEL_REGISTRY[tool_id]


def normalize_model_selection(
    tool_id: AgenticToolId,
    persisted: Mapping[str, Any] | None,
    *,
    mode: NormalizeMode,
) -> NormalizedToolModelSelection:
    config = get_global_model_config(tool_id)
    data = dict(persisted or {})

    custom_models = [
        model
        for model in _clean_model_list(data.get("customModels"))
        if model not in config.models
    ]
    available_models = _unique([*config.models, *custom_models])
    allowed_models = _clean_model_list(data.get("allowedModels"))
    allowed_models = [model for model in allowed_models if model in available_models]
    default_model = data.get("defaultModel")
    default_model = default_model.strip() if isinstance(default_model, str) else ""

    if not allowed_models:
        if mode == "update":
            raise ValueError("allowedModels must not be empty")
        logger.warning(
            "Recovered invalid model selection: empty allowedModels",
            extra={"tool_id": tool_id},
        )
        allowed_models = list(config.models)

    if not default_model:
        default_model = allowed_models[0] if mode == "update" else config.default_model

    if default_model not in allowed_models:
        if mode == "update":
            raise ValueError("defaultModel must be one of allowedModels")
        logger.warning(
            "Recovered invalid model selection: defaultModel outside allowedModels",
            extra={"tool_id": tool_id, "default_model": default_model},
        )
        default_model = (
            config.default_model
            if config.default_model in allowed_models
            else allowed_models[0]
        )

    return NormalizedToolModelSelection(
        customModels=custom_models,
        availableModels=available_models,
        allowedModels=allowed_models,
        defaultModel=default_model,
    )


def selection_to_persisted(
    selection: NormalizedToolModelSelection,
) -> dict[str, list[str] | str]:
    return {
        "customModels": selection.custom_models,
        "allowedModels": selection.allowed_models,
        "defaultModel": selection.default_model,
    }
