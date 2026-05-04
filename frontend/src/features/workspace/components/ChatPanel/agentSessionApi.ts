/**
 * Agent Session API Client
 *
 * 提供多 Agent CLI 工具對話系統的 API 呼叫
 */

import { ApiClient } from '@/shared/api/apiClient';
import type {
  AgentSession,
  AgentTask,
  AgentMessage,
  AgenticTool,
  SessionStatus,
  TaskStatus,
  MessageType,
  MessageRole,
  SessionCreateRequest,
  SessionUpdateRequest,
  SessionListResponse,
  TaskCreateRequest,
  TaskListResponse,
  MessageCreateRequest,
  MessageListResponse,
  ToolDecisionRequest,
  PromptRequest,
  PromptResponse,
  ToolCapabilities,
  PermissionConfig,
} from './agentSessionTypes';
import { isGeminiSessionPermissionMode } from './agentSessionTypes';

/**
 * 創建帶認證的 Runtime API Client
 */
function createRuntimeClient(runtimeBaseUrl: string): ApiClient {
  // 在測試環境下添加內部測試 token
  const headers: Record<string, string> = {};
  if (import.meta.env.DEV || window.location.pathname.includes('/test/')) {
    headers['X-Internal-Token'] = 'test-internal-token';
  }
  return new ApiClient({
    baseUrl: runtimeBaseUrl,
    headers: Object.keys(headers).length > 0 ? headers : undefined
  });
}

const normalizePermissionConfig = (permissionConfig: any): PermissionConfig | null => {
  if (!permissionConfig || typeof permissionConfig !== 'object') {
    return null;
  }

  return {
    mode: permissionConfig.mode,
    codex: permissionConfig.codex,
    gemini: isGeminiSessionPermissionMode(permissionConfig.gemini)
      ? permissionConfig.gemini
      : undefined,
    geminiSpawnedWith: isGeminiSessionPermissionMode(permissionConfig.gemini_spawned_with)
      ? permissionConfig.gemini_spawned_with
      : undefined,
  };
};

const normalizeSessionResponse = (session: any): AgentSession => {
  const normalizedSessionId = session?.session_id;
  return {
    ...session,
    session_id: normalizedSessionId,
    permission_config: normalizePermissionConfig(session?.permission_config),
  } as AgentSession;
};

const normalizeTaskResponse = (task: any): AgentTask => {
  return {
    ...task,
    task_id: task?.task_id ?? task?.id,
  } as AgentTask;
};

// ============================================================================
// Session API
// ============================================================================

export const agentSessionApi = {
  /**
   * 建立會話
   */
  async createSession(
    runtimeBaseUrl: string,
    data: SessionCreateRequest
  ): Promise<AgentSession> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.post<any>('/api/v1/agent-sessions', data);
    return normalizeSessionResponse(response);
  },

  /**
   * 取得會話
   */
  async getSession(
    runtimeBaseUrl: string,
    sessionId: string
  ): Promise<AgentSession> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.get<any>(`/api/v1/agent-sessions/${sessionId}`);
    return normalizeSessionResponse(response);
  },

  /**
   * 查詢會話列表
   */
  async listSessions(
    runtimeBaseUrl: string,
    params: {
      workspace_id?: string;
      status?: SessionStatus;
      agentic_tool?: AgenticTool;
      source?: string;
      archived?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<SessionListResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const queryParams = new URLSearchParams();

    if (params.workspace_id) queryParams.set('workspace_id', params.workspace_id);
    if (params.status) queryParams.set('status', params.status);
    if (params.agentic_tool) queryParams.set('agentic_tool', params.agentic_tool);
    if (params.source) queryParams.set('source', params.source);
    if (params.archived !== undefined) queryParams.set('archived', String(params.archived));
    if (params.limit) queryParams.set('limit', String(params.limit));
    if (params.offset) queryParams.set('offset', String(params.offset));

    const queryString = queryParams.toString();
    const url = queryString ? `/api/v1/agent-sessions?${queryString}` : '/api/v1/agent-sessions';
    const response = await client.get<any>(url);
    return {
      ...response,
      items: response.items?.map((item: any) => normalizeSessionResponse(item)) || []
    };
  },

  /**
   * 更新會話
   */
  async updateSession(
    runtimeBaseUrl: string,
    sessionId: string,
    data: SessionUpdateRequest
  ): Promise<AgentSession> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.patch<any>(`/api/v1/agent-sessions/${sessionId}`, data);
    return normalizeSessionResponse(response);
  },

  /**
   * 刪除會話
   */
  async deleteSession(
    runtimeBaseUrl: string,
    sessionId: string
  ): Promise<void> {
    const client = createRuntimeClient(runtimeBaseUrl);
    await client.delete(`/api/v1/agent-sessions/${sessionId}`);
  },

  /**
   * 封存會話
   */
  async archiveSession(
    runtimeBaseUrl: string,
    sessionId: string,
    reason: string = 'manual'
  ): Promise<AgentSession> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.post<any>(
      `/api/v1/agent-sessions/${sessionId}/archive?reason=${encodeURIComponent(reason)}`
    );
    return normalizeSessionResponse(response);
  },

  /**
   * 執行 Prompt
   */
  async executePrompt(
    runtimeBaseUrl: string,
    sessionId: string,
    data: PromptRequest
  ): Promise<PromptResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.post<PromptResponse>(
      `/api/v1/agent-sessions/${sessionId}/prompt`,
      data
    );
  },

  /**
   * 處理工具決策
   */
  async submitToolDecision(
    runtimeBaseUrl: string,
    sessionId: string,
    decision: ToolDecisionRequest
  ): Promise<{ success: boolean }> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.post<{ success: boolean }>(
      `/api/v1/agent-sessions/${sessionId}/tool-decision`,
      decision
    );
  },

  /**
   * 取得當前執行狀態
   */
  async getCurrentExecution(
    runtimeBaseUrl: string,
    sessionId: string
  ): Promise<{
    has_active_execution: boolean;
    session_id?: string;
    task_id?: string;
    agentic_tool?: AgenticTool;
    started_at?: string | null;
  }> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.get<{
      has_active_execution: boolean;
      session_id?: string;
      task_id?: string;
      agentic_tool?: AgenticTool;
      started_at?: string | null;
    }>(
      `/api/v1/agent-sessions/${sessionId}/current-execution`
    );
  },

  /**
   * 取得佇列訊息
   */
  async getQueuedMessages(
    runtimeBaseUrl: string,
    sessionId: string
  ): Promise<{
    session_id: string;
    count: number;
    max_queue_size: number;
      messages: Array<{
        message_id: string;
        queue_position: number;
        content_preview: string;
        created_at: string | null;
        status?: 'queued' | 'dispatching' | null;
      }>;
  }> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.get<{
      session_id: string;
      count: number;
      max_queue_size: number;
      messages: Array<{
        message_id: string;
        queue_position: number;
        content_preview: string;
        created_at: string | null;
        status?: 'queued' | 'dispatching' | null;
      }>;
    }>(`/api/v1/agent-sessions/${sessionId}/queued-messages`);
  },

  /**
   * 刪除佇列訊息
   */
  async deleteQueuedMessage(
    runtimeBaseUrl: string,
    sessionId: string,
    messageId: string
  ): Promise<void> {
    const client = createRuntimeClient(runtimeBaseUrl);
    await client.delete(`/api/v1/agent-sessions/${sessionId}/messages/${messageId}`);
  },
};

// ============================================================================
// Task API
// ============================================================================

export const agentTaskApi = {
  /**
   * 建立任務
   */
  async createTask(
    runtimeBaseUrl: string,
    sessionId: string,
    data: TaskCreateRequest
  ): Promise<AgentTask> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.post<any>(`/api/v1/agent-sessions/${sessionId}/tasks`, data);
    return normalizeTaskResponse(response);
  },

  /**
   * 取得任務
   */
  async getTask(
    runtimeBaseUrl: string,
    sessionId: string,
    taskId: string
  ): Promise<AgentTask> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const response = await client.get<any>(`/api/v1/agent-sessions/${sessionId}/tasks/${taskId}`);
    return normalizeTaskResponse(response);
  },

  /**
   * 查詢任務列表
   */
  async listTasks(
    runtimeBaseUrl: string,
    sessionId: string,
    params: {
      status?: TaskStatus;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<TaskListResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const queryParams = new URLSearchParams();

    if (params.status) queryParams.set('status', params.status);
    if (params.limit) queryParams.set('limit', String(params.limit));
    if (params.offset) queryParams.set('offset', String(params.offset));

    const queryString = queryParams.toString();
    const url = queryString 
      ? `/api/v1/agent-sessions/${sessionId}/tasks?${queryString}` 
      : `/api/v1/agent-sessions/${sessionId}/tasks`;
    const response = await client.get<any>(url);
    return {
      ...response,
      items: response.items?.map((item: any) => normalizeTaskResponse(item)) || [],
    } as TaskListResponse;
  },

  /**
   * 停止任務
   */
  async stopTask(
    runtimeBaseUrl: string,
    sessionId: string,
    taskId: string
  ): Promise<{ success: boolean; task_id: string; status: TaskStatus }> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.post<{ success: boolean; task_id: string; status: TaskStatus }>(
      `/api/v1/agent-sessions/${sessionId}/tasks/${taskId}/stop`
    );
  },
};

// ============================================================================
// Message API
// ============================================================================

export const agentMessageApi = {
  /**
   * 建立訊息
   */
  async createMessage(
    runtimeBaseUrl: string,
    sessionId: string,
    data: MessageCreateRequest
  ): Promise<AgentMessage> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.post<AgentMessage>(`/api/v1/agent-sessions/${sessionId}/messages`, data);
  },

  /**
   * 取得訊息
   */
  async getMessage(
    runtimeBaseUrl: string,
    sessionId: string,
    messageId: string
  ): Promise<AgentMessage> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.get<AgentMessage>(`/api/v1/agent-sessions/${sessionId}/messages/${messageId}`);
  },

  /**
   * 查詢訊息列表
   */
  async listMessages(
    runtimeBaseUrl: string,
    sessionId: string,
    params: {
      task_id?: string;
      type?: MessageType;
      role?: MessageRole;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<MessageListResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const queryParams = new URLSearchParams();

    if (params.task_id) queryParams.set('task_id', params.task_id);
    if (params.type) queryParams.set('type', params.type);
    if (params.role) queryParams.set('role', params.role);
    if (params.limit) queryParams.set('limit', String(params.limit));
    if (params.offset) queryParams.set('offset', String(params.offset));

    const queryString = queryParams.toString();
    const url = queryString
      ? `/api/v1/agent-sessions/${sessionId}/messages?${queryString}`
      : `/api/v1/agent-sessions/${sessionId}/messages`;
    const response = await client.get<MessageListResponse>(url);
    return response;
  },

  /**
   * 批次建立訊息
   */
  async createMessagesBulk(
    runtimeBaseUrl: string,
    sessionId: string,
    messages: MessageCreateRequest[]
  ): Promise<{ success: boolean; created_count: number; messages: AgentMessage[] }> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return await client.post<{ success: boolean; created_count: number; messages: AgentMessage[] }>(
      `/api/v1/agent-sessions/${sessionId}/messages/bulk`,
      { messages }
    );
  },

  // NOTE: Queue API 已整合至 agentSessionApi
  // - getQueuedMessages: 取得佇列訊息
  // - deleteQueuedMessage: 刪除佇列訊息
  // - 佇列訊息透過 executePrompt 自動建立
};

// 導出所有 API
export const agentApi = {
  sessions: agentSessionApi,
  tasks: agentTaskApi,
  messages: agentMessageApi,
};

export type AgentApi = typeof agentApi;
