"""OpenAPI contracts shared across product resources."""

import pytest


@pytest.mark.integration
def test_shared_api_error_envelope_has_generic_openapi_name(test_app) -> None:
    client, _ = test_app
    openapi_schema = client.get("/openapi.json").json()
    openapi_paths = openapi_schema["paths"]
    expected_schema = {"$ref": "#/components/schemas/ApiErrorResponse"}

    knowledge_base_error_schema = openapi_paths["/api/v1/knowledge-bases"]["post"][
        "responses"
    ]["400"]["content"]["application/json"]["schema"]
    workspace_share_error_schema = openapi_paths[
        "/api/v1/workspaces/{workspace_id}/shares"
    ]["post"]["responses"]["409"]["content"]["application/json"]["schema"]

    assert knowledge_base_error_schema == expected_schema
    assert workspace_share_error_schema == expected_schema
    schemas = openapi_schema["components"]["schemas"]
    assert "KnowledgeBaseErrorDetail" not in schemas
    assert "KnowledgeBaseErrorResponse" not in schemas
    assert schemas["ApiErrorResponse"]["properties"]["detail"] == {
        "$ref": "#/components/schemas/ApiErrorDetail"
    }
    assert set(schemas["ApiErrorDetail"]["properties"]) == {
        "errorCode",
        "message",
        "details",
    }
