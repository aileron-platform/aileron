from __future__ import annotations

import hashlib

import pytest
from fastapi import HTTPException

from app.core.revision import assert_revision, compute_revision


def test_compute_revision_stable_full_sha256() -> None:
    assert compute_revision("abc") == hashlib.sha256(b"abc").hexdigest()
    assert compute_revision("abc") == compute_revision(b"abc")
    assert compute_revision("abc") != compute_revision("abd")


def test_assert_revision_conflict() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_revision(current="r1", expected="r2")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {
        "errorCode": "REVISION_CONFLICT",
        "message": "Resource was modified",
    }


def test_assert_revision_allows_match_and_transition_missing_expected() -> None:
    assert_revision(current="r1", expected="r1")
    assert_revision(current="r1", expected=None)
