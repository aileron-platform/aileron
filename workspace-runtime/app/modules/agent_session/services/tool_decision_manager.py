"""
Tool Decision Manager.

全域 Tool Decision 管理器，參考 agor 的 permission-manager.ts 設計。
將 Tool Decision 決策路由到正確的 session。

職責分離說明：
- ToolDecisionManager（本模組）：全域單例，管理內存中的 DecisionHooks 路由
  - 負責 register/unregister hooks
  - 路由決策到正確的 session callback
  - 不需要資料庫存取

- ToolDecisionService（tool_decision_service.py）：每請求實例，處理資料庫操作
  - 建立/更新決策請求訊息
  - 管理 asyncio 事件的等待/通知
  - 需要資料庫存取

兩者配合工作：API endpoint 調用 ToolDecisionManager 來喚醒 SDK callback，
而 ToolDecisionService 負責持久化狀態到資料庫。
"""

from typing import Any, Dict, Optional, Protocol


class DecisionHooksProtocol(Protocol):
    """DecisionHooks 的協議定義（用於類型檢查）."""

    def resolve_decision(self, decision: Dict[str, Any]) -> bool:
        """解決 Tool Decision."""
        ...


class ToolDecisionManager:
    """
    全域 Tool Decision 管理器.

    職責：
    - register_hooks(): 註冊 session 的 DecisionHooks
    - unregister_hooks(): 取消註冊
    - resolve_decision(): 路由決策到正確的 hooks（喚醒等待中的 SDK callback）
    - get_hooks(): 取得指定 session 的 hooks

    注意：
    - DecisionHooks 處理 SDK callback 的等待/喚醒
    - ToolDecisionService 處理 DB 狀態更新（由 API 單獨調用）
    """

    def __init__(self):
        """初始化 ToolDecisionManager."""
        self._hooks: Dict[str, DecisionHooksProtocol] = {}

    def register_hooks(self, session_id: str, hooks: DecisionHooksProtocol) -> None:
        """
        註冊 session 的 DecisionHooks.

        Args:
            session_id: 會話 ID
            hooks: DecisionHooks 實例
        """
        self._hooks[session_id] = hooks

    def unregister_hooks(self, session_id: str) -> None:
        """
        取消註冊 session 的 DecisionHooks.

        Args:
            session_id: 會話 ID
        """
        if session_id in self._hooks:
            del self._hooks[session_id]

    def get_hooks(self, session_id: str) -> Optional[DecisionHooksProtocol]:
        """
        取得指定 session 的 DecisionHooks.

        Args:
            session_id: 會話 ID

        Returns:
            DecisionHooks 或 None
        """
        return self._hooks.get(session_id)

    def resolve_decision(self, session_id: str, decision: Dict[str, Any]) -> bool:
        """
        路由 Tool Decision 到正確的 hooks.

        喚醒等待中的 SDK callback。由 API endpoint 調用。

        Args:
            session_id: 會話 ID
            decision: 決策資料，包含 request_id, outcome 等

        Returns:
            bool: 是否成功解決
        """
        hooks = self._hooks.get(session_id)
        if hooks:
            return hooks.resolve_decision(decision)
        return False

    def resolve_tool_input(self, session_id: str, decision: Dict[str, Any]) -> bool:
        """保留既有 user_input 路由的相容入口."""
        return self.resolve_decision(session_id, decision)

    @property
    def active_session_count(self) -> int:
        """取得活躍 session 數量."""
        return len(self._hooks)

    def has_session(self, session_id: str) -> bool:
        """檢查是否有指定 session 的 hooks."""
        return session_id in self._hooks


# 全域單例
global_tool_decision_manager = ToolDecisionManager()


__all__ = [
    "ToolDecisionManager",
    "global_tool_decision_manager",
]
