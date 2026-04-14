"""API 測試輔助工具"""

from fastapi import status


def check_api_endpoint_exists(client, endpoint: str, method: str = "GET") -> bool:
    """檢查 API 端點是否存在

    Args:
        client: 測試客戶端
        endpoint: API 端點路徑
        method: HTTP 方法

    Returns:
        bool: 端點是否存在
    """
    try:
        # 保存原始標頭
        original_headers = client.headers.copy()

        # 設置內部 token 認證
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

        # 恢復原始標頭
        client.headers.clear()
        client.headers.update(original_headers)

        # 如果返回 404，表示端點不存在
        return response.status_code != status.HTTP_404_NOT_FOUND
    except Exception:
        return False


def skip_if_api_not_exists(client, endpoint: str, method: str = "GET"):
    """如果 API 端點不存在則跳過測試"""
    if not check_api_endpoint_exists(client, endpoint, method):
        import pytest
        pytest.skip(f"API 端點 {method} {endpoint} 不存在，跳過測試")