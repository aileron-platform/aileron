// @vitest-environment jsdom

import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Thread } from '../model/threadModel';
import { useMarkThreadRead } from './useMarkThreadRead';

const buildThread = (updatedAt: string): Thread => ({
  id: 'thread-read',
  workspaceId: 'workspace-read',
  userId: 'user-read',
  title: 'aiChat.mock.threadTitles.complete',
  agenticTool: 'claude',
  model: 'sonnet-5',
  claudeMode: 'execute',
  status: 'complete',
  archived: false,
  errorCode: null,
  errorInfo: null,
  errorMessage: null,
  contextTokens: null,
  contextWindow: null,
  createdAt: '2026-07-09T01:00:00.000Z',
  updatedAt,
  messages: [],
  queuedMessages: [],
  draftMessage: null,
});

const Harness = ({ thread }: { thread: Thread | null }) => {
  useMarkThreadRead({
    thread,
    workspaceId: 'workspace-read',
    userId: 'user-read',
  });
  return null;
};

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe('useMarkThreadRead', () => {
  it('marks a visible thread as read and updates when updatedAt changes', () => {
    const firstUpdatedAt = '2026-07-09T01:00:00.000Z';
    const nextUpdatedAt = '2026-07-09T01:05:00.000Z';
    const view = render(<Harness thread={buildThread(firstUpdatedAt)} />);

    expect(localStorage.getItem('aichat.lastRead.user-read.workspace-read.thread-read')).toBe(firstUpdatedAt);

    view.rerender(<Harness thread={buildThread(nextUpdatedAt)} />);

    expect(localStorage.getItem('aichat.lastRead.user-read.workspace-read.thread-read')).toBe(nextUpdatedAt);
  });
});
