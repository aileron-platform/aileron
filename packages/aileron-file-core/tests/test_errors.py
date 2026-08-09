from aileron_file_core import (
    FileCoreError,
    PathOutsideRootError,
    VersionConflictError,
)


def test_file_core_error_exposes_code_details_and_status_hint() -> None:
    error = FileCoreError(
        code="INVALID_UPLOAD_FILENAME",
        message="Invalid filename",
        details={"filename": "../x"},
        status_hint=400,
    )

    assert str(error) == "Invalid filename"
    assert error.code == "INVALID_UPLOAD_FILENAME"
    assert error.details == {"filename": "../x"}
    assert error.status_hint == 400


def test_path_outside_root_error_uses_domain_neutral_shape() -> None:
    error = PathOutsideRootError("../secret")

    assert error.code == "PATH_OUTSIDE_ROOT"
    assert error.details == {"path": "../secret"}
    assert error.status_hint == 400
    assert error.path == "../secret"


def test_version_conflict_error_keeps_existing_attributes() -> None:
    error = VersionConflictError(
        path="notes.md",
        expected_version="sha256:old",
        actual_version="sha256:new",
    )

    assert error.code == "CONTENT_CONFLICT"
    assert error.details == {
        "path": "notes.md",
        "expectedVersion": "sha256:old",
        "actualVersion": "sha256:new",
    }
    assert error.status_hint == 409
    assert error.path == "notes.md"
    assert error.expected_version == "sha256:old"
    assert error.actual_version == "sha256:new"
