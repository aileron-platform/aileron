"""Knowledge base Git operation manager primitives."""

from contextlib import contextmanager
from typing import Iterator

from aileron_git_core import GitOperationInProgressError, OperationManager

KB_GIT_OPERATION_IN_PROGRESS = "KB_GIT_OPERATION_IN_PROGRESS"
KB_GIT_OPERATION_MANAGER = OperationManager()


def kb_git_operation_key(kb_id: str) -> str:
    return f"knowledge-base:{kb_id}"


@contextmanager
def kb_file_write_barrier(kb_id: str, *, operation_name: str) -> Iterator[None]:
    try:
        with KB_GIT_OPERATION_MANAGER.acquire_file_write_barrier(
            kb_git_operation_key(kb_id),
            operation_name=operation_name,
        ):
            yield
    except GitOperationInProgressError as exc:
        raise ValueError(KB_GIT_OPERATION_IN_PROGRESS) from exc


__all__ = [
    "KB_GIT_OPERATION_IN_PROGRESS",
    "KB_GIT_OPERATION_MANAGER",
    "kb_file_write_barrier",
    "kb_git_operation_key",
]
