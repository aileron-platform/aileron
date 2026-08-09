import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { ThreadStatus } from '../model/threadModel';
import type { ThreadTimelinePage, ThreadTurnStatus } from '../model/threadTimelineModel';
import { getThreadApi } from '../api/threadApi';
import { aiChatThreadQueryKey, aiChatThreadTimelineQueryKey } from '../api/threadQueryKeys';
import { mergeThreadTimelineSnapshot } from '../hooks/useThreadTimeline';
import type { InfiniteData } from '@tanstack/react-query';
import { WebSocketConnectionRegistry } from '@/shared/realtime/webSocketConnectionRegistry';
import { createWebSocketBearerProtocols } from '@/shared/realtime/webSocketBearerProtocols';
import { createLogger } from '@/shared/services/logger';
import { executionGrantBroker } from '@/features/auth/public';
import { toSameOriginWebSocketUrl } from '@/shared/utils/workspaceGateway';

const logger = createLogger('ThreadEvents');
const registry = new WebSocketConnectionRegistry<'chat'>();
const SOCKET_TYPE = 'chat' as const;
const THREAD_WEBSOCKET_PROTOCOL = 'aileron-thread-v1';
const RECONNECT_BASE_DELAY = 1_000;
const RECONNECT_MAX_DELAY = 30_000;
const EVENT_TYPES = new Set<ThreadEvent['type']>([
  'thread_created',
  'messages_updated',
  'status_updated',
  'archived',
  'deleted',
  'error',
  'timeline_updated',
]);

export interface ThreadEvent {
  threadId: string;
  type: 'thread_created' | 'messages_updated' | 'status_updated' | 'archived' | 'deleted' | 'error' | 'timeline_updated';
  status?: ThreadStatus;
  threadVersion?: number;
  createdItemIds: string[];
  changedItemIds: string[];
  turns: Array<{ id: string; version: number; status: ThreadTurnStatus }>;
  executions: Array<{ id: string; version: number; status: ThreadTurnStatus }>;
  refreshLatest: boolean;
}

type ThreadEventSubscriber = (event: ThreadEvent) => void;
const subscribers = new Map<string, Set<ThreadEventSubscriber>>();

export const subscribeThreadEvents = (
  workspaceId: string,
  callback: ThreadEventSubscriber,
): (() => void) => {
  const workspaceSubscribers = subscribers.get(workspaceId) ?? new Set();
  workspaceSubscribers.add(callback);
  subscribers.set(workspaceId, workspaceSubscribers);
  return () => {
    workspaceSubscribers.delete(callback);
    if (workspaceSubscribers.size === 0) {
      subscribers.delete(workspaceId);
    }
  };
};

const buildWebSocketUrl = (runtimeBaseUrl: string): string => {
  return toSameOriginWebSocketUrl(
    `${runtimeBaseUrl.replace(/\/$/, '')}/api/v1/threads/events`,
  );
};

const parseThreadEvent = (data: string): ThreadEvent | null => {
  try {
    const value = JSON.parse(data) as Record<string, unknown>;
    const threadId = value.threadId ?? value.thread_id;
    if (typeof threadId !== 'string' || typeof value.type !== 'string') return null;
    if (!EVENT_TYPES.has(value.type as ThreadEvent['type'])) return null;
    return {
      threadId,
      type: value.type as ThreadEvent['type'],
      ...(typeof value.status === 'string' ? { status: value.status as ThreadStatus } : {}),
      ...(typeof value.threadVersion === 'number' ? { threadVersion: value.threadVersion } : {}),
      createdItemIds: Array.isArray(value.createdItemIds)
        ? value.createdItemIds.filter((item): item is string => typeof item === 'string')
        : [],
      changedItemIds: Array.isArray(value.changedItemIds)
        ? value.changedItemIds.filter((item): item is string => typeof item === 'string')
        : [],
      turns: Array.isArray(value.turns) ? value.turns.filter((item): item is ThreadEvent['turns'][number] =>
        typeof item === 'object' && item !== null && typeof (item as { id?: unknown }).id === 'string'
      ) : [],
      executions: Array.isArray(value.executions) ? value.executions.filter((item): item is ThreadEvent['executions'][number] =>
        typeof item === 'object' && item !== null && typeof (item as { id?: unknown }).id === 'string'
      ) : [],
      refreshLatest: value.refreshLatest === true,
    };
  } catch (error) {
    logger.warn('Ignoring invalid thread event', { error });
    return null;
  }
};

export const useThreadEvents = (
  workspaceId: string,
  runtimeBaseUrl: string,
  enabled: boolean,
): void => {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !workspaceId || !runtimeBaseUrl) return undefined;

    const api = getThreadApi(runtimeBaseUrl);
    let active = true;
    let reconnectTimer: number | null = null;

    const invalidateList = () => queryClient.invalidateQueries({
      queryKey: ['ai-chat', 'threads', workspaceId],
    });

    const scheduleReconnect = () => {
      if (!active || reconnectTimer !== null) return;
      registry.incrementAttempts(SOCKET_TYPE);
      const attempts = registry.getOrCreate(SOCKET_TYPE).reconnectAttempts;
      const delay = Math.min(RECONNECT_BASE_DELAY * 2 ** (attempts - 1), RECONNECT_MAX_DELAY);
      registry.updateStatus(SOCKET_TYPE, 'reconnecting');
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, delay);
    };

    const openSocket = (token: string) => {
      if (!active) return;
      let protocols: [string, string];
      try {
        protocols = createWebSocketBearerProtocols(
          THREAD_WEBSOCKET_PROTOCOL,
          token,
        );
      } catch (error) {
        logger.warn('Thread WebSocket bearer token is invalid', { error });
        return;
      }
      const socket = new WebSocket(buildWebSocketUrl(runtimeBaseUrl), protocols);
      registry.setSocket(SOCKET_TYPE, socket, 'connecting');

      socket.onopen = () => {
        if (!active || registry.getOrCreate(SOCKET_TYPE).socket !== socket) return;
        const reconnected = registry.getOrCreate(SOCKET_TYPE).reconnectAttempts > 0;
        registry.resetAttempts(SOCKET_TYPE);
        registry.updateStatus(SOCKET_TYPE, 'open');
        if (reconnected) {
          void invalidateList();
          void queryClient.invalidateQueries({ queryKey: ['ai-chat', 'thread', workspaceId] });
          void queryClient.resetQueries({ queryKey: ['ai-chat', 'thread-timeline', workspaceId] });
        }
      };

      socket.onmessage = (message) => {
        const event = parseThreadEvent(String(message.data));
        if (!event) return;
        if (event.type === 'thread_created') {
          void invalidateList();
        } else if (event.type === 'deleted') {
          queryClient.removeQueries({
            queryKey: aiChatThreadQueryKey(workspaceId, event.threadId),
          });
          void invalidateList();
        } else if (event.type === 'timeline_updated') {
          const queryKey = aiChatThreadTimelineQueryKey(workspaceId, event.threadId);
          if (event.refreshLatest) {
            void queryClient.resetQueries({ queryKey, exact: true });
          } else {
            const ids = [...new Set([...event.createdItemIds, ...event.changedItemIds])];
            if (ids.length > 0) {
              void api.getTimelineItems(event.threadId, ids)
                .then((snapshot) => mergeThreadTimelineSnapshot(
                  queryClient, workspaceId, event.threadId, snapshot,
                ))
                .catch(() => queryClient.resetQueries({ queryKey, exact: true }));
            }
            queryClient.setQueryData(
              queryKey,
              (current: InfiniteData<ThreadTimelinePage, number | undefined> | undefined) => {
                if (!current) return current;
                const turnPatches = new Map(event.turns.map((item) => [item.id, item]));
                const executionPatches = new Map(event.executions.map((item) => [item.id, item]));
                return {
                  ...current,
                  pages: current.pages.map((page) => ({
                    ...page,
                    turns: page.turns.map((item) => {
                      const patch = turnPatches.get(item.id);
                      return patch && patch.version >= item.version ? { ...item, ...patch } : item;
                    }),
                    executions: page.executions.map((item) => {
                      const patch = executionPatches.get(item.id);
                      return patch && patch.version >= item.version ? { ...item, ...patch } : item;
                    }),
                  })),
                };
              },
            );
          }
          void queryClient.invalidateQueries({ queryKey: aiChatThreadQueryKey(workspaceId, event.threadId) });
        } else if (event.type === 'messages_updated') {
          void queryClient.invalidateQueries({
            queryKey: aiChatThreadQueryKey(workspaceId, event.threadId),
          });
        } else {
          void queryClient.invalidateQueries({
            queryKey: aiChatThreadQueryKey(workspaceId, event.threadId),
          });
          void invalidateList();
        }
        subscribers.get(workspaceId)?.forEach((callback) => callback(event));
      };

      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!active || registry.getOrCreate(SOCKET_TYPE).socket !== socket) return;
        registry.setSocket(SOCKET_TYPE, null, 'closed');
        scheduleReconnect();
      };
    };

    const connect = () => {
      if (!active) return;
      const existing = registry.getOrCreate(SOCKET_TYPE);
      if (existing.status === 'connecting' || existing.status === 'open') return;

      executionGrantBroker.registerTarget(runtimeBaseUrl, workspaceId);
      try {
        const grant = executionGrantBroker.getGrant(
          runtimeBaseUrl, 'workspace-runtime', 'agent', workspaceId,
        );
        if (typeof (grant as unknown) === 'string') {
          openSocket(grant as unknown as string);
          return;
        }
        void grant.then(openSocket).catch((error: unknown) => {
          logger.warn('Thread WebSocket execution grant is unavailable', { error });
          scheduleReconnect();
        });
      } catch (error) {
        logger.warn('Thread WebSocket execution grant is unavailable', { error });
        scheduleReconnect();
      }
    };

    const reconnectNow = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      registry.updateStatus(SOCKET_TYPE, 'closed');
      void connect();
    };

    void connect();
    window.addEventListener('online', reconnectNow);
    return () => {
      active = false;
      window.removeEventListener('online', reconnectNow);
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      registry.close(SOCKET_TYPE);
      registry.resetAttempts(SOCKET_TYPE);
    };
  }, [enabled, queryClient, runtimeBaseUrl, workspaceId]);
};
