import { describe, expect, it, vi } from 'vitest';
import {
  composeFileConflictTransports,
  createLocalFileConflictTransport,
  type LocalFileConflictEntry,
} from './localFileConflictTransport';
import type {
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictTransportOptions,
  FileConflictWorkflowTransport,
} from './types';

interface TestPayload {
  content?: string;
  entryType?: 'file' | 'directory';
  sourcePath?: string;
}

const transportOptions: FileConflictTransportOptions = {
  signal: new AbortController().signal,
};

const preflightRequest = (
  overrides: Partial<FileConflictPreflightRequest> = {},
): FileConflictPreflightRequest => ({
  operation: 'create',
  targetPath: '/docs/report.md',
  sources: [{ sourcePath: '/report.md', entryType: 'file' }],
  archivePath: null,
  ...overrides,
});

const executionRequest = (
  overrides: Partial<FileConflictExecutionRequest<TestPayload>> = {},
): FileConflictExecutionRequest<TestPayload> => ({
  ...preflightRequest(),
  defaultStrategy: 'keep-both',
  resolutions: [],
  payload: { content: '# New report', entryType: 'file' },
  ...overrides,
});

const createTestTransport = (entries: Record<string, LocalFileConflictEntry> = {}) => {
  const entryMap = new Map(Object.entries(entries));
  const refreshTree = vi.fn().mockResolvedValue(undefined);
  const findEntry = vi.fn((path: string) => entryMap.get(path) ?? null);
  const createEntry = vi.fn().mockResolvedValue({ success: true });
  const moveEntry = vi.fn().mockResolvedValue({ success: true });
  const deleteEntry = vi.fn().mockResolvedValue({ success: true });
  const transport = createLocalFileConflictTransport<TestPayload>({
    findEntry,
    refreshTree,
    createEntry,
    moveEntry,
    deleteEntry,
    getPayload: payload => payload,
  });

  return {
    transport,
    refreshTree,
    findEntry,
    createEntry,
    moveEntry,
    deleteEntry,
  };
};

describe('createLocalFileConflictTransport', () => {
  it('refreshes before preflight and does not report a conflict for a missing target', async () => {
    const testTransport = createTestTransport();

    await expect(testTransport.transport.preflight(
      preflightRequest(),
      transportOptions,
    )).resolves.toEqual({ conflicts: [], total: 1 });

    expect(testTransport.refreshTree).toHaveBeenCalledTimes(1);
    expect(testTransport.findEntry).toHaveBeenCalledWith('/docs/report.md');
  });

  it('reports a conflict only when the refreshed target exists', async () => {
    const testTransport = createTestTransport({
      '/docs/report.md': { type: 'file' },
    });

    await expect(testTransport.transport.preflight(
      preflightRequest(),
      transportOptions,
    )).resolves.toEqual({
      conflicts: [{
        sourcePath: '/report.md',
        targetPath: '/docs/report.md',
        sourceType: 'file',
        targetType: 'file',
        canReplace: true,
      }],
      total: 1,
    });
  });

  it('uses the refreshed snapshot instead of a stale state closure', async () => {
    const refreshTree = vi.fn().mockResolvedValue([]);
    const findEntry = vi.fn().mockReturnValue({ type: 'file' as const });
    const transport = createLocalFileConflictTransport<TestPayload>({
      findEntry,
      refreshTree,
      createEntry: vi.fn().mockResolvedValue({ success: true }),
      moveEntry: vi.fn().mockResolvedValue({ success: true }),
      deleteEntry: vi.fn().mockResolvedValue({ success: true }),
      getPayload: payload => payload,
    });

    await expect(transport.preflight(preflightRequest(), transportOptions))
      .resolves.toEqual({ conflicts: [], total: 1 });
    expect(findEntry).not.toHaveBeenCalled();
  });

  it('detects a target that appears only in the refreshed snapshot', async () => {
    const refreshTree = vi.fn().mockResolvedValue([
      { path: '/docs/report.md', type: 'file' as const },
    ]);
    const findEntry = vi.fn().mockReturnValue(null);
    const transport = createLocalFileConflictTransport<TestPayload>({
      findEntry,
      refreshTree,
      createEntry: vi.fn().mockResolvedValue({ success: true }),
      moveEntry: vi.fn().mockResolvedValue({ success: true }),
      deleteEntry: vi.fn().mockResolvedValue({ success: true }),
      getPayload: payload => payload,
    });

    await expect(transport.preflight(preflightRequest(), transportOptions))
      .resolves.toMatchObject({ conflicts: [{ targetPath: '/docs/report.md' }] });
    expect(findEntry).not.toHaveBeenCalled();
  });

  it('keeps both by choosing the next available path without deleting the target', async () => {
    const testTransport = createTestTransport({
      '/docs/report.md': { type: 'file' },
      '/docs/report (1).md': { type: 'file' },
    });

    await expect(testTransport.transport.execute(
      executionRequest(),
      transportOptions,
    )).resolves.toMatchObject({
      succeeded: 1,
      items: [{
        sourcePath: '/report.md',
        finalPath: '/docs/report (2).md',
        status: 'kept-both',
      }],
    });

    expect(testTransport.deleteEntry).not.toHaveBeenCalled();
    expect(testTransport.createEntry).toHaveBeenCalledWith(
      '/docs/report (2).md',
      'file',
      '# New report',
    );
  });

  it('replaces an existing directory only after an explicit replace strategy', async () => {
    const testTransport = createTestTransport({
      '/docs/assets': { type: 'directory' },
    });

    await expect(testTransport.transport.execute(
      executionRequest({
        targetPath: '/docs/assets',
        sources: [{ sourcePath: '/assets', entryType: 'directory' }],
        payload: { entryType: 'directory' },
        resolutions: [{ sourcePath: '/assets', strategy: 'replace' }],
      }),
      transportOptions,
    )).resolves.toMatchObject({
      succeeded: 1,
      items: [{
        sourcePath: '/assets',
        finalPath: '/docs/assets',
        status: 'replaced',
        type: 'directory',
      }],
    });

    expect(testTransport.deleteEntry).toHaveBeenCalledWith('/docs/assets', true);
    expect(testTransport.createEntry).toHaveBeenCalledWith('/docs/assets', 'directory', '');
  });

  it('does not mutate when the user skips or cancels a conflict', async () => {
    const testTransport = createTestTransport({
      '/docs/report.md': { type: 'file' },
    });

    for (const strategy of ['skip', 'cancel'] as const) {
      await expect(testTransport.transport.execute(
        executionRequest({
          resolutions: [{ sourcePath: '/report.md', strategy }],
        }),
        transportOptions,
      )).resolves.toMatchObject({
        succeeded: 0,
        skipped: 1,
        items: [{ status: strategy === 'skip' ? 'skipped' : 'cancelled' }],
      });
    }

    expect(testTransport.deleteEntry).not.toHaveBeenCalled();
    expect(testTransport.createEntry).not.toHaveBeenCalled();
    expect(testTransport.moveEntry).not.toHaveBeenCalled();
  });

  it('moves a source without opening a conflict dialog when the target is missing', async () => {
    const testTransport = createTestTransport();

    await expect(testTransport.transport.execute(
      executionRequest({
        operation: 'move',
        targetPath: '/docs/renamed.md',
        sources: [{ sourcePath: '/report.md', entryType: 'file' }],
        payload: { sourcePath: '/report.md', entryType: 'file' },
      }),
      transportOptions,
    )).resolves.toMatchObject({
      succeeded: 1,
      items: [{
        finalPath: '/docs/renamed.md',
        status: 'created',
      }],
    });

    expect(testTransport.moveEntry).toHaveBeenCalledWith('/report.md', '/docs/renamed.md');
    expect(testTransport.createEntry).not.toHaveBeenCalled();
  });
});

describe('composeFileConflictTransports', () => {
  it('routes create and move to the local transport and other operations to the remote transport', async () => {
    const remote: FileConflictWorkflowTransport<TestPayload> = {
      preflight: vi.fn().mockResolvedValue({ conflicts: [], total: 0 }),
      execute: vi.fn().mockResolvedValue({ items: [], total: 0, succeeded: 0, skipped: 0, failed: 0 }),
    };
    const local: FileConflictWorkflowTransport<TestPayload> = {
      preflight: vi.fn().mockResolvedValue({ conflicts: [], total: 0 }),
      execute: vi.fn().mockResolvedValue({ items: [], total: 0, succeeded: 0, skipped: 0, failed: 0 }),
    };
    const composed = composeFileConflictTransports(remote, local);

    await composed.preflight(preflightRequest({ operation: 'create' }), transportOptions);
    await composed.preflight(preflightRequest({ operation: 'upload' }), transportOptions);
    await composed.execute(executionRequest({ operation: 'move' }), transportOptions);
    await composed.execute(executionRequest({ operation: 'paste' }), transportOptions);

    expect(local.preflight).toHaveBeenCalledTimes(1);
    expect(remote.preflight).toHaveBeenCalledTimes(1);
    expect(local.execute).toHaveBeenCalledTimes(1);
    expect(remote.execute).toHaveBeenCalledTimes(1);
  });
});
