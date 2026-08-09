"""Manager adapters for the shared file-conflict wire contract."""

import pytest
from pydantic import ValidationError

from app.core.file_management import (
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileExtractExecutionRequest,
)


def test_models_emit_exact_shared_wire_fields() -> None:
    assert set(FileConflictPreflightRequest.model_json_schema()["properties"]) == {
        "operation",
        "targetPath",
        "sources",
        "archivePath",
    }
    assert set(FileConflictPreflightResponse.model_json_schema()["properties"]) == {
        "conflicts",
        "total",
    }
    assert set(FileConflictBatchResult.model_json_schema()["properties"]) == {
        "items",
        "total",
        "succeeded",
        "skipped",
        "failed",
    }


def test_execution_models_require_strategy_and_resolutions() -> None:
    with pytest.raises(ValidationError):
        FileConflictExecutionRequest.model_validate(
            {
                "targetPath": "docs",
                "sources": [{"sourcePath": "a.txt", "entryType": "file"}],
            }
        )
    with pytest.raises(ValidationError):
        FileExtractExecutionRequest.model_validate(
            {"archivePath": "archive.zip", "targetPath": "docs"}
        )


@pytest.mark.parametrize("removed", ["rename", "overwrite", "reject"])
def test_removed_conflict_strategies_are_rejected(removed: str) -> None:
    with pytest.raises(ValidationError):
        FileConflictExecutionRequest.model_validate(
            {
                "targetPath": "docs",
                "sources": [{"sourcePath": "a.txt", "entryType": "file"}],
                "defaultStrategy": removed,
                "resolutions": [],
            }
        )


def test_file_conflict_payloads_forbid_extra_aliases() -> None:
    with pytest.raises(ValidationError):
        FileExtractExecutionRequest.model_validate(
            {
                "archivePath": "archive.zip",
                "targetPath": "docs",
                "defaultStrategy": "cancel",
                "resolutions": [],
                "conflictStrategy": "rename",
            }
        )
