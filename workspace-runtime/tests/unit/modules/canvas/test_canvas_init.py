"""Tests for canvas module __init__.py"""
import pytest
from fastapi import APIRouter


class TestCanvasModuleInit:
    """Tests for canvas module initialization and lazy loading"""

    def test_router_attribute_access(self):
        """Test accessing router attribute triggers lazy loading"""
        from app.modules.canvas import router

        assert router is not None
        # Verify it's an APIRouter instance
        assert isinstance(router, APIRouter)

    def test_invalid_attribute_raises_error(self):
        """Test accessing invalid attribute raises AttributeError"""
        import app.modules.canvas as canvas_module

        with pytest.raises(AttributeError) as exc_info:
            _ = canvas_module.invalid_attribute

        assert "has no attribute 'invalid_attribute'" in str(exc_info.value)

    def test_all_exports(self):
        """Test __all__ contains expected exports"""
        from app.modules.canvas import __all__

        assert 'router' in __all__
        assert 'CanvasService' in __all__
        assert 'get_canvas_service' in __all__

    def test_direct_imports(self):
        """Test directly imported items are available"""
        from app.modules.canvas import (
            CanvasService,
            get_canvas_service,
        )

        assert CanvasService is not None
        assert get_canvas_service is not None
        assert CanvasService.__name__ == 'CanvasService'
