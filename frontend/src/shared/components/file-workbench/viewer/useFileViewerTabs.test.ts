import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '../types';
import { useFileViewerTabs } from './useFileViewerTabs';

const buildNode = (path: string, name?: string): FileTreeNode => ({
  id: path,
  name: name ?? path.split('/').pop() ?? path,
  path,
  type: 'file',
});

describe('useFileViewerTabs', () => {
  it('opens a file as a new tab and activates it', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
    });

    expect(result.current.tabs).toHaveLength(1);
    expect(result.current.tabs[0]).toMatchObject({
      id: '/pkg/a.md',
      path: '/pkg/a.md',
      name: 'a.md',
      content: 'A',
      originalContent: 'A',
      isModified: false,
    });
    expect(result.current.activeTabId).toBe('/pkg/a.md');
  });

  it('reactivates an existing tab without duplicating', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
      result.current.openFile(buildNode('/pkg/b.md'), 'B');
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
    });

    expect(result.current.tabs.map(tab => tab.id)).toEqual(['/pkg/a.md', '/pkg/b.md']);
    expect(result.current.activeTabId).toBe('/pkg/a.md');
  });

  it('falls back to the last tab when active tab is removed via tabs change', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
      result.current.openFile(buildNode('/pkg/b.md'), 'B');
      result.current.openFile(buildNode('/pkg/c.md'), 'C');
    });

    act(() => {
      result.current.applyTabsChange(result.current.tabs.filter(tab => tab.id !== '/pkg/c.md'));
    });

    expect(result.current.activeTabId).toBe('/pkg/b.md');
    expect(result.current.tabs.map(tab => tab.id)).toEqual(['/pkg/a.md', '/pkg/b.md']);
  });

  it('preserves incoming tab order when applying tabs change', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
      result.current.openFile(buildNode('/pkg/b.md'), 'B');
      result.current.openFile(buildNode('/pkg/c.md'), 'C');
    });

    const reordered = [
      result.current.tabs[2],
      result.current.tabs[0],
      result.current.tabs[1],
    ];

    act(() => {
      result.current.applyTabsChange(reordered);
    });

    expect(result.current.tabs.map(tab => tab.id)).toEqual([
      '/pkg/c.md',
      '/pkg/a.md',
      '/pkg/b.md',
    ]);
    expect(result.current.activeTabId).toBe('/pkg/c.md');
  });

  it('clears active tab id when last tab is closed', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
    });

    act(() => {
      result.current.applyTabsChange([]);
    });

    expect(result.current.tabs).toHaveLength(0);
    expect(result.current.activeTabId).toBeNull();
  });

  it('renames matching tab id, path and name and preserves active tab id when active tab renamed', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/folder/b.md'), 'B');
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
    });

    act(() => {
      result.current.renamePath('/pkg/a.md', '/pkg/renamed.md', 'renamed.md');
    });

    const renamedTab = result.current.tabs.find(tab => tab.id === '/pkg/renamed.md');
    expect(renamedTab).toMatchObject({
      id: '/pkg/renamed.md',
      path: '/pkg/renamed.md',
      name: 'renamed.md',
    });
    expect(result.current.activeTabId).toBe('/pkg/renamed.md');
  });

  it('renames descendant tab paths when a directory is renamed', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/folder/a.md'), 'A');
      result.current.openFile(buildNode('/pkg/folder/sub/b.md'), 'B');
    });

    act(() => {
      result.current.renamePath('/pkg/folder', '/pkg/folder-2', 'folder-2');
    });

    expect(result.current.tabs.map(tab => tab.path)).toEqual([
      '/pkg/folder-2/a.md',
      '/pkg/folder-2/sub/b.md',
    ]);
    expect(result.current.activeTabId).toBe('/pkg/folder-2/sub/b.md');
  });

  it('removes tabs and clears active id when paths are deleted', () => {
    const { result } = renderHook(() => useFileViewerTabs());

    act(() => {
      result.current.openFile(buildNode('/pkg/a.md'), 'A');
      result.current.openFile(buildNode('/pkg/folder/b.md'), 'B');
      result.current.openFile(buildNode('/pkg/folder/c.md'), 'C');
    });

    act(() => {
      result.current.removePaths(['/pkg/folder']);
    });

    expect(result.current.tabs.map(tab => tab.id)).toEqual(['/pkg/a.md']);
    expect(result.current.activeTabId).toBeNull();
  });
});
