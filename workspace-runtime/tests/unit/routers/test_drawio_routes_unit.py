"""Draw.io Router 單元測試."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.modules.drawio.router import get_drawio_viewer_url, save_drawio_file


class MockFileService:
    def __init__(self, content: str = "<mxfile>test</mxfile>", raise_error: bool = False):
        self.content = content
        self.raise_error = raise_error
        self.write_file = Mock()

    def read_file(self, path: str, scope=None):
        if self.raise_error:
            raise FileNotFoundError(path)

        class FileResponse:
            def __init__(self, content):
                self.content = content

        return FileResponse(self.content)


class MockI18nService:
    def __call__(self, key: str, **kwargs):
        return f"{key}:{kwargs}" if kwargs else key


@pytest.mark.asyncio
async def test_get_drawio_viewer_url_returns_json_response():
    result = await get_drawio_viewer_url(
        file_path="test.drawio",
        mode="view",
        file_service=MockFileService(),
        translate=MockI18nService(),
    )

    assert result.status_code == 200
    body = result.body.decode()
    assert '"mode":"view"' in body
    assert '"file_path":"test.drawio"' in body


@pytest.mark.asyncio
async def test_get_drawio_viewer_url_raises_404_for_missing_file():
    with pytest.raises(HTTPException) as exc_info:
        await get_drawio_viewer_url(
            file_path="missing.drawio",
            mode="view",
            file_service=MockFileService(raise_error=True),
            translate=MockI18nService(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_save_drawio_file_calls_file_service_write():
    file_service = MockFileService()

    result = await save_drawio_file(
        file_path="test.drawio",
        content="<mxfile>test</mxfile>",
        file_service=file_service,
        translate=MockI18nService(),
    )

    assert result.status_code == 200
    file_service.write_file.assert_called_once()


@pytest.mark.asyncio
async def test_save_drawio_file_rejects_invalid_xml():
    with pytest.raises(HTTPException) as exc_info:
        await save_drawio_file(
            file_path="test.drawio",
            content="not xml",
            file_service=MockFileService(),
            translate=MockI18nService(),
        )

    assert exc_info.value.status_code == 400
