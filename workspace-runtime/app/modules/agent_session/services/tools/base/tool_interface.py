"""
ITool 介面定義.

比照 agor-main 的 ITool interface
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.agent_session.domain.enums import PermissionMode

from .streaming_callbacks import StreamingCallbacks
from .types import TaskResult, ToolCapabilities, ToolType


class ITool(ABC):
    """
    Tool 基礎介面.
    
    所有 SDK Tool 的統一介面。
    """
    
    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Tool 類型識別碼."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """人類可讀的 Tool 名稱."""
        ...
    
    @abstractmethod
    def get_capabilities(self) -> ToolCapabilities:
        """
        取得 Tool 能力標記.
        
        Returns:
            ToolCapabilities: 能力標記
        """
        ...
    
    @abstractmethod
    async def check_installed(self) -> bool:
        """
        檢查 Tool 是否已安裝且可存取.
        
        Returns:
            bool: 是否已安裝
        """
        ...
    
    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        """
        執行任務（發送 prompt）.

        CONTRACT:
        - 必須呼叫 messagesService.create() 建立完整訊息
        - 完整訊息會自動透過 WebSocket 廣播
        - 如果提供 streamingCallbacks 且 supportsStreaming=True，可在執行期間呼叫回調

        STREAMING:
        - 如果提供 streamingCallbacks 且 supportsStreaming=True:
          - 呼叫 on_stream_start() 開始生成
          - 呼叫 on_stream_chunk() 傳送 3-10 字片段
          - 呼叫 on_stream_end() 結束生成
          - 然後在 DB 建立完整訊息
        - 如果未提供 streamingCallbacks 或 supportsStreaming=False:
          - 同步執行
          - 在 DB 建立完整訊息
          - 使用者看到載入動畫，然後看到完整訊息

        PERMISSION MODE (Claude Code):
        - DEFAULT: 每個工具都提示（最嚴格）
        - ACCEPT_EDITS: 自動接受檔案編輯，其他工具提示
        - BYPASS_PERMISSIONS: 允許所有操作（不提示）
        - PLAN: 計劃模式（生成計劃但不執行）

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            task_id: 任務 ID（用於連結訊息）
            permission_mode: 權限模式（Claude Code 原生模式）
            streaming_callbacks: 串流回調（可選）

        Returns:
            TaskResult: 任務結果（包含訊息 ID）
        """
        raise NotImplementedError("execute_task not implemented")
    
    async def stop_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """
        停止目前執行的任務.
        
        優雅地終止 agent 的目前執行。
        實作方式因 SDK 而異：
        - Claude Agent SDK: 呼叫 Query 物件的 interrupt()
        - Gemini SDK: 呼叫 AbortController 的 abort()
        - Codex SDK: 設定停止標記並中斷事件循環
        
        Args:
            session_id: 會話 ID
            task_id: 任務 ID（可選，如果有多個任務執行）
        
        Returns:
            dict: 成功狀態和部分結果（如果有）
        """
        raise NotImplementedError("stop_task not implemented")

