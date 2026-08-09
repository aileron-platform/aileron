"""Logging configuration tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core import logging as logging_module


def _capture_logging_config(monkeypatch: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        logging_module.logging.config,
        "dictConfig",
        lambda config: captured.setdefault("config", config),
    )
    return captured


def test_production_logging_only_uses_console_handlers(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        logging_module,
        "settings",
        SimpleNamespace(
            LOG_LEVEL="INFO", DEBUG=False, ENV="production", is_production=True
        ),
    )
    captured = _capture_logging_config(monkeypatch)

    logging_module.setup_logging()

    config = captured["config"]
    assert set(config["handlers"]) == {"console"}
    assert all(
        logger_config["handlers"] == ["console"]
        for logger_config in config["loggers"].values()
    )
    assert not (tmp_path / "logs").exists()


def test_development_logging_creates_rotating_file_handlers(
    monkeypatch: Any, tmp_path: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        logging_module,
        "settings",
        SimpleNamespace(
            LOG_LEVEL="DEBUG", DEBUG=True, ENV="development", is_production=False
        ),
    )
    captured = _capture_logging_config(monkeypatch)

    logging_module.setup_logging()

    config = captured["config"]
    assert set(config["handlers"]) == {"console", "app_file", "error_file"}
    assert config["loggers"]["app"]["handlers"] == [
        "console",
        "app_file",
        "error_file",
    ]
    assert config["loggers"]["docker"]["handlers"] == ["console", "app_file"]
    assert config["loggers"]["celery"]["handlers"] == ["console", "app_file"]
    assert (tmp_path / "logs").is_dir()
