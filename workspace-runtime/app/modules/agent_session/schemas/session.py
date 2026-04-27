"""Backward-compatible session schema exports.

Deprecated: New code should use app.modules.agent_session.schemas.agent_session.
"""

from .agent_session import PermissionDecisionRequest

__all__ = ["PermissionDecisionRequest"]
