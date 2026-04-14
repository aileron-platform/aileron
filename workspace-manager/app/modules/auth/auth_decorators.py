"""
角色和權限檢查裝飾器與依賴注入

提供用於檢查用戶角色和權限的裝飾器和依賴注入函數。
"""

from functools import wraps
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTValidationError, get_jwt_utils


class PermissionDeniedError(HTTPException):
    """權限不足異常"""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def load_role_mapping() -> dict:
    """載入角色映射配置

    Returns:
        角色映射配置字典
    """
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent / "role_mapping.yaml"

    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_user_permissions(roles: List[str]) -> List[str]:
    """根據用戶角色獲取權限列表

    Args:
        roles: 用戶角色列表

    Returns:
        權限列表
    """
    role_mapping = load_role_mapping()
    role_mappings = role_mapping.get("role_mappings", {})

    # 收集所有角色的權限
    permissions = set()
    processed_roles = set()

    def add_role_permissions(role: str):
        """遞歸添加角色權限（處理繼承）"""
        if role in processed_roles:
            return

        processed_roles.add(role)

        # 添加該角色的直接權限
        if role in role_mappings:
            role_config = role_mappings[role]
            role_permissions = role_config.get("permissions", [])
            permissions.update(role_permissions)

            # 處理角色繼承
            inheritance = role_mapping.get("role_inheritance", {})
            if role in inheritance:
                for parent_role in inheritance[role].get("inherits", []):
                    add_role_permissions(parent_role)

    # 添加所有角色的權限
    for role in roles:
        add_role_permissions(role)

    # 應用自定義規則（可選）
    # TODO: 實作 custom_rules 的邏輯

    return list(permissions)


def has_permission(permission: str, user_permissions: List[str]) -> bool:
    """檢查用戶是否具有特定權限

    Args:
        permission: 要檢查的權限
        user_permissions: 用戶權限列表

    Returns:
        True 如果用戶具有該權限
    """
    return permission in user_permissions


def has_role(role: str, user_roles: List[str]) -> bool:
    """檢查用戶是否具有特定角色

    Args:
        role: 要檢查的角色
        user_roles: 用戶角色列表

    Returns:
        True 如果用戶具有該角色
    """
    return role in user_roles


def has_any_role(roles: List[str], user_roles: List[str]) -> bool:
    """檢查用戶是否具有任一指定角色

    Args:
        roles: 要檢查的角色列表
        user_roles: 用戶角色列表

    Returns:
        True 如果用戶具有任一角色
    """
    return any(role in user_roles for role in roles)


def has_all_permissions(permissions: List[str], user_permissions: List[str]) -> bool:
    """檢查用戶是否具有所有指定權限

    Args:
        permissions: 要檢查的權限列表
        user_permissions: 用戶權限列表

    Returns:
        True 如果用戶具有所有權限
    """
    return all(perm in user_permissions for perm in permissions)


def has_any_permission(permissions: List[str], user_permissions: List[str]) -> bool:
    """檢查用戶是否具有任一指定權限

    Args:
        permissions: 要檢查的權限列表
        user_permissions: 用戶權限列表

    Returns:
        True 如果用戶具有任一權限
    """
    return any(perm in user_permissions for perm in permissions)


# ============================================================================
# FastAPI 依賴注入函數
# ============================================================================

async def get_current_user(
    request: Request,
    config = Depends(get_keycloak_config)
) -> dict:
    """從請求中獲取當前用戶信息

    Args:
        request: FastAPI 請求對象
        config: Keycloak 配置

    Returns:
        用戶信息字典（包含 sub, username, email, roles 等）

    Raises:
        HTTPException: 當認證失敗時
    """
    if not config.enabled:
        # 認證未啟用，返回空用戶
        return {}

    # 從 Authorization header 提取 token
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        # 驗證並解碼 token
        jwt_utils = get_jwt_utils()
        payload = jwt_utils.decode_token(token)

        return payload

    except JWTValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_current_user(
    request: Request,
    config = Depends(get_keycloak_config)
) -> Optional[dict]:
    """可選的當前用戶信息（不強制要求認證）

    Args:
        request: FastAPI 請求對象
        config: Keycloak 配置

    Returns:
        用戶信息字典，如果未認證則返回 None
    """
    if not config.enabled:
        return None

    try:
        return await get_current_user(request, config)
    except HTTPException:
        return None


async def require_authenticated_user(
    current_user: dict = Depends(get_current_user),
    config = Depends(get_keycloak_config)
) -> dict:
    """要求用戶已認證的依賴注入

    Args:
        current_user: 當前用戶信息
        config: Keycloak 配置

    Returns:
        用戶信息字典

    Raises:
        HTTPException: 當用戶未認證時
    """
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication is not enabled"
        )

    if not current_user or not current_user.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    return current_user


# ============================================================================
# 角色檢查裝飾器工廠函數
# ============================================================================

def require_role(required_role: str):
    """要求特定角色的裝飾器工廠

    Args:
        required_role: 必需的角色名稱

    Returns:
        裝飾器函數

    使用示例：
        @router.get("/admin")
        @require_role("admin")
        async def admin_endpoint():
            return {"message": "Admin access"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 從 kwargs 中獲取 current_user
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            # 獲取用戶角色
            user_roles = current_user.get("roles", [])

            if not has_role(required_role, user_roles):
                raise PermissionDeniedError(f"Role '{required_role}' required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_role(*required_roles: str):
    """要求任一特定角色的裝飾器工廠

    Args:
        *required_roles: 必需的角色名稱列表

    Returns:
        裝飾器函數

    使用示例：
        @router.get("/moderator")
        @require_any_role("admin", "moderator")
        async def moderator_endpoint():
            return {"message": "Moderator access"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            user_roles = current_user.get("roles", [])

            if not has_any_role(list(required_roles), user_roles):
                raise PermissionDeniedError(f"One of roles {required_roles} required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_permission(required_permission: str):
    """要求特定權限的裝飾器工廠

    Args:
        required_permission: 必需的權限名稱

    Returns:
        裝飾器函數

    使用示例：
        @router.post("/workspaces")
        @require_permission("workspace:create")
        async def create_workspace():
            return {"message": "Workspace created"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            # 獲取用戶權限
            user_roles = current_user.get("roles", [])
            user_permissions = get_user_permissions(user_roles)

            if not has_permission(required_permission, user_permissions):
                raise PermissionDeniedError(f"Permission '{required_permission}' required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*required_permissions: str):
    """要求任一特定權限的裝飾器工廠

    Args:
        *required_permissions: 必需的權限名稱列表

    Returns:
        裝飾器函數
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            user_roles = current_user.get("roles", [])
            user_permissions = get_user_permissions(user_roles)

            if not has_any_permission(list(required_permissions), user_permissions):
                raise PermissionDeniedError(f"One of permissions {required_permissions} required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_all_permissions(*required_permissions: str):
    """要求所有特定權限的裝飾器工廠

    Args:
        *required_permissions: 必需的權限名稱列表

    Returns:
        裝飾器函數
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            user_roles = current_user.get("roles", [])
            user_permissions = get_user_permissions(user_roles)

            if not has_all_permissions(list(required_permissions), user_permissions):
                raise PermissionDeniedError(f"All permissions {required_permissions} required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def get_current_user_id(request: Request) -> str:
    """從 request.state 獲取當前用戶 ID
    
    Args:
        request: FastAPI Request 物件
        
    Returns:
        str: 用戶 ID
        
    Raises:
        HTTPException: 當用戶未認證時
    """
    from fastapi import status, HTTPException
    
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: User not authenticated",
        )
    return request.state.user_id
