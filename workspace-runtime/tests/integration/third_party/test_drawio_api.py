"""Draw.io 整合 API 測試"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.drawio.availability import DrawioAvailability
from app.modules.drawio.router import get_file_service_sync, get_i18n_service
from app.modules.file_system.exceptions import FileNotFoundException, FileTooLargeException, InvalidPathException

from .helpers import override_dependency


class DrawioFileServiceStub:
    """提供可配置回傳的檔案服務 stub"""

    def __init__(self, content: str = "<mxfile></mxfile>") -> None:
        self.content = content
        self.saved_request = None
        self.raise_missing = False
        self.read_error = None
        self.write_error = None

    def read_file(self, path: str, scope: str = None):  # pragma: no cover - 測試 stub
        if self.read_error:
            raise self.read_error
        if self.raise_missing:
            raise FileNotFoundException(path)
        return {"content": self.content, "path": path, "scope": scope}

    def write_file(self, request, scope: str = None, expected_version_id: str = None):  # pragma: no cover - 測試 stub
        if self.write_error:
            raise self.write_error
        # 處理 SaveFileRequest 或直接參數
        if hasattr(request, 'path') and hasattr(request, 'content'):
            path = request.path
            content = request.content
        else:
            # 向後相容：如果直接傳入參數
            path = request if isinstance(request, str) else "unknown"
            content = scope if isinstance(scope, str) else ""
            scope = expected_version_id

        self.saved_request = {"path": path, "content": content, "scope": scope}
        return {"path": path, "scope": scope}


class TranslateStub:
    def translate(self, key: str, **kwargs):  # pragma: no cover - 測試 stub
        if kwargs:
            parts = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            return f"{key}:{parts}"
        return key

    def __call__(self, key: str, **kwargs):  # pragma: no cover - 測試 stub
        # 使物件可調用，直接呼叫 translate 方法
        return self.translate(key, **kwargs)


# 創建一個模擬的 I18nService 實例
class MockI18nService:
    def __call__(self, key: str, **kwargs):
        if kwargs:
            parts = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            return f"{key}:{parts}"
        return key

    def translate(self, key: str, **kwargs):
        return self(key, **kwargs)

_translation_service = MockI18nService()


@pytest.fixture(autouse=True)
def drawio_available(monkeypatch):
    async def _available(settings, *, force_refresh=False):
        return DrawioAvailability(True, None, datetime.now(timezone.utc))

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _available)


def test_drawio_viewer_generates_url(client):
    service = DrawioFileServiceStub(content="<mxfile>demo</mxfile>")

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "diagram.drawio", "mode": "edit"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "edit"
    assert payload["file_path"] == "diagram.drawio"
    assert "draw" in payload["url"]  # URL contains draw (diagrams.net)


def test_drawio_viewer_empty_file_returns_error(client):
    service = DrawioFileServiceStub(content="   ")

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "diagram.drawio"},
        )

    assert response.status_code == 400
    # 確認錯誤訊息與空檔案相關
    error_detail = response.json()["detail"]
    assert "empty_file" in error_detail


def test_drawio_viewer_file_not_found(client):
    """測試檔案不存在的錯誤處理"""
    service = DrawioFileServiceStub()
    service.raise_missing = True

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "nonexistent.drawio"},
        )

    assert response.status_code == 404
    error_detail = response.json()["detail"]
    assert error_detail["code"] == "FILE_NOT_FOUND"


def test_drawio_viewer_invalid_path_returns_400(client):
    """測試 viewer 非法路徑回 400 而不是 500"""
    service = DrawioFileServiceStub()
    service.read_error = InvalidPathException("../diagram.drawio", "path traversal")

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "../diagram.drawio"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PATH"


def test_drawio_viewer_unavailable_returns_503(client, monkeypatch):
    """測試 viewer 在 Draw.io 停用時回結構化 503"""

    async def _unavailable(settings, *, force_refresh=False):
        return DrawioAvailability(False, "DISABLED", datetime.now(timezone.utc))

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _unavailable)
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "diagram.drawio"},
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "DRAWIO_UNAVAILABLE"
    assert detail["reason"] == "DISABLED"


def test_drawio_viewer_unreachable_returns_503(client, monkeypatch):
    """測試 viewer 在 Draw.io container 不可達時回結構化 503"""

    async def _unavailable(settings, *, force_refresh=False):
        return DrawioAvailability(False, "UNREACHABLE", datetime.now(timezone.utc))

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _unavailable)
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.get(
            "/api/v1/drawio/viewer",
            params={"file_path": "diagram.drawio"},
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "DRAWIO_UNAVAILABLE"
    assert detail["reason"] == "UNREACHABLE"


def test_drawio_save_success(client):
    """測試成功儲存 Draw.io 檔案"""
    service = DrawioFileServiceStub()
    content = "<mxfile><diagram id=\"1\">test content</diagram></mxfile>"

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": content}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["file_path"] == "diagram.drawio"
    # 驗證檔案服務的 write_file 被呼叫
    assert service.saved_request is not None
    assert service.saved_request["path"] == "diagram.drawio"
    assert service.saved_request["content"] == content


def test_drawio_save_empty_content_error(client):
    """測試儲存空內容的錯誤處理"""
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": "   "}
        )

    assert response.status_code == 400
    error_detail = response.json()["detail"]
    assert "empty_content" in error_detail


def test_drawio_save_invalid_xml_error(client):
    """測試儲存無效 XML 的錯誤處理"""
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": "invalid xml content"}
        )

    assert response.status_code == 400
    error_detail = response.json()["detail"]
    assert "invalid_xml" in error_detail


def test_drawio_save_invalid_path_returns_400(client):
    """測試 save 非法路徑回 400 而不是 500"""
    service = DrawioFileServiceStub()
    service.write_error = InvalidPathException("../diagram.drawio", "path traversal")

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "../diagram.drawio"},
            json={"content": "<mxfile><diagram /></mxfile>"}
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_PATH"


def test_drawio_save_file_too_large_returns_413(client):
    """測試 save 超大檔回 413 而不是 500"""
    service = DrawioFileServiceStub()
    service.write_error = FileTooLargeException("diagram.drawio", 10, 1)

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": "<mxfile><diagram /></mxfile>"}
        )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_drawio_save_unavailable_returns_503_without_write(client, monkeypatch):
    """測試 save 在 Draw.io 不可用時不進入寫檔"""

    async def _unavailable(settings, *, force_refresh=False):
        return DrawioAvailability(False, "UNREACHABLE", datetime.now(timezone.utc))

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _unavailable)
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": "<mxfile><diagram /></mxfile>"}
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "DRAWIO_UNAVAILABLE"
    assert detail["reason"] == "UNREACHABLE"
    assert service.saved_request is None


def test_drawio_save_disabled_returns_503_without_write(client, monkeypatch):
    """測試 save 在 Draw.io 停用時不進入寫檔"""

    async def _unavailable(settings, *, force_refresh=False):
        return DrawioAvailability(False, "DISABLED", datetime.now(timezone.utc))

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _unavailable)
    service = DrawioFileServiceStub()

    with override_dependency(get_file_service_sync, lambda: service), override_dependency(get_i18n_service, lambda: _translation_service):
        response = client.post(
            "/api/v1/drawio/save",
            params={"file_path": "diagram.drawio"},
            json={"content": "<mxfile><diagram /></mxfile>"}
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "DRAWIO_UNAVAILABLE"
    assert detail["reason"] == "DISABLED"
    assert service.saved_request is None


@pytest.mark.parametrize(
    ("available", "reason"),
    [
        (True, None),
        (False, "DISABLED"),
        (False, "UNREACHABLE"),
    ],
)
def test_drawio_availability_endpoint_returns_state(client, monkeypatch, available, reason):
    """測試 availability endpoint 回傳 helper 狀態"""

    checked_at = datetime.now(timezone.utc)

    async def _unavailable(settings, *, force_refresh=False):
        return DrawioAvailability(available, reason, checked_at)

    monkeypatch.setattr("app.modules.drawio.router.get_drawio_availability", _unavailable)

    response = client.get("/api/v1/drawio/availability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is available
    assert payload["reason"] == reason
    assert payload["checked_at"] == checked_at.isoformat()
