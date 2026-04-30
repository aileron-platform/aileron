import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useFileEditor } from './useFileEditor';
import type { FileTreeNode } from '../types';

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
});
