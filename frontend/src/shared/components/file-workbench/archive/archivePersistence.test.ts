import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  findLatestPersistedArchiveOperation,
  loadPersistedArchiveOperations,
  markPersistedArchiveDownloadTriggered,
  removePersistedArchiveOperation,
  removePersistedArchiveOperationsForContext,
  removePersistedArchiveOperationsForResource,
  upsertPersistedArchiveOperation,
  type PersistedArchiveOperation,
} from './archivePersistence';

const STORAGE_KEY = 'workspace.fileManagement.archiveOperations.v1';

interface WorkspaceArchiveContext {
  workspaceId: string;
  contextId: string | null;
  runtimeBaseUrl: string;
}

const createStorage = () => {
  const values = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      values.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      values.delete(key);
    }),
    clear: vi.fn(() => {
      values.clear();
    }),
    key: vi.fn((index: number) => Array.from(values.keys())[index] ?? null),
    get length() {
      return values.size;
    },
  } satisfies Storage;
};

const createOperation = (
  operationId: string,
  overrides: Partial<PersistedArchiveOperation<WorkspaceArchiveContext>> = {},
): PersistedArchiveOperation<WorkspaceArchiveContext> => ({
  operationId,
  archiveName: `${operationId}.zip`,
  paths: [`/${operationId}`],
  context: {
    workspaceId: 'workspace-1',
    contextId: null,
    runtimeBaseUrl: 'http://runtime.local',
  },
  startedAt: `2026-06-07T00:00:0${operationId.slice(-1)}Z`,
  ...overrides,
});

describe('archivePersistence', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-07T10:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns an empty list without browser storage', () => {
    expect(loadPersistedArchiveOperations(STORAGE_KEY, undefined)).toEqual([]);
  });

  it('clears invalid persisted JSON and returns an empty list', () => {
    const storage = createStorage();
    storage.setItem(STORAGE_KEY, '{invalid-json');

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([]);
    expect(storage.removeItem).toHaveBeenCalledWith(STORAGE_KEY);
  });

  it('upserts operations without duplicating an existing operation id', () => {
    const storage = createStorage();

    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-1'), storage);
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-2'), storage);
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-1', { archiveName: 'operation-1-new.zip' }),
      storage,
    );

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([
      createOperation('operation-2'),
      createOperation('operation-1', { archiveName: 'operation-1-new.zip' }),
    ]);
  });

  it('removes operations by operation id', () => {
    const storage = createStorage();
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-1'), storage);
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-2'), storage);

    removePersistedArchiveOperation(STORAGE_KEY, 'operation-1', storage);

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([
      createOperation('operation-2'),
    ]);
  });

  it('removes only operations for the revoked resource context', () => {
    const storage = createStorage();
    const revokedContext = {
      workspaceId: 'workspace-1',
      contextId: null,
      runtimeBaseUrl: 'http://runtime.local',
    };
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-1', { context: revokedContext }),
      storage,
    );
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-2', { context: revokedContext }),
      storage,
    );
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-3', {
        context: {
          workspaceId: 'workspace-2',
          contextId: null,
          runtimeBaseUrl: 'http://runtime.local',
        },
      }),
      storage,
    );

    removePersistedArchiveOperationsForContext({
      storageKey: STORAGE_KEY,
      context: revokedContext,
      storage,
    });

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([
      createOperation('operation-3', {
        context: {
          workspaceId: 'workspace-2',
          contextId: null,
          runtimeBaseUrl: 'http://runtime.local',
        },
      }),
    ]);
  });

  it('removes every operation for a revoked resource across runtime contexts', () => {
    const storage = createStorage();
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-1'), storage);
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-2', {
        context: {
          workspaceId: 'workspace-1',
          contextId: 'worktree:authorization',
          runtimeBaseUrl: 'http://runtime-restarted.local',
        },
      }),
      storage,
    );
    upsertPersistedArchiveOperation(
      STORAGE_KEY,
      createOperation('operation-3', {
        context: {
          workspaceId: 'workspace-2',
          contextId: null,
          runtimeBaseUrl: 'http://runtime.local',
        },
      }),
      storage,
    );

    removePersistedArchiveOperationsForResource({
      storageKey: STORAGE_KEY,
      resourceKey: 'workspaceId',
      resourceId: 'workspace-1',
      storage,
    });

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([
      createOperation('operation-3', {
        context: {
          workspaceId: 'workspace-2',
          contextId: null,
          runtimeBaseUrl: 'http://runtime.local',
        },
      }),
    ]);
  });

  it('marks an operation download as triggered', () => {
    const storage = createStorage();
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-1'), storage);

    markPersistedArchiveDownloadTriggered(STORAGE_KEY, 'operation-1', storage);

    expect(loadPersistedArchiveOperations(STORAGE_KEY, storage)).toEqual([
      createOperation('operation-1', {
        downloadTriggeredAt: '2026-06-07T10:00:00.000Z',
      }),
    ]);
  });

  it('finds the latest operation for the active workspace runtime context', () => {
    const storage = createStorage();
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-1'), storage);
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-2', {
      context: { workspaceId: 'workspace-1', contextId: 'git-context-1', runtimeBaseUrl: 'http://runtime.local' },
      startedAt: '2026-06-07T00:00:02Z',
    }), storage);
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-3', {
      context: { workspaceId: 'workspace-1', contextId: 'git-context-1', runtimeBaseUrl: 'http://runtime.local' },
      startedAt: '2026-06-07T00:00:03Z',
    }), storage);
    upsertPersistedArchiveOperation(STORAGE_KEY, createOperation('operation-4', {
      context: { workspaceId: 'workspace-2', contextId: 'git-context-1', runtimeBaseUrl: 'http://runtime.local' },
      startedAt: '2026-06-07T00:00:04Z',
    }), storage);

    expect(findLatestPersistedArchiveOperation({
      storageKey: STORAGE_KEY,
      context: { workspaceId: 'workspace-1', contextId: 'git-context-1', runtimeBaseUrl: 'http://runtime.local' },
      storage,
    })).toEqual(createOperation('operation-3', {
      context: { workspaceId: 'workspace-1', contextId: 'git-context-1', runtimeBaseUrl: 'http://runtime.local' },
      startedAt: '2026-06-07T00:00:03Z',
    }));
  });
});
