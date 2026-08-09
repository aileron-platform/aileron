import type { ListThreadsQuery } from './threadApi';

export const aiChatThreadsQueryKey = (workspaceId: string, filters: ListThreadsQuery = {}) =>
  ['ai-chat', 'threads', workspaceId, filters.archived ?? false] as const;

export const aiChatThreadQueryKey = (
  workspaceId: string,
  threadId: string | null | undefined,
) => ['ai-chat', 'thread', workspaceId, threadId ?? ''] as const;

export const aiChatThreadTimelineQueryKey = (workspaceId: string, threadId: string) =>
  ['ai-chat', 'thread-timeline', workspaceId, threadId] as const;

export const aiChatToolResultQueryKey = (
  workspaceId: string,
  threadId: string,
  messageId: string,
) => ['ai-chat', 'tool-result', workspaceId, threadId, messageId] as const;

export const aiChatAutomationExecutionThreadQueryKey = (
  workspaceId: string,
  executionId: string | null | undefined,
) => ['ai-chat', 'automation-execution-thread', workspaceId, executionId ?? ''] as const;

export const aiChatCapabilitiesQueryKey = (workspaceId: string) => ['ai-chat', 'capabilities', workspaceId] as const;
