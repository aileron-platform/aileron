import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Thread } from '../model/threadModel';
import { aiChatThreadQueryKey } from '../api/threadQueryKeys';

const { threadApi } = vi.hoisted(() => ({
  threadApi: {
    listThreads: vi.fn(),
    createDraft: vi.fn(),
    patchDraft: vi.fn(),
  },
}));

vi.mock('./useThreadApi', () => ({
  useThreadApi: () => threadApi,
  requireThreadApi: (api: unknown) => api,
}));

import { useThreads } from './useThreads';

const thread: Thread = {
  id: 'thread-1',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'Inspect workspace',
  agenticTool: 'claude',
  model: 'claude-alpha',
  claudeMode: 'execute',
  status: 'draft',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: 200000,
  createdAt: '2026-07-10T00:00:00Z',
  updatedAt: '2026-07-10T00:00:00Z',
  queuedMessages: [],
  draftMessage: null,
};

describe('useThreads', () => {
  beforeEach(() => {
    threadApi.listThreads.mockReset().mockResolvedValue([]);
    threadApi.createDraft.mockReset();
    threadApi.patchDraft.mockReset().mockResolvedValue(thread);
  });

  it('stores a patched draft under the workspace-scoped thread query key', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useThreads('workspace-1'), { wrapper });

    await act(async () => {
      await result.current.patchDraft.mutateAsync({ threadId: thread.id, input: { model: thread.model } });
    });

    expect(queryClient.getQueryData(aiChatThreadQueryKey('workspace-1', thread.id))).toEqual(thread);
    expect(queryClient.getQueryData(aiChatThreadQueryKey('workspace-2', thread.id))).toBeUndefined();
  });
});
