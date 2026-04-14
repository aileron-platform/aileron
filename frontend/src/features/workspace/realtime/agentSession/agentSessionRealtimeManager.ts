/**
 * Agent Session Realtime Manager
 *
 * 管理 Agent Session WebSocket 連接，處理事件分發
 */

import { WebSocketConnectionRegistry, ManagedSocketStatus } from '../core/websocketRegistry';
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';
import { getAgentSessionStore } from '../../components/ChatPanel/agentSessionStore';
import type { WebSocketEvent } from '../../components/ChatPanel/agentSessionTypes';
import { createLogger } from '@/shared/services/logger';
import { toWebSocketUrl } from '../../services/workspacePublicUrl';

const logger = createLogger('AgentSessionRealtimeManager');

export type AgentSessionWebSocketType = 'agent-session';

interface AgentSessionRealtimeManagerOptions {
  heartbeatInterval?: number;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
}

const DEFAULT_OPTIONS: Required<AgentSessionRealtimeManagerOptions> = {
  heartbeatInterval: 30000, // 30 seconds
  reconnectDelay: 3000,     // 3 seconds
  maxReconnectAttempts: 10,
};

export class AgentSessionRealtimeManager {
  private registry: WebSocketConnectionRegistry;
  private options: Required<AgentSessionRealtimeManagerOptions>;
  private workspaceId: string | null = null;
  private runtimeBaseUrl: string | null = null;
  private currentSessionId: string | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;

  constructor(
    registry: WebSocketConnectionRegistry,
    options: AgentSessionRealtimeManagerOptions = {}
  ) {
    this.registry = registry;
    this.options = { ...DEFAULT_OPTIONS, ...options };
  }

  /**
   * 更新 workspace 資訊
   */
  updateWorkspace(workspaceId: string | null, runtimeBaseUrl: string | null): void {
    logger.debug(' updateWorkspace', { workspaceId, runtimeBaseUrl });

    // 如果 workspace 變了，斷開現有連接
    if (this.workspaceId !== workspaceId || this.runtimeBaseUrl !== runtimeBaseUrl) {
      this.disconnect();
    }

    this.workspaceId = workspaceId;
    this.runtimeBaseUrl = runtimeBaseUrl;
  }

  /**
   * 連接到 WebSocket
   */
  connect(sessionId?: string): void {
    if (this.disposed || !this.runtimeBaseUrl) {
      logger.warn(' Cannot connect: disposed or no runtimeBaseUrl');
      return;
    }

    const managed = this.registry.ensure('agent-session' as any);

    // 如果已連接，不重複連接
    if (managed.socket && managed.status === 'open') {
      // 如果提供了新的 sessionId，訂閱它
      if (sessionId && sessionId !== this.currentSessionId) {
        this.subscribeSession(sessionId);
      }
      return;
    }

    this.registry.updateStatus('agent-session' as any, 'connecting');
    getAgentSessionStore().setConnectionStatus('connecting');

    // 構建 WebSocket URL
    const wsUrl = this.buildWebSocketUrl(sessionId);
    logger.debug(' Connecting to:', wsUrl);

    try {
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => this.handleOpen(socket, sessionId);
      socket.onmessage = (event) => this.handleMessage(event);
      socket.onerror = (error) => this.handleError(error);
      socket.onclose = (event) => this.handleClose(event);

      this.registry.setSocket('agent-session' as any, socket, 'connecting');
    } catch (error) {
      logger.error(' Failed to create WebSocket:', error);
      this.scheduleReconnect(sessionId);
    }
  }

  /**
   * 斷開連接
   */
  disconnect(): void {
    this.clearTimers();
    this.registry.close('agent-session' as any);
    this.currentSessionId = null;
    getAgentSessionStore().setConnectionStatus('idle');
  }

  /**
   * 訂閱 session
   */
  subscribeSession(sessionId: string): void {
    const managed = this.registry.get('agent-session' as any);
    if (!managed.socket || managed.status !== 'open') {
      // 如果未連接，連接並訂閱
      this.connect(sessionId);
      return;
    }

    logger.debug(' Subscribing to session:', sessionId);
    this.currentSessionId = sessionId;

    managed.socket.send(JSON.stringify({
      type: 'subscribe',
      session_id: sessionId,
    }));
  }

  /**
   * 取消訂閱 session
   */
  unsubscribeSession(sessionId: string): void {
    const managed = this.registry.get('agent-session' as any);
    if (!managed.socket || managed.status !== 'open') {
      return;
    }

    logger.debug(' Unsubscribing from session:', sessionId);

    managed.socket.send(JSON.stringify({
      type: 'unsubscribe',
      session_id: sessionId,
    }));

    if (this.currentSessionId === sessionId) {
      this.currentSessionId = null;
    }
  }

  /**
   * 釋放資源
   */
  dispose(): void {
    this.disposed = true;
    this.disconnect();
  }

  // ============================================================================
  // Private Methods
  // ============================================================================

  private buildWebSocketUrl(sessionId?: string): string {
    if (sessionId) {
      return toWebSocketUrl(this.runtimeBaseUrl!, `/api/v1/ws/agent-sessions/${sessionId}`);
    }
    return toWebSocketUrl(this.runtimeBaseUrl!, '/api/v1/ws');
  }

  private handleOpen(socket: WebSocket, sessionId?: string): void {
    logger.debug(' Connected');
    this.registry.setSocket('agent-session' as any, socket, 'open');
    this.registry.resetAttempts('agent-session' as any);
    getAgentSessionStore().setConnectionStatus('open');

    if (sessionId) {
      this.currentSessionId = sessionId;
    }

    // 開始心跳
    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as WebSocketEvent | { type: string;[key: string]: unknown };

      // 處理 pong 響應
      if (data.type === 'pong') {
        return;
      }

      // 處理訂閱確認
      if (data.type === 'subscribed') {
        logger.debug(' Subscribed to session:', data.session_id);
        return;
      }

      // 處理取消訂閱確認
      if (data.type === 'unsubscribed') {
        logger.debug(' Unsubscribed from session:', data.session_id);
        return;
      }

      // 處理錯誤
      if (data.type === 'error') {
        logger.error(' Server error:', data.message);
        return;
      }

      // 分發事件到 dispatcher
      const dispatcher = getEventDispatcher();
      dispatcher.dispatch(data as WebSocketEvent);
    } catch (error) {
      logger.error(' Failed to parse message:', error);
    }
  }

  private handleError(error: Event): void {
    logger.error(' WebSocket error:', error);
    getAgentSessionStore().setConnectionStatus('error', 'WebSocket error');
  }

  private handleClose(event: CloseEvent): void {
    logger.debug(' Disconnected:', event.code, event.reason);
    this.clearTimers();
    this.registry.setSocket('agent-session' as any, null, 'closed');

    if (!this.disposed && event.code !== 1000) {
      // 非正常關閉，嘗試重連
      this.scheduleReconnect(this.currentSessionId || undefined);
    } else {
      getAgentSessionStore().setConnectionStatus('idle');
    }
  }

  private startHeartbeat(): void {
    this.clearHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      const managed = this.registry.get('agent-session' as any);
      if (managed.socket && managed.status === 'open') {
        managed.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, this.options.heartbeatInterval);
  }

  private clearHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(sessionId?: string): void {
    if (this.disposed) return;

    const managed = this.registry.get('agent-session' as any);
    if (managed.reconnectAttempts >= this.options.maxReconnectAttempts) {
      logger.error(' Max reconnect attempts reached');
      getAgentSessionStore().setConnectionStatus('error', 'Max reconnect attempts reached');
      return;
    }

    this.registry.incrementAttempts('agent-session' as any);
    this.registry.updateStatus('agent-session' as any, 'reconnecting');
    getAgentSessionStore().setConnectionStatus('connecting');

    const delay = this.options.reconnectDelay * Math.pow(1.5, managed.reconnectAttempts);
    logger.debug(`Reconnecting in ${delay}ms (attempt ${managed.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect(sessionId);
    }, delay);
  }

  private clearTimers(): void {
    this.clearHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // ============================================================================
  // Public API
  // ============================================================================

  get api() {
    return {
      connect: this.connect.bind(this),
      disconnect: this.disconnect.bind(this),
      subscribeSession: this.subscribeSession.bind(this),
      unsubscribeSession: this.unsubscribeSession.bind(this),
      isConnected: () => {
        const managed = this.registry.get('agent-session' as any);
        return managed.status === 'open';
      },
      getCurrentSessionId: () => this.currentSessionId,
    };
  }
}
