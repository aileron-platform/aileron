from __future__ import annotations

from typing import Any

from app.modules.thread.domain.enums import ThreadStatus
from app.modules.thread.persistence_models import ThreadModel


def apply_thread_error(
    model: ThreadModel,
    *,
    error_code: str,
    error_message: str | None,
    error_info: dict[str, Any] | None,
    preserve_existing_specific: bool = True,
) -> None:
    """Apply the canonical terminal error state to a thread."""
    has_specific_error = bool(
        preserve_existing_specific
        and model.error_code
        and error_code == "agent_process_failed"
        and model.error_code != "agent_process_failed"
    )

    model.status = ThreadStatus.ERROR.value
    model.active_turn_id = None
    model.active_turn_execution_id = None
    if has_specific_error:
        return

    resolved_info = dict(error_info or {})
    if error_message and "message" not in resolved_info:
        resolved_info["message"] = error_message

    model.error_code = error_code
    model.error_message = error_message
    model.error_info = resolved_info
