"""Marketplace Git operation manager integration tests."""

from __future__ import annotations

import pytest
from aileron_git_core import OperationManager

import app.modules.marketplace.workflows.package_git as marketplace_git_support_module
import app.modules.marketplace.workflows.registry_git as marketplace_registry_git_module
from app.config.settings import get_settings
from app.modules.marketplace.models import (
    MarketplaceRegistryRootMetadataSavePayload,
)
from app.modules.marketplace.request import MarketplaceRequest


@pytest.fixture
def operation_manager(monkeypatch):
    manager = OperationManager()
    monkeypatch.setattr(
        marketplace_git_support_module,
        "MARKETPLACE_GIT_OPERATION_MANAGER",
        manager,
    )
    monkeypatch.setattr(
        marketplace_registry_git_module,
        "MARKETPLACE_GIT_OPERATION_MANAGER",
        manager,
    )
    return manager


@pytest.fixture
def marketplace_workflows(tmp_path, monkeypatch, operation_manager):
    monkeypatch.setenv("MARKETPLACE_STORAGE_PATH", str(tmp_path / "marketplace"))
    get_settings.cache_clear()
    try:
        yield MarketplaceRequest.create()
    finally:
        get_settings.cache_clear()


def _metadata(
    name: str = "Team Marketplace",
) -> MarketplaceRegistryRootMetadataSavePayload:
    return MarketplaceRegistryRootMetadataSavePayload(
        name=name,
        owner={"name": "Team Maintainer", "email": "team@example.local"},
        description="Team package registry",
    )
