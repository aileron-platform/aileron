"""
Tool Decision Manager.

Global Tool Decision Manager, references agor's permission-manager.ts design.
Routes Tool Decision decisions to correct session.

Responsibility separation explanation:
- ToolDecisionManager (this module): Global singleton, manages DecisionHooks routing in memory
  - Responsible for register/unregister hooks
  - Route decisions to correct session callback
  - No database access needed

- ToolDecisionService (tool_decision_service.py): Per-request instance, handles database operations
  - Create/update decision request messages
  - Manage asyncio event waiting/notification
  - Requires database access

Both work together: API endpoint calls ToolDecisionManager to wake up SDK callback,
while ToolDecisionService handles persisting state to database.
"""

from typing import Any, Dict, Optional, Protocol


class DecisionHooksProtocol(Protocol):
    """Protocol definition for DecisionHooks (for type checking)."""

    def resolve_decision(self, decision: Dict[str, Any]) -> bool:
        """Resolve Tool Decision."""
        ...


class ToolDecisionManager:
    """
    Global Tool Decision Manager.

    Responsibilities:
    - register_hooks(): Register session's DecisionHooks
    - unregister_hooks(): Unregister
    - resolve_decision(): Route decision to correct hooks (wake waiting SDK callback)
    - get_hooks(): Get hooks for specified session

    Notes:
    - DecisionHooks handle SDK callback wait/wake
    - ToolDecisionService handles DB state updates (called by API endpoint)
    """

    def __init__(self):
        """Initialize ToolDecisionManager."""
        self._hooks: Dict[str, DecisionHooksProtocol] = {}

    def register_hooks(self, session_id: str, hooks: DecisionHooksProtocol) -> None:
        """
        Register DecisionHooks for session.

        Args:
            session_id: Session ID
            hooks: DecisionHooks instance
        """
        self._hooks[session_id] = hooks

    def unregister_hooks(self, session_id: str) -> None:
        """
        Unregister DecisionHooks for session.

        Args:
            session_id: Session ID
        """
        if session_id in self._hooks:
            del self._hooks[session_id]

    def get_hooks(self, session_id: str) -> Optional[DecisionHooksProtocol]:
        """
        Get DecisionHooks for specified session.

        Args:
            session_id: Session ID

        Returns:
            DecisionHooks or None
        """
        return self._hooks.get(session_id)

    def resolve_decision(self, session_id: str, decision: Dict[str, Any]) -> bool:
        """
        Route Tool Decision to correct hooks.

        Wake waiting SDK callback. Called by API endpoint.

        Args:
            session_id: Session ID
            decision: Decision data, includes request_id, outcome, etc.

        Returns:
            bool: Whether resolution succeeded
        """
        hooks = self._hooks.get(session_id)
        if hooks:
            return hooks.resolve_decision(decision)
        return False

    def resolve_tool_input(self, session_id: str, decision: Dict[str, Any]) -> bool:
        """Preserve legacy user_input routing compatibility entry."""
        return self.resolve_decision(session_id, decision)

    @property
    def active_session_count(self) -> int:
        """Get active session count."""
        return len(self._hooks)

    def has_session(self, session_id: str) -> bool:
        """Check if hooks exist for specified session."""
        return session_id in self._hooks


# Global singleton
global_tool_decision_manager = ToolDecisionManager()


__all__ = [
    "ToolDecisionManager",
    "global_tool_decision_manager",
]
