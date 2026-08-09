import json
import logging

from app.core.logging import ConsoleFormatter, StructuredFormatter


def test_structured_formatter_emits_thread_id() -> None:
    record = logging.makeLogRecord(
        {
            "name": "thread-test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "running",
            "thread_id": "thread-12345678",
        }
    )

    payload = json.loads(StructuredFormatter().format(record))

    assert payload["thread_id"] == "thread-12345678"
    assert "session_id" not in payload


def test_console_formatter_labels_thread_context() -> None:
    record = logging.makeLogRecord(
        {
            "name": "thread-test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "running",
            "thread_id": "thread-12345678",
        }
    )

    formatted = ConsoleFormatter(use_colors=False).format(record)

    assert "thread=thread-1" in formatted
    assert "sess=" not in formatted
