import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useFileEditor } from './useFileEditor';
import type { FileTreeNode } from '../types';

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

const createDeferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
};

const createFileNode = (path: string): FileTreeNode => ({
  id: path,
  path,
  name: path.split('/').pop() || path,
  type: 'file',
});

describe('useFileEditor', () => {
  it('remaps opened file and descendant tab paths while preserving edit state', () => {
    const { result } = renderHook(() => useFileEditor());

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base');
      result.current.openTab(createFileNode('/docs/nested/guide.md'), 'guide base');
      result.current.updateContent('/docs/nested/guide.md', 'guide draft');
      result.current.remapPath('/docs', '/articles');
    });

    expect(result.current.tabs).toMatchObject([
      {
        path: '/articles/readme.md',
        name: 'readme.md',
        content: 'base',
        originalContent: 'base',
        isModified: false,
      },
      {
        path: '/articles/nested/guide.md',
        name: 'guide.md',
        content: 'guide draft',
        originalContent: 'guide base',
        isModified: true,
      },
    ]);
    expect(result.current.activeTabPath).toBe('/articles/nested/guide.md');
  });

  it('closes exact or descendant tabs for recursive delete flows', () => {
    const onFileClose = vi.fn();
    const { result } = renderHook(() => useFileEditor({ onFileClose }));

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'readme');
      result.current.openTab(createFileNode('/docs/nested/guide.md'), 'guide');
      result.current.openTab(createFileNode('/other/keep.md'), 'keep');
      result.current.closeTabsForPath('/docs', true);
    });

    expect(result.current.tabs.map((tab) => tab.path)).toEqual(['/other/keep.md']);
    expect(result.current.activeTabPath).toBe('/other/keep.md');
    expect(onFileClose).toHaveBeenCalledWith('/docs/readme.md');
    expect(onFileClose).toHaveBeenCalledWith('/docs/nested/guide.md');
  });

  it('tracks version ids across open, save, and revert flows', () => {
    const { result } = renderHook(() => useFileEditor());

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base', 'version-1');
      result.current.updateContent('/docs/readme.md', 'draft');
      result.current.saveTab('/docs/readme.md', 'draft', 'version-2');
      result.current.updateContent('/docs/readme.md', 'draft again');
      result.current.revertTab('/docs/readme.md');
    });

    expect(result.current.tabs[0]).toMatchObject({
      path: '/docs/readme.md',
      content: 'draft',
      originalContent: 'draft',
      isModified: false,
      revision: 'version-2',
    });
  });

  it('keeps newer edits dirty when a pending save resolves with older saved content', () => {
    const { result } = renderHook(() => useFileEditor());

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base', 'version-1');
      result.current.updateContent('/docs/readme.md', 'draft sent to server');
      result.current.updateContent('/docs/readme.md', 'newer draft');
      result.current.saveTab('/docs/readme.md', 'draft sent to server', 'version-2');
    });

    expect(result.current.tabs[0]).toMatchObject({
      content: 'newer draft',
      originalContent: 'draft sent to server',
      isModified: true,
      revision: 'version-2',
    });
  });

  it('keeps newer edits dirty when saveAll resolves with older saved content', () => {
    const { result } = renderHook(() => useFileEditor());

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base', 'version-1');
      result.current.updateContent('/docs/readme.md', 'draft sent to server');
      result.current.updateContent('/docs/readme.md', 'newer draft');
      result.current.saveAllTabs({
        '/docs/readme.md': {
          savedContent: 'draft sent to server',
          revision: 'version-2',
        },
      });
    });

    expect(result.current.tabs[0]).toMatchObject({
      content: 'newer draft',
      originalContent: 'draft sent to server',
      isModified: true,
      revision: 'version-2',
    });
  });

  it('passes the current version id to scheduled auto-save callbacks', () => {
    vi.useFakeTimers();
    const onAutoSave = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useFileEditor({ autoSaveDelay: 100, onAutoSave }));

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base', 'version-1');
    });

    act(() => {
      result.current.updateContent('/docs/readme.md', 'draft');
      vi.advanceTimersByTime(100);
    });

    expect(onAutoSave).toHaveBeenCalledWith('/docs/readme.md', 'draft', 'version-1');
    vi.useRealTimers();
  });

  it('keeps newer auto-save timers after an older auto-save marks saved content', async () => {
    vi.useFakeTimers();
    const firstAutoSave = createDeferred<void>();
    const onAutoSave = vi
      .fn<() => Promise<void>>()
      .mockReturnValueOnce(firstAutoSave.promise)
      .mockResolvedValue(undefined);
    const { result } = renderHook(() => useFileEditor({ autoSaveDelay: 100, onAutoSave }));

    act(() => {
      result.current.openTab(createFileNode('/docs/readme.md'), 'base', 'version-1');
    });

    act(() => {
      result.current.updateContent('/docs/readme.md', 'draft sent to server');
      vi.advanceTimersByTime(100);
    });

    expect(onAutoSave).toHaveBeenCalledTimes(1);
    expect(onAutoSave).toHaveBeenLastCalledWith(
      '/docs/readme.md',
      'draft sent to server',
      'version-1',
    );

    act(() => {
      result.current.updateContent('/docs/readme.md', 'newer draft');
    });

    await act(async () => {
      firstAutoSave.resolve();
      await firstAutoSave.promise;
      result.current.saveTab('/docs/readme.md', 'draft sent to server', 'version-2', {
        clearAutoSaveTimer: false,
      });
    });

    expect(result.current.tabs[0]).toMatchObject({
      content: 'newer draft',
      originalContent: 'draft sent to server',
      isModified: true,
      revision: 'version-2',
    });

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(onAutoSave).toHaveBeenCalledTimes(2);
    expect(onAutoSave).toHaveBeenLastCalledWith('/docs/readme.md', 'newer draft', 'version-2');
    vi.useRealTimers();
  });
});
