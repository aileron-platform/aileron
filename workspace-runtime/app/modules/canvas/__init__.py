"""Canvas 管理模組"""

from .dependencies import get_canvas_service
from .router import router
from .service import CanvasService

__all__ = ["router", "CanvasService", "get_canvas_service"]
