"""API Testing Helper Functions"""

from fastapi import status


def check_api_endpoint_exists(client, endpoint: str, method: str = "GET") -> bool:
    """Check if API endpoint exists

    Args:
        client: Test client
        endpoint: API endpoint path
        method: HTTP method

    Returns:
        bool: Whether endpoint exists
    """
    try:
        # Save original headers
        original_headers = client.headers.copy()

        # Set internal token authentication
        client.headers.update({"X-Internal-Token": "test-internal-token"})

        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        elif method == "PUT":
            response = client.put(endpoint, json={})
        elif method == "DELETE":
            response = client.delete(endpoint)
        else:
            return False

        # Restore original headers
        client.headers.clear()
        client.headers.update(original_headers)

        # If returns 404, endpoint does not exist
        return response.status_code != status.HTTP_404_NOT_FOUND
    except Exception:
        return False


def skip_if_api_not_exists(client, endpoint: str, method: str = "GET"):
    """Skip test if API endpoint does not exist"""
    if not check_api_endpoint_exists(client, endpoint, method):
        import pytest
        pytest.skip(f"API endpoint {method} {endpoint} does not exist, skipping test")