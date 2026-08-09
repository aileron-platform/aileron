import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useFileConflictController } from './useFileConflictController';
import type {
  FileConflictBatchResult,
  FileConflictPreflightRequest,
  FileConflictWorkflowTransport,
} from './types';

const request: FileConflictPreflightRequest = {
  operation: 'upload',
  targetPath: '/docs',
  sources: [{ sourcePath: 'draft.md', entryType: 'file' }],
  archivePath: null,
};

const result: FileConflictBatchResult = {
  items: [{
    sourcePath: 'draft.md',
    finalPath: '/docs/draft (1).md',
    status: 'kept-both',
    size: 10,
    type: 'file',
    error: null,
  }],
  total: 1,
  succeeded: 1,
  skipped: 0,
  failed: 0,
};

const createTransport = (): FileConflictWorkflowTransport<{ files: string[] }> => ({
  preflight: vi.fn().mockResolvedValue({ conflicts: [], total: 0 }),
  execute: vi.fn().mockResolvedValue(result),
});

describe('useFileConflictController', () => {
  it('runs exactly one preflight before executing a conflict-free batch', async () => {
    const transport = createTransport();
    const onCompleted = vi.fn();
    const { result: hook } = renderHook(() => useFileConflictController({ transport, onCompleted }));

    await act(async () => {
      await hook.current.start(request, { files: ['draft.md'] });
    });

    expect(transport.preflight).toHaveBeenCalledTimes(1);
    expect(transport.execute).toHaveBeenCalledWith(
      {
        ...request,
        defaultStrategy: 'cancel',
        resolutions: [],
        payload: { files: ['draft.md'] },
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(onCompleted).toHaveBeenCalledWith(result);
    expect(hook.current.result).toEqual(result);
    expect(hook.current.phase).toBe('completed');
    expect(hook.current.open).toBe(false);
  });

  it('keeps the conflict dialog closed while a conflict-free execution is pending', async () => {
    let resolveExecution!: (value: FileConflictBatchResult) => void;
    const transport = createTransport();
    vi.mocked(transport.execute).mockReturnValueOnce(new Promise((resolve) => {
      resolveExecution = resolve;
    }));
    const { result: hook } = renderHook(() => useFileConflictController({ transport }));

    let startPromise!: Promise<FileConflictBatchResult | null>;
    act(() => {
      startPromise = hook.current.start(request, { files: ['draft.md'] });
    });

    await waitFor(() => expect(hook.current.phase).toBe('executing'));
    expect(hook.current.pending).toBe(true);
    expect(hook.current.open).toBe(false);

    await act(async () => {
      resolveExecution(result);
      await startPromise;
    });
  });

  it('holds a conflicting batch for one aggregate resolution and emits per-item strategies', async () => {
    const transport = createTransport();
    vi.mocked(transport.preflight).mockResolvedValue({
      total: 2,
      conflicts: [
        {
          sourcePath: 'draft.md',
          targetPath: '/docs/draft.md',
          sourceType: 'file',
          targetType: 'file',
          canReplace: true,
        },
        {
          sourcePath: 'assets',
          targetPath: '/docs/assets',
          sourceType: 'directory',
          targetType: 'file',
          canReplace: false,
        },
      ],
    });
    const { result: hook } = renderHook(() => useFileConflictController({ transport }));

    await act(async () => {
      await hook.current.start(request, { files: ['draft.md'] });
    });

    expect(hook.current.phase).toBe('resolving');
    expect(hook.current.open).toBe(true);
    expect(transport.execute).not.toHaveBeenCalled();

    act(() => {
      hook.current.setDefaultStrategy('replace');
      hook.current.setItemStrategy('draft.md', 'replace');
      hook.current.setItemStrategy('assets', 'replace');
      hook.current.setItemStrategy('assets', 'skip');
    });

    expect(hook.current.defaultStrategy).toBe('keep-both');
    expect(hook.current.itemStrategies).toEqual({
      'draft.md': 'replace',
      assets: 'skip',
    });

    await act(async () => {
      await hook.current.confirm();
    });

    expect(transport.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultStrategy: 'keep-both',
        resolutions: [
          { sourcePath: 'draft.md', strategy: 'replace' },
          { sourcePath: 'assets', strategy: 'skip' },
        ],
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('cancels the entire batch without executing any mutation', async () => {
    const transport = createTransport();
    vi.mocked(transport.preflight).mockResolvedValue({
      total: 1,
      conflicts: [{
        sourcePath: 'draft.md',
        targetPath: '/docs/draft.md',
        sourceType: 'file',
        targetType: 'file',
        canReplace: true,
      }],
    });
    const onCancelled = vi.fn();
    const { result: hook } = renderHook(() => useFileConflictController({ transport, onCancelled }));

    await act(async () => {
      await hook.current.start(request, { files: ['draft.md'] });
    });
    act(() => hook.current.cancel());

    expect(hook.current.phase).toBe('cancelled');
    expect(hook.current.open).toBe(false);
    expect(transport.execute).not.toHaveBeenCalled();
    expect(onCancelled).toHaveBeenCalledTimes(1);
  });

  it('ignores a stale preflight response after a newer request starts', async () => {
    let resolveFirst!: (value: { conflicts: []; total: 0 }) => void;
    const first = new Promise<{ conflicts: []; total: 0 }>((resolve) => {
      resolveFirst = resolve;
    });
    const transport = createTransport();
    vi.mocked(transport.preflight)
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce({ conflicts: [], total: 0 });
    const { result: hook } = renderHook(() => useFileConflictController({ transport }));

    let firstStart!: Promise<unknown>;
    act(() => {
      firstStart = hook.current.start(request, { files: ['first.md'] });
    });
    await act(async () => {
      await hook.current.start(
        { ...request, sources: [{ sourcePath: 'second.md', entryType: 'file' }] },
        { files: ['second.md'] },
      );
    });
    resolveFirst({ conflicts: [], total: 0 });
    await act(async () => { await firstStart; });

    expect(transport.execute).toHaveBeenCalledTimes(1);
    expect(transport.execute).toHaveBeenCalledWith(
      expect.objectContaining({ payload: { files: ['second.md'] } }),
      expect.anything(),
    );
  });

  it('keeps the dialog and resolutions available after execution fails', async () => {
    const transport = createTransport();
    vi.mocked(transport.preflight).mockResolvedValue({
      total: 1,
      conflicts: [{
        sourcePath: 'draft.md',
        targetPath: '/docs/draft.md',
        sourceType: 'file',
        targetType: 'file',
        canReplace: true,
      }],
    });
    vi.mocked(transport.execute).mockRejectedValue(new Error('offline'));
    const { result: hook } = renderHook(() => useFileConflictController({ transport }));

    await act(async () => { await hook.current.start(request, { files: ['draft.md'] }); });
    await act(async () => { await hook.current.confirm(); });

    await waitFor(() => expect(hook.current.phase).toBe('resolving'));
    expect(hook.current.open).toBe(true);
    expect(hook.current.error).toBeInstanceOf(Error);
    expect(hook.current.conflicts).toHaveLength(1);
  });
});
