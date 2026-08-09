from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.i18n import I18nMiddleware


class StubI18nService:
    def __init__(self) -> None:
        self.translate_calls: list[tuple[str, str]] = []

    def resolve_language(self, preferred: str) -> str:
        if preferred.startswith("zh"):
            return "zh-TW"
        return "en"

    def translate(self, key: str, *, language: str) -> str:
        self.translate_calls.append((key, language))
        return f"{language}:{key}"


def create_app(stub_i18n: StubI18nService, monkeypatch) -> FastAPI:
    monkeypatch.setattr("app.middleware.i18n.get_i18n_service", lambda: stub_i18n)
    monkeypatch.setattr(
        "app.middleware.i18n.get_settings",
        lambda: SimpleNamespace(AILERON_WORKSPACE_ID="ws-test"),
    )

    app = FastAPI()
    app.add_middleware(I18nMiddleware, default_language="zh-TW")

    @app.get("/language")
    async def language(request: Request) -> dict[str, str]:
        return {
            "language": request.state.language,
            "translated": request.state.translate("greeting"),
        }

    return app


def test_x_language_header_has_highest_priority(monkeypatch) -> None:
    stub_i18n = StubI18nService()
    client = TestClient(create_app(stub_i18n, monkeypatch))

    response = client.get(
        "/language",
        headers={
            "X-Language": "en-US",
            "Accept-Language": "zh-TW,zh;q=0.9",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"language": "en", "translated": "en:greeting"}
    assert response.headers["Content-Language"] == "en"


def test_accept_language_used_when_x_language_missing(monkeypatch) -> None:
    stub_i18n = StubI18nService()
    client = TestClient(create_app(stub_i18n, monkeypatch))

    response = client.get("/language", headers={"Accept-Language": "zh-TW,zh;q=0.9"})

    assert response.status_code == 200
    assert response.json()["language"] == "zh-TW"
    assert stub_i18n.translate_calls == [("greeting", "zh-TW")]


def test_default_language_used_when_headers_missing(monkeypatch) -> None:
    stub_i18n = StubI18nService()
    client = TestClient(create_app(stub_i18n, monkeypatch))

    response = client.get("/language")

    assert response.status_code == 200
    assert response.json()["language"] == "zh-TW"
    assert response.headers["Content-Language"] == "zh-TW"
