import { describe, expect, it } from 'vitest';
import {
  applyStageAllToChangesResponse,
  applyStagePathsToChangesResponse,
  applyUnstageAllToChangesResponse,
} from './versionControlOptimisticUpdates';

describe('versionControlOptimisticUpdates', () => {
  const page = <T,>(items: T[], total = items.length) => ({
    items,
    total,
    nextCursor: null,
    hasMore: total > items.length,
  });

  it('applies staged paths to the visible changes cache immediately', () => {
    const next = applyStagePathsToChangesResponse(
      {
        staged: page([{ name: 'README.md', path: 'README.md', status: 'M', type: 'modified' }]),
        unstaged: page([{ name: 'notes.md', path: 'notes.md', status: 'M', type: 'modified' }]),
        untracked: page([{ name: 'draft.txt', path: 'draft.txt', status: '??', type: 'untracked' }]),
        conflicts: page([{ name: 'conflict.txt', path: 'conflict.txt', status: 'UU', type: 'unmerged' }]),
      },
      ['notes.md', 'draft.txt'],
    );

    expect(next?.staged.items.map((file) => file.path)).toEqual([
      'README.md',
      'notes.md',
      'draft.txt',
    ]);
    expect(next?.staged.items.find((file) => file.path === 'draft.txt')).toMatchObject({
      status: 'A',
      type: 'added',
      changeType: 'staged',
    });
    expect(next?.unstaged.items).toEqual([]);
    expect(next?.untracked.items).toEqual([]);
    expect(next?.conflicts.items).toEqual([
      {
        name: 'conflict.txt',
        path: 'conflict.txt',
        status: 'UU',
        type: 'unmerged',
      },
    ]);
    expect(next?.untracked.total).toBe(0);
  });

  it('preserves paginated totals while staging all files', () => {
    const next = applyStageAllToChangesResponse({
      staged: page([{ name: 'ready.md', path: 'ready.md', status: 'M' }], 2),
      unstaged: page([{ name: 'notes.md', path: 'notes.md', status: 'M' }], 5),
      untracked: page([{ name: 'draft.md', path: 'draft.md', status: '??' }], 3),
      conflicts: page([]),
    });

    expect(next).toMatchObject({
      staged: expect.objectContaining({ total: 10, hasMore: true }),
      unstaged: expect.objectContaining({ total: 0, hasMore: false }),
      untracked: expect.objectContaining({ total: 0, hasMore: false }),
    });
  });

  it('preserves paginated totals while unstaging all files', () => {
    const next = applyUnstageAllToChangesResponse({
      staged: page([{ name: 'ready.md', path: 'ready.md', status: 'M' }], 4),
      unstaged: page([{ name: 'notes.md', path: 'notes.md', status: 'M' }], 2),
      untracked: page([]),
      conflicts: page([]),
    });

    expect(next).toMatchObject({
      staged: expect.objectContaining({ items: [], total: 0, hasMore: false }),
      unstaged: expect.objectContaining({ total: 6, hasMore: true }),
    });
  });
});
