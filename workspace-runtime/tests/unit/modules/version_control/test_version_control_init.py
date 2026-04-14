"""Tests for version_control module __init__.py"""
import pytest
from fastapi import APIRouter


class TestVersionControlModuleInit:
    """Tests for version_control module initialization and lazy loading"""

    def test_router_attribute_access(self):
        """Test accessing router attribute triggers lazy loading"""
        from app.modules.version_control import router

        assert router is not None
        # Verify it's an APIRouter instance
        assert isinstance(router, APIRouter)

    def test_invalid_attribute_raises_error(self):
        """Test accessing invalid attribute raises AttributeError"""
        import app.modules.version_control as vc_module

        with pytest.raises(AttributeError) as exc_info:
            _ = vc_module.invalid_attribute

        assert "has no attribute 'invalid_attribute'" in str(exc_info.value)

    def test_all_exports(self):
        """Test __all__ contains expected exports"""
        from app.modules.version_control import __all__

        assert 'router' in __all__
        assert 'GitService' in __all__
        assert 'VersionControlError' in __all__
        assert 'get_git_service' in __all__

    def test_direct_imports(self):
        """Test directly imported items are available"""
        from app.modules.version_control import (
            GitService,
            VersionControlError,
            get_git_service,
        )

        assert GitService is not None
        assert VersionControlError is not None
        assert get_git_service is not None
        assert GitService.__name__ == 'GitService'
