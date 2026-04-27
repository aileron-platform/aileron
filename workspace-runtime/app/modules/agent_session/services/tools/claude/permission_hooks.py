"""
Permission Hooks for Claude Agent SDK.

Handles can_use_tool callback for custom permission UI via WebSocket.
Based on agor's permission-hooks.ts implementation.

Flow:
1. SDK calls can_use_tool when it needs permission
2. We create a permission request message
3. Emit WebSocket event to frontend
4. Wait for frontend decision
5. Return decision to SDK
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from claude_agent_sdk.types import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    PermissionUpdate,
    ToolPermissionContext,
)

from app.database import async_session_scope


class PermissionHooks:
    """Permission hooks for Claude SDK can_use_tool callback."""

    def __init__(
        self,
        session_id: str,
        task_id: str,
        emit_event: Callable[[str, Dict[str, Any]], None],
        permission_mode: Optional[str] = None,
    ):
        """
        Initialize permission hooks.

        Args:
            session_id: Current session ID
            task_id: Current task ID
            emit_event: Function to emit WebSocket events
            permission_mode: Permission mode (e.g., "bypassPermissions")
        """
        self.session_id = session_id
        self.task_id = task_id
        self.emit_event = emit_event
        self.permission_mode = permission_mode

        # Pending permission requests
        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, Dict[str, Any]] = {}
        self._request_options: Dict[str, list[Dict[str, Any]]] = {}

        # Permission lock to prevent race conditions
        # Ensures only one permission request is processed at a time per session
        self._permission_lock = asyncio.Lock()

    # Tools that require user input instead of permission approval
    USER_INPUT_TOOLS = {"AskUserQuestion"}

    # Default permission options (for Tool Decision)
    DEFAULT_PERMISSION_OPTIONS = [
        {"option_id": "allow_once", "name": "Allow once", "kind": "allow_once", "scope": "once"},
        {"option_id": "allow_session", "name": "Allow for session", "kind": "allow_always", "scope": "session"},
        {"option_id": "reject_once", "name": "Reject", "kind": "reject_once", "scope": "once"},
    ]

    USER_INPUT_OPTIONS = [
        {"option_id": "submit", "name": "Submit", "kind": "allow_once", "scope": "once"},
        {"option_id": "cancel", "name": "Cancel", "kind": "reject_once", "scope": "once"},
    ]

    async def can_use_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResult:
        """
        Handle tool permission request.

        This callback is invoked by the SDK when it needs permission to use a tool.
        Uses a lock to prevent race conditions when multiple permission requests
        occur concurrently in the same session.

        For user input tools like AskUserQuestion, we handle the input directly
        and return a special deny response with the user's answer, bypassing
        the SDK's internal tool execution which may fail in Docker environments.

        Args:
            tool_name: Name of the tool being used
            tool_input: Input parameters for the tool
            context: Permission context with signal and suggestions

        Returns:
            PermissionResult: Allow or Deny decision
        """
        # Use lock to serialize permission requests and prevent race conditions
        logger.info(
            "can_use_tool called: tool=%s, session=%s, permission_mode=%s",
            tool_name, self.session_id[:8], self.permission_mode,
        )
        async with self._permission_lock:
            # Special handling for user input tools (always requires user interaction)
            if tool_name in self.USER_INPUT_TOOLS:
                return await self._process_user_input_request(tool_name, tool_input, context)
            # In BYPASS_PERMISSIONS or DONT_ASK mode, auto-approve non-user-input tools
            if self.permission_mode in ("bypassPermissions", "dontAsk"):
                return PermissionResultAllow(behavior="allow")
            return await self._process_permission_request(tool_name, tool_input, context)

    async def _process_user_input_request(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResult:
        """
        Process user input tools like AskUserQuestion.

        Collects user input via WebSocket UI and returns PermissionResultAllow
        with updated_input containing the user's answers, following the
        Claude Agent SDK specification.

        Args:
            tool_name: Name of the tool (e.g., AskUserQuestion)
            tool_input: Tool input containing questions
            context: Permission context

        Returns:
            PermissionResultAllow with updated_input containing answers,
            or PermissionResultDeny if cancelled/error
        """
        request_id = str(uuid.uuid4())
        timestamp = utcnow().isoformat()
        tool_use_id = getattr(context, 'tool_use_id', None)

        # Check for abort signal
        signal = getattr(context, 'signal', None)
        if signal and getattr(signal, 'aborted', False):
            return PermissionResultDeny(
                behavior="deny",
                message="Request cancelled",
            )

        try:
            # Step 1: Update task status to awaiting_user_input
            await self._set_awaiting_permission({
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "type": "user_input",
                "tool_use_id": tool_use_id,  # For replaying events on reconnection
            })

            # Step 2: Emit WebSocket event for tool decision (user_input)
            options = [dict(option) for option in self.USER_INPUT_OPTIONS]
            self._request_options[request_id] = options
            tool_call = {
                "toolCallId": tool_use_id or request_id,
                "title": tool_name,
                "kind": "execute",
                "rawInput": tool_input,
            }
            await self._create_permission_message(
                request_id=request_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id,
                decision_type="user_input",
                options=options,
                raw_tool_call=tool_call,
                tool_call_id=tool_use_id or request_id,
            )

            self.emit_event("tool-decision:request", {
                "request_id": request_id,
                "session_id": self.session_id,
                "task_id": self.task_id,
                "decision_type": "user_input",
                "options": options,
                "tool_call": tool_call,
                "timeout": 300,  # 5 minutes for user input
                "timestamp": timestamp,
            })

            # Step 3: Wait for user input (using same mechanism as permission)
            result = await self._wait_for_decision(request_id, timeout=300, signal=signal)

            # Step 4: Resume task
            await self._resume_from_permission()

            # Step 5: Check if user cancelled
            outcome = result.get("outcome")
            if outcome == "cancelled":
                return PermissionResultDeny(
                    behavior="deny",
                    message="User cancelled the input request",
                )

            # Step 6: Build updated_input per SDK spec and return Allow
            user_answer = result.get("content", result.get("answer", result.get("reason", "")))
            updated_input = self._build_ask_user_question_input(tool_name, tool_input, user_answer)

            return PermissionResultAllow(
                behavior="allow",
                updated_input=updated_input,
            )

        except asyncio.TimeoutError:
            await self._handle_timeout(request_id)
            return PermissionResultDeny(
                behavior="deny",
                message=f"User input request timed out for {tool_name}",
            )
        except Exception as e:
            return PermissionResultDeny(
                behavior="deny",
                message=f"Error getting user input: {str(e)}",
            )
        finally:
            self._request_options.pop(request_id, None)

    def _build_ask_user_question_input(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        user_answer: str,
    ) -> Dict[str, Any]:
        """
        Build updated_input for AskUserQuestion per SDK spec.

        Parses user answer and maps q0/q1 keys to full question text,
        returning the format expected by Claude Agent SDK:
        {"questions": [...], "answers": {"full question text": "answer"}}

        Args:
            tool_name: Name of the tool
            tool_input: Original tool input containing questions
            user_answer: User's answer (format: "q0: answer1\\nq1: answer2" or JSON)

        Returns:
            Dict for PermissionResultAllow.updated_input
        """
        if tool_name != "AskUserQuestion":
            return {"answer": user_answer}

        questions = tool_input.get("questions", [])

        # Parse user_answer into raw key-value pairs
        raw_answers: Dict[str, str] = {}
        try:
            parsed = json.loads(user_answer)
            if isinstance(parsed, dict):
                raw_answers = parsed
        except (json.JSONDecodeError, TypeError):
            # Parse "q0: answer\nq1: answer" format (newline-separated)
            for line in user_answer.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if ": " in line:
                    key, value = line.split(": ", 1)
                    raw_answers[key.strip()] = value.strip()
                else:
                    raw_answers["q0"] = line.strip()

        # Map q0/q1 keys to full question text per SDK spec
        mapped_answers: Dict[str, str] = {}
        for key, value in raw_answers.items():
            if key.startswith("q") and key[1:].isdigit():
                idx = int(key[1:])
                if idx < len(questions):
                    question_text = questions[idx].get("question", key)
                    mapped_answers[question_text] = value
                else:
                    mapped_answers[key] = value
            else:
                # Already a full question text or other key
                mapped_answers[key] = value

        return {
            "questions": questions,
            "answers": mapped_answers,
        }

    async def _process_permission_request(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResult:
        """
        Internal method to process permission request.

        This method is called within the permission lock to ensure
        only one request is processed at a time. Supports cancellation
        via context.signal (AbortSignal pattern from agor).
        """
        request_id = str(uuid.uuid4())
        timestamp = utcnow().isoformat()

        # Get tool_use_id from context if available
        tool_use_id = getattr(context, 'tool_use_id', None)

        # Extract SDK permission suggestions (PermissionUpdate[])
        sdk_suggestions = getattr(context, 'suggestions', None)

        # Check for abort signal (if supported by SDK)
        signal = getattr(context, 'signal', None)
        if signal and getattr(signal, 'aborted', False):
            return PermissionResultDeny(
                behavior="deny",
                message="Request cancelled",
            )

        try:
            # Step 1: Create permission request message (Tool Decision)
            options = [dict(option) for option in self.DEFAULT_PERMISSION_OPTIONS]
            self._request_options[request_id] = options
            tool_call = {
                "toolCallId": tool_use_id or request_id,
                "title": tool_name,
                "kind": "execute",
                "rawInput": tool_input,
            }
            await self._create_permission_message(
                request_id=request_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id,
                decision_type="permission",
                options=options,
                raw_tool_call=tool_call,
                tool_call_id=tool_use_id or request_id,
            )

            # Step 2: Update task and session status to awaiting_permission
            await self._set_awaiting_permission(
                {
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "type": "permission",  # For replaying events on reconnection
                    "tool_use_id": tool_use_id,  # For replaying events on reconnection
                },
            )

            # Step 3: Emit WebSocket event (include SDK suggestions for frontend)
            event_data = {
                "request_id": request_id,
                "session_id": self.session_id,
                "task_id": self.task_id,
                "decision_type": "permission",
                "options": options,
                "tool_call": tool_call,
                "timeout": 60,
                "timestamp": timestamp,
            }
            # Pass SDK permission suggestions to frontend if available
            if sdk_suggestions:
                event_data["suggestions"] = self._serialize_suggestions(sdk_suggestions)
            self.emit_event("tool-decision:request", event_data)

            # Step 4: Wait for decision (with abort signal support)
            # Note: DB state updates are handled by API layer's tool_decision_service.resolve_decision()
            # PermissionHooks is only responsible for waiting for decision and returning result to SDK
            decision = await self._wait_for_decision(request_id, timeout=60, signal=signal)

            # Step 5: Return decision to SDK
            allow, resolved_scope = self._resolve_permission_decision(decision, request_id)
            if allow:
                # Build response with updatedPermissions if scope is set
                response = PermissionResultAllow(
                    behavior="allow",
                    updated_input=tool_input,
                )

                # Add permission update if user chose to remember
                # Note: "once" and "session" scopes don't persist to settings files
                # - once: applies only to this single request
                # - session: applies during current session but not persisted
                scope = decision.get("scope") or resolved_scope
                if scope and scope not in ("once", "session"):
                    destination_map = {
                        "project": "projectSettings",
                        "user": "userSettings",
                        "local": "localSettings",
                    }
                    destination = destination_map.get(scope)
                    if destination:
                        response.updated_permissions = [
                            PermissionUpdate(
                                type="addRules",
                                rules=[{"tool_name": tool_name}],
                                behavior="allow",
                                destination=destination,
                            )
                        ]

                return response
            else:
                # Note: DB state updates are handled by API layer's tool_decision_service.resolve_decision()
                return PermissionResultDeny(
                    behavior="deny",
                    message=decision.get("reason", f"Permission denied for: {tool_name}"),
                )

        except asyncio.TimeoutError:
            # In timeout case, need to update DB because API won't be called
            await self._handle_timeout(request_id)
            return PermissionResultDeny(
                behavior="deny",
                message=f"Permission request timed out for: {tool_name}",
            )
        except Exception as e:
            return PermissionResultDeny(
                behavior="deny",
                message=f"Error in permission flow: {str(e)}",
            )
        finally:
            self._request_options.pop(request_id, None)

    async def _create_permission_message(
        self,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str],
        decision_type: str,
        options: list[Dict[str, Any]],
        raw_tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> None:
        """Create permission request message.

        Uses a separate database session to avoid 'another operation in progress' errors
        when multiple async operations share the same connection.
        """
        # Import here to avoid circular imports
        from app.modules.agent_session.services.message_service import MessageService

        async with async_session_scope() as db:
            message_service = MessageService(db)
            await message_service.create_permission_request(
                session_id=self.session_id,
                task_id=self.task_id,
                request_id=request_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id,
                decision_type=decision_type,
                options=options,
                raw_tool_call=raw_tool_call,
                tool_call_id=tool_call_id,
            )

    async def _set_awaiting_permission(
        self,
        permission_request: Dict[str, Any],
    ) -> None:
        """Set task to awaiting_permission status.

        Uses a separate database session to avoid 'another operation in progress' errors.
        """
        from app.modules.agent_session.services.task_service import TaskService

        async with async_session_scope() as db:
            task_service = TaskService(db)
            await task_service.set_awaiting_permission(self.task_id, permission_request)

    async def _resume_from_permission(self) -> None:
        """Resume task from permission.

        Uses a separate database session to avoid 'another operation in progress' errors.
        """
        from app.modules.agent_session.services.task_service import TaskService

        async with async_session_scope() as db:
            task_service = TaskService(db)
            await task_service.resume_from_permission(self.task_id)

    async def _fail_task(self, error_message: str) -> None:
        """Fail task with error message.

        Uses a separate database session to avoid 'another operation in progress' errors.
        """
        from app.modules.agent_session.services.task_service import TaskService

        async with async_session_scope() as db:
            task_service = TaskService(db)
            await task_service.fail_task(self.task_id, error_message=error_message)

    async def _wait_for_decision(
        self,
        request_id: str,
        timeout: int = 60,
        signal: Any = None,
    ) -> Dict[str, Any]:
        """Wait for permission decision from frontend.

        Supports cancellation via signal (AbortSignal pattern).

        Args:
            request_id: The permission request ID
            timeout: Timeout in seconds
            signal: Optional abort signal for cancellation

        Returns:
            Decision dict with allow, scope, etc.
        """
        event = asyncio.Event()
        self._pending_decisions[request_id] = event

        # Create cancel event for signal handling
        cancel_event = asyncio.Event()

        def on_abort():
            cancel_event.set()

        # Register abort listener if signal is provided
        if signal is not None:
            add_listener = getattr(signal, 'add_abort_listener', None) or getattr(signal, 'addEventListener', None)
            if callable(add_listener):
                try:
                    add_listener(on_abort)
                except TypeError:
                    try:
                        add_listener('abort', on_abort)
                    except TypeError:
                        pass  # Signal API incompatible, abort won't cancel permission wait

        try:
            # Wait for either decision or cancellation
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(event.wait()),
                    asyncio.create_task(cancel_event.wait()),
                ],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Check if cancelled
            if cancel_event.is_set():
                return {"allow": False, "reason": "Cancelled", "decided_by": "system"}

            # Check if timeout (no tasks completed)
            if not done:
                raise asyncio.TimeoutError()

            # Return decision
            decision = self._decision_results.get(request_id, {"allow": False})
            return decision
        finally:
            self._pending_decisions.pop(request_id, None)
            self._decision_results.pop(request_id, None)

            # Unregister abort listener
            if signal is not None:
                remove_listener = getattr(signal, 'remove_abort_listener', None) or getattr(signal, 'removeEventListener', None)
                if callable(remove_listener):
                    try:
                        remove_listener(on_abort)
                    except TypeError:
                        try:
                            remove_listener('abort', on_abort)
                        except TypeError:
                            pass  # Ignore if incompatible

    def resolve_decision(self, decision: Dict[str, Any]) -> bool:
        """
        Resolve a pending permission decision.

        Called from the API endpoint when user makes a decision.

        Args:
            decision: Decision dict with request_id, allow, scope, etc.

        Returns:
            True if decision was resolved, False if no pending request found
        """
        request_id = decision.get("request_id")
        if not request_id:
            return False

        event = self._pending_decisions.get(request_id)
        if not event:
            return False

        self._decision_results[request_id] = decision
        event.set()
        return True

    @staticmethod
    def _serialize_suggestions(suggestions: list) -> list:
        """Serialize SDK PermissionUpdate suggestions for WebSocket transport."""
        serialized = []
        for s in suggestions:
            try:
                item = {}
                if hasattr(s, 'type'):
                    item["type"] = s.type
                if hasattr(s, 'rules'):
                    item["rules"] = s.rules
                if hasattr(s, 'behavior'):
                    item["behavior"] = s.behavior
                if hasattr(s, 'destination'):
                    item["destination"] = s.destination
                # Fallback: if it's already a dict
                if isinstance(s, dict):
                    item = s
                serialized.append(item)
            except Exception:
                pass
        return serialized

    def _resolve_permission_decision(
        self,
        decision: Dict[str, Any],
        request_id: str,
    ) -> tuple[bool, Optional[str]]:
        """Resolve Tool Decision to allow/scope."""
        if "allow" in decision:
            return bool(decision.get("allow")), decision.get("scope")

        outcome = decision.get("outcome")
        option_id = decision.get("option_id")
        scope = decision.get("scope")

        allow = outcome != "cancelled"

        if option_id:
            options = self._request_options.get(request_id, [])
            for option in options:
                if option.get("option_id") == option_id or option.get("optionId") == option_id:
                    kind = option.get("kind", "")
                    if kind.startswith("reject"):
                        allow = False
                    elif kind.startswith("allow"):
                        allow = True
                    if scope is None:
                        scope = option.get("scope")
                    break

        if outcome == "cancelled":
            allow = False

        return allow, scope

    async def _handle_timeout(self, request_id: str) -> None:
        """Handle permission request timeout."""
        # Emit timeout event
        self.emit_event("tool-decision:timeout", {
            "request_id": request_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
        })

        # Update task status (also updates session status to IDLE internally)
        await self._fail_task("Permission request timed out")


# Note: Global registry has been moved to PermissionManager
# PermissionHooks instances are managed by ClaudeTool during execute_task
# And registered via global_tool_decision_manager.register_hooks/unregister_hooks
