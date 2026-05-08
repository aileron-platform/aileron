"""
Role and permission check decorators and dependency injection

Provides decorators and dependency injection functions for checking user roles and permissions.
"""

from functools import wraps
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTValidationError, get_jwt_utils


class PermissionDeniedError(HTTPException):
    """Insufficient permission exception"""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def load_role_mapping() -> dict:
    """Load role mapping configuration

    Returns:
        Role mapping configuration dictionary
    """
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent / "role_mapping.yaml"

    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_user_permissions(roles: List[str] | None) -> List[str]:
    """Get permission list based on user role

    Args:
        roles: User role list

    Returns:
        Permission list
    """
    role_mapping = load_role_mapping()
    role_mappings = role_mapping.get("role_mappings", {})
    normalized_roles = [role for role in (roles or []) if isinstance(role, str)]
    if not normalized_roles:
        default_role = role_mapping.get("default_role")
        normalized_roles = [default_role] if isinstance(default_role, str) else []

    # Collect permissions from all roles
    permissions = set()
    processed_roles = set()

    def add_role_permissions(role: str):
        """Recursively add role permissions (handle inheritance)"""
        if role in processed_roles:
            return

        processed_roles.add(role)

        # Add direct permissions of this role
        if role in role_mappings:
            role_config = role_mappings[role]
            role_permissions = role_config.get("permissions", [])
            permissions.update(role_permissions)

            # Handle role inheritance
            inheritance = role_mapping.get("role_inheritance", {})
            if role in inheritance:
                for parent_role in inheritance[role].get("inherits", []):
                    add_role_permissions(parent_role)

    # Add permissions from all roles
    for role in normalized_roles:
        add_role_permissions(role)

    if not permissions:
        default_role = role_mapping.get("default_role")
        if isinstance(default_role, str):
            add_role_permissions(default_role)

    # Application custom rules (optional)
    # TODO: Implement custom_rules logic

    return list(permissions)


def has_permission(permission: str, user_permissions: List[str]) -> bool:
    """Check if user has specific permission

    Args:
        permission: Permission to check
        user_permissions: User permission list

    Returns:
        True if user has the permission
    """
    if permission in user_permissions:
        return True
    if "*:all" in user_permissions:
        return True

    resource, separator, _scope = permission.partition(":")
    if separator and f"{resource}:all" in user_permissions:
        return True

    return False


def has_role(role: str, user_roles: List[str]) -> bool:
    """Check if user has specific role

    Args:
        role: Role to check
        user_roles: User role list

    Returns:
        True if user has the role
    """
    return role in user_roles


def has_any_role(roles: List[str], user_roles: List[str]) -> bool:
    """Check if user has any of the specified roles

    Args:
        roles: Role list to check
        user_roles: User role list

    Returns:
        True if user has any of the roles
    """
    return any(role in user_roles for role in roles)


def has_all_permissions(permissions: List[str], user_permissions: List[str]) -> bool:
    """Check if user has all specified permissions

    Args:
        permissions: Permission list to check
        user_permissions: User permission list

    Returns:
        True if user has all permissions
    """
    return all(has_permission(perm, user_permissions) for perm in permissions)


def has_any_permission(permissions: List[str], user_permissions: List[str]) -> bool:
    """Check if user has any of the specified permissions

    Args:
        permissions: Permission list to check
        user_permissions: User permission list

    Returns:
        True if user has any of the permissions
    """
    return any(has_permission(perm, user_permissions) for perm in permissions)


# ============================================================================
# FastAPI dependency injection functions
# ============================================================================

async def get_current_user(
    request: Request,
    config = Depends(get_keycloak_config)
) -> dict:
    """Get current user information from request

    Args:
        request: FastAPI request object
        config: Keycloak configuration

    Returns:
        User information dictionary (contains sub, username, email, roles, etc.)

    Raises:
        HTTPException: When authentication fails
    """
    if not config.enabled:
        # Authentication not enabled, return empty user
        return {}

    # Extract token from Authorization header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        # Validate and decode token
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
    """Optional current user information (authentication not required)

    Args:
        request: FastAPI request object
        config: Keycloak configuration

    Returns:
        User information dictionary, returns None if not authenticated
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
    """Dependency injection requiring user to be authenticated

    Args:
        current_user: Current user information
        config: Keycloak configuration

    Returns:
        User information dictionary

    Raises:
        HTTPException: When user is not authenticated
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
# Role check decorator factory functions
# ============================================================================

def require_role(required_role: str):
    """Decorator factory requiring specific role

    Args:
        required_role: Required role name

    Returns:
        Decorator function

    Usage example:
        @router.get("/admin")
        @require_role("admin")
        async def admin_endpoint():
            return {"message": "Admin access"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current_user from kwargs
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionDeniedError("Authentication required")

            # GetUserRole
            user_roles = current_user.get("roles", [])

            if not has_role(required_role, user_roles):
                raise PermissionDeniedError(f"Role '{required_role}' required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_role(*required_roles: str):
    """Decorator factory requiring any of specific roles

    Args:
        *required_roles: List of required role names

    Returns:
        Decorator function

    Usage example:
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
    """Decorator factory requiring specific permission

    Args:
        required_permission: Required permission name

    Returns:
        Decorator function

    Usage example:
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

            # GetUserPermission
            user_roles = current_user.get("roles", [])
            user_permissions = get_user_permissions(user_roles)

            if not has_permission(required_permission, user_permissions):
                raise PermissionDeniedError(f"Permission '{required_permission}' required")

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*required_permissions: str):
    """Decorator factory requiring any of specific permissions

    Args:
        *required_permissions: List of required permission names

    Returns:
        Decorator function
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
    """Decorator factory requiring all of specific permissions

    Args:
        *required_permissions: List of required permission names

    Returns:
        Decorator function
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
    """Get current user ID from request.state

    Args:
        request: FastAPI request object

    Returns:
        str: User ID

    Raises:
        HTTPException: When user is not authenticated
    """
    from fastapi import status, HTTPException
    
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: User not authenticated",
        )
    return request.state.user_id
