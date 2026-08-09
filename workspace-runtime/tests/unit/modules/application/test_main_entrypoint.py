"""Workspace Runtime process entrypoint tests."""

from app import main as runtime_main


def test_main_reuses_loaded_app_when_reload_is_disabled(
    monkeypatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(application: object, **kwargs: object) -> None:
        calls.append((application, kwargs))

    monkeypatch.setattr(runtime_main.settings, "DEBUG", False)
    monkeypatch.setattr("uvicorn.run", fake_run)

    runtime_main.main()

    assert calls == [
        (
            runtime_main.app,
            {
                "host": runtime_main.settings.HOST,
                "port": runtime_main.settings.PORT,
                "reload": False,
                "log_level": "info",
                "access_log": True,
            },
        )
    ]


def test_main_uses_import_string_when_reload_is_enabled(
    monkeypatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(application: object, **kwargs: object) -> None:
        calls.append((application, kwargs))

    monkeypatch.setattr(runtime_main.settings, "DEBUG", True)
    monkeypatch.setattr("uvicorn.run", fake_run)

    runtime_main.main()

    assert calls == [
        (
            "app.main:app",
            {
                "host": runtime_main.settings.HOST,
                "port": runtime_main.settings.PORT,
                "reload": True,
                "log_level": "debug",
                "access_log": True,
            },
        )
    ]
