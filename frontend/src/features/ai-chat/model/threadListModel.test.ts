import { describe, expect, it } from 'vitest';
import { sortThreadSummaries } from './threadListModel';
import type { ThreadSummary } from './threadModel';

const buildThread = (overrides: Partial<ThreadSummary>): ThreadSummary => ({
  id: 'thread',
  workspaceId: 'workspace-1',
  userId: 'user-1',
  title: 'Thread',
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
  createdAt: '2026-07-09T00:00:00.000Z',
  updatedAt: '2026-07-09T00:00:00.000Z',
  ...overrides,
});

const t = (key: string) => key;

describe('sortThreadSummaries', () => {
  it('uses createdAt for drafts and updatedAt for non-drafts in activity order', () => {
    const threads = [
      buildThread({
        id: 'edited-draft',
        status: 'draft',
        createdAt: '2026-07-09T01:00:00.000Z',
        updatedAt: '2026-07-09T04:00:00.000Z',
      }),
      buildThread({
        id: 'newer-draft',
        status: 'draft',
        createdAt: '2026-07-09T02:00:00.000Z',
        updatedAt: '2026-07-09T02:00:00.000Z',
      }),
      buildThread({
        id: 'completed',
        status: 'complete',
        createdAt: '2026-07-09T01:00:00.000Z',
        updatedAt: '2026-07-09T04:00:00.000Z',
      }),
    ];

    expect(sortThreadSummaries(threads, 'activity', t).map((thread) => thread.id)).toEqual([
      'completed',
      'newer-draft',
      'edited-draft',
    ]);
    expect(sortThreadSummaries(threads, 'activity', t)).not.toBe(threads);
  });

  it('sorts by created time descending', () => {
    const threads = [
      buildThread({ id: 'old', createdAt: '2026-07-09T01:00:00.000Z' }),
      buildThread({ id: 'new', createdAt: '2026-07-09T02:00:00.000Z' }),
    ];

    expect(sortThreadSummaries(threads, 'created', t).map((thread) => thread.id)).toEqual(['new', 'old']);
  });

  it('sorts by resolved title', () => {
    const threads = [
      buildThread({ id: 'z', title: 'Zeta' }),
      buildThread({ id: 'a', title: 'Alpha' }),
    ];

    expect(sortThreadSummaries(threads, 'title', t).map((thread) => thread.id)).toEqual(['a', 'z']);
  });
});
