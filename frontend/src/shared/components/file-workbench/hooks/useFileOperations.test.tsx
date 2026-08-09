import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FileOperationResponse, FileTreeDataAdapter } from '../types';
import { useFileOperations } from './useFileOperations';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

const createDeferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const createAdapter = (
  update: FileTreeDataAdapter['update'],
): FileTreeDataAdapter => ({
  getTree: vi.fn().mockResolvedValue([]),
  getChildren: vi.fn().mockResolvedValue([]),
  getContent: vi.fn().mockResolvedValue(''),
  create: vi.fn().mockResolvedValue({ success: true }),
  update,
  delete: vi.fn().mockResolvedValue({ success: true }),
  batchDelete: vi.fn().mockResolvedValue({
    success: true,
    deleted: [],
    failed: [],
    total: 0,
    successCount: 0,
    failedCount: 0,
  }),
  move: vi.fn().mockResolvedValue({ success: true }),
  upload: vi.fn().mockResolvedValue([]),
  download: vi.fn().mockResolvedValue(undefined),
});

describe('useFileOperations', () => {
  it('keeps an activity busy until every concurrent request settles', async () => {
    const requests = [
      createDeferred<FileOperationResponse>(),
      createDeferred<FileOperationResponse>(),
    ];
    const update = vi.fn()
      .mockReturnValueOnce(requests[0].promise)
      .mockReturnValueOnce(requests[1].promise);
    const { result } = renderHook(() => useFileOperations({
      adapter: createAdapter(update),
      resourceGeneration: 0,
    }));

    let first!: Promise<FileOperationResponse>;
    let second!: Promise<FileOperationResponse>;
    act(() => {
      first = result.current.updateFile('/first.md', 'first');
      second = result.current.updateFile('/second.md', 'second');
    });
    expect(result.current.isUpdating).toBe(true);

    await act(async () => {
      requests[0].resolve({ success: true });
      await first;
    });
    expect(result.current.isUpdating).toBe(true);

    await act(async () => {
      requests[1].resolve({ success: true });
      await second;
    });
    expect(result.current.isUpdating).toBe(false);
  });

  it('does not let an old generation settlement clear current activity', async () => {
    const oldRequest = createDeferred<FileOperationResponse>();
    const currentRequest = createDeferred<FileOperationResponse>();
    const update = vi.fn((path: string) => (
      path === '/old.md' ? oldRequest.promise : currentRequest.promise
    ));
    const adapter = createAdapter(update);
    const { result, rerender } = renderHook(
      ({ resourceGeneration }: { resourceGeneration: number }) => useFileOperations({
        adapter,
        resourceGeneration,
      }),
      { initialProps: { resourceGeneration: 0 } },
    );

    let oldOperation!: Promise<FileOperationResponse>;
    act(() => {
      oldOperation = result.current.updateFile('/old.md', 'old');
    });
    expect(result.current.isUpdating).toBe(true);

    rerender({ resourceGeneration: 1 });
    expect(result.current.isUpdating).toBe(false);

    let currentOperation!: Promise<FileOperationResponse>;
    act(() => {
      currentOperation = result.current.updateFile('/current.md', 'current');
    });
    expect(result.current.isUpdating).toBe(true);

    await act(async () => {
      oldRequest.resolve({ success: true });
      await oldOperation;
    });
    expect(result.current.isUpdating).toBe(true);

    await act(async () => {
      currentRequest.resolve({ success: true });
      await currentOperation;
    });
    expect(result.current.isUpdating).toBe(false);
  });
});
