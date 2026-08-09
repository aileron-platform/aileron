import pytest
from fastapi import HTTPException

from app.core.resource_envelope import ResourceResult, raise_resource_error


def test_resource_result_camel_alias():
    result = ResourceResult(revision="r1", resource={"id": "a"})

    dumped = result.model_dump(by_alias=True, exclude_none=True)

    assert dumped == {"revision": "r1", "resource": {"id": "a"}}


def test_raise_resource_error_shape():
    with pytest.raises(HTTPException) as exc_info:
        raise_resource_error("SCOPE_NOT_SUPPORTED", "nope", 404)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "errorCode": "SCOPE_NOT_SUPPORTED",
        "message": "nope",
    }
