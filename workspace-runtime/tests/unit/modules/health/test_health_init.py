"""Tests for health module __init__.py"""
import pytest
from fastapi import APIRouter


class TestHealthModuleInit:
    """Tests for health module initialization and lazy loading"""

    def test_router_attribute_access(self):
        """Test accessing router attribute triggers lazy loading"""
        from app.modules.health import router

        assert router is not None
        assert isinstance(router, APIRouter)

    def test_service_attribute_access(self):
        """Test accessing service attribute triggers lazy loading"""
        import app.modules.health.service as service

        assert service is not None
        import types
        assert isinstance(service, types.ModuleType)
        assert hasattr(service, 'HealthCheckService')

    def test_invalid_attribute_raises_error(self):
        """Test accessing invalid attribute raises AttributeError"""
        import app.modules.health as health_module

        with pytest.raises(AttributeError) as exc_info:
            _ = health_module.invalid_attribute

        assert "has no attribute 'invalid_attribute'" in str(exc_info.value)

    def test_all_exports(self):
        """Test __all__ contains expected exports"""
        from app.modules.health import __all__

        assert 'router' in __all__
        assert 'service' in __all__
        assert 'dependencies' in __all__
