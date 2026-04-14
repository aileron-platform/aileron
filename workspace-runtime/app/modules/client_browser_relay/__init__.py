"""
Client Browser Relay 模組

CDP Relay Server 用於控制用戶端的 Chrome 瀏覽器
此模組作為 Playwright 客戶端和 Chrome 擴展程式之間的橋接層

技術架構:
    Playwright 客戶端 <-> Relay Server <-> Chrome Extension <-> Chrome Browser
           (WebSocket /cdp)    (WebSocket /extension)     (CDP)

WebSocket 端點:
    - /api/v1/client-browser-relay/cdp - Playwright 客戶端連接
    - /api/v1/client-browser-relay/extension - Chrome 擴展連接

HTTP 端點:
    - GET /api/v1/client-browser-relay/ - 健康檢查和狀態
    - GET /api/v1/client-browser-relay/pages - 列出命名頁面
    - POST /api/v1/client-browser-relay/pages - 建立命名頁面
    - DELETE /api/v1/client-browser-relay/pages/{name} - 刪除命名頁面
"""

from .router import router
from .service import RelayService, get_relay_service

__all__ = ["router", "RelayService", "get_relay_service"]
