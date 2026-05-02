"""
ITool interface definition.

References agor-main's ITool interface
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.agent_session.domain.enums import PermissionMode

from .streaming_callbacks import StreamingCallbacks
from .types import TaskResult


class ITool(ABC):
    """
    Tool base interface.
    
    Unified interface for all SDK Tools.
    """
    
    @abstractmethod
    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        """
        Execute task (send prompt).

        CONTRACT:
        - Must call messagesService.create() to create complete message
        - Complete message is automatically broadcast via WebSocket
        - If streamingCallbacks provided and supportsStreaming=True, can call callbacks during execution

        STREAMING:
        - If streamingCallbacks provided and supportsStreaming=True:
          - Call on_stream_start() to start generation
          - Call on_stream_chunk() to send 3-10 char chunks
          - Call on_stream_end() to end generation
          - Then create complete message in DB
        - If streamingCallbacks not provided or supportsStreaming=False:
          - Execute synchronously
          - Create complete message in DB
          - User sees loading animation, then sees complete message

        PERMISSION MODE (Claude Code):
        - DEFAULT: Prompt for every tool (strictest)
        - ACCEPT_EDITS: Auto-accept file edits, prompt for other tools
        - BYPASS_PERMISSIONS: Allow all operations (no prompt)
        - PLAN: Plan mode (generate plan but do not execute)

        Args:
            session_id: Session ID
            prompt: User prompt
            task_id: Task ID (for linking messages)
            permission_mode: Permission mode (Claude Code native mode)
            streaming_callbacks: Streaming callbacks (optional)

        Returns:
            TaskResult: Task result (includes message ID)
        """
        raise NotImplementedError("execute_task not implemented")
    
    @abstractmethod
    async def stop_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """
        Stop currently executing task.
        
        Gracefully terminate agent's current execution.
        Implementation varies by SDK:
        - Claude Agent SDK: Call Query object's interrupt()
        - Gemini SDK: Call AbortController's abort()
        - Codex SDK: Set stop flag and interrupt event loop
        
        Args:
            session_id: Session ID
            task_id: Task ID (optional, if multiple tasks executing)
        
        Returns:
            dict: Success status and partial results (if any)
        """
        raise NotImplementedError("stop_task not implemented")
