"""
Client Browser Relay module

CDP Relay Server for controlling client-side Chrome browser
This module serves as a bridge layer between Playwright client and Chrome extension

Technical Architecture:
    Playwright Client <-> Relay Server <-> Chrome Extension <-> Chrome Browser
           (WebSocket /cdp)    (WebSocket /extension)     (CDP)

WebSocket Endpoints:
    - /api/v1/client-browser-relay/cdp - Playwright client connection
    - /api/v1/client-browser-relay/extension - Chrome extension connection

HTTP Endpoints:
    - GET /api/v1/client-browser-relay/ - Health check and status
    - GET /api/v1/client-browser-relay/pages - List named pages
    - POST /api/v1/client-browser-relay/pages - Create named page
    - DELETE /api/v1/client-browser-relay/pages/{name} - Delete named page
"""

from .router import router
from .service import RelayService, get_relay_service

__all__ = ["router", "RelayService", "get_relay_service"]
