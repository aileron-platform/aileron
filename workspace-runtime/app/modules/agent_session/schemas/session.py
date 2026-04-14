"""Backward-compatible session schema exports.

Deprecated: 新程式碼請改用 app.modules.agent_session.schemas.agent_session。
"""

from .agent_session import PermissionDecisionRequest

__all__ = ["PermissionDecisionRequest"]
