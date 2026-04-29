
export type AgentSessionEvent =
    | CrudEvent
    | StreamingEvent
    | ThinkingEvent
    | ToolDecisionEvent
    | ToolEvent
    | QueueEvent
    | TaskEvent;

// CRUD events
export type CrudEvent =
    | { type: 'sessions created'; data: any }
    | { type: 'session:init'; data: any }
    | { type: 'sessions patched'; data: any }
    | { type: 'sessions updated'; data: any }
    | { type: 'sessions removed'; data: any }
    | { type: 'tasks created'; data: any }
    | { type: 'tasks patched'; data: any }
    | { type: 'tasks updated'; data: any }
    | { type: 'tasks removed'; data: any }
    | { type: 'messages created'; data: any }
    | { type: 'messages patched'; data: any }
    | { type: 'messages updated'; data: any }
    | { type: 'messages removed'; data: any };

// Streaming events
export type StreamingEvent =
    | { type: 'streaming:start'; session_id: string; task_id?: string; data: { message_id?: string } }
    | { type: 'streaming:chunk'; session_id: string; task_id?: string; data: { message_id?: string; content: string; is_partial: boolean } }
    | { type: 'streaming:end'; session_id: string; task_id?: string; data: { message_id?: string } }
    | { type: 'streaming:error'; session_id: string; task_id?: string; data: { message_id?: string; error: string; code?: string } };

// Thinking events
export type ThinkingEvent =
    | { type: 'thinking:start'; session_id: string; task_id?: string; data: { message_id?: string } }
    | { type: 'thinking:chunk'; session_id: string; task_id?: string; data: { message_id?: string; content: string; is_partial: boolean } }
    | { type: 'thinking:end'; session_id: string; task_id?: string; data: { message_id?: string } };

// Tool Decision events
export type ToolDecisionEvent =
    | { type: 'tool-decision:request'; session_id: string; task_id?: string; data: any }
    | { type: 'tool-decision:approved'; session_id: string; task_id?: string; data: any }
    | { type: 'tool-decision:denied'; session_id: string; task_id?: string; data: any }
    | { type: 'tool-decision:timeout'; session_id: string; task_id?: string; data: any };

// Tool events
export type ToolEvent =
    | { type: 'tool:start'; session_id: string; task_id: string; data: { tool_use_id: string; tool_name: string; tool_input?: Record<string, unknown> } }
    | { type: 'tool:complete'; session_id: string; task_id: string; data: { tool_use_id: string; tool_name: string; result: unknown; is_error?: boolean } }
    | { type: 'tool:error'; session_id: string; task_id: string; data: { tool_use_id: string; tool_name: string; error_message: string; error_code?: string } };

// Queue events
export type QueueEvent =
    | { type: 'messages queued'; session_id: string; data: { message_id: string; queue_position: number; content_canvas?: string } }
    | { type: 'message:dequeued'; session_id: string; data: { message_id: string; queue_position: number; reason: string } }
    | { type: 'queue:processing_failed'; session_id: string; data: { message_id: string; queue_position: number; error_message?: string; error_type?: string; content_preview?: string | null } };

// General task events
export type TaskEvent =
    | { type: 'task:started'; session_id: string; task_id: string; data: any }
    | { type: 'task:completed'; session_id: string; task_id: string; data: any }
    | { type: 'task:failed'; session_id: string; task_id: string; data: any }
    | { type: 'task:stop_ack'; session_id: string; task_id: string; data: any }
    | { type: 'task:stopping'; session_id: string; task_id: string; data: any }
    | { type: 'task:stopped'; session_id: string; task_id: string; data: any };
