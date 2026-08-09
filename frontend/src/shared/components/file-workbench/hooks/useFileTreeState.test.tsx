import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { FileTreeNode } from '../types';
import { useFileTreeState } from './useFileTreeState';

describe('useFileTreeState', () => {
  it('removes a nested node without mutating the input tree', () => {
    const removedNode: FileTreeNode = {
      id: '/docs/remove.md',
      name: 'remove.md',
      path: '/docs/remove.md',
      type: 'file',
    };
    const retainedNode: FileTreeNode = {
      id: '/docs/keep.md',
      name: 'keep.md',
      path: '/docs/keep.md',
      type: 'file',
    };
    const originalChildren = [removedNode, retainedNode];
    const parentNode: FileTreeNode = {
      id: '/docs',
      name: 'docs',
      path: '/docs',
      type: 'directory',
      children: originalChildren,
    };
    const initialNodes = [parentNode];
    const { result } = renderHook(() => useFileTreeState({ initialNodes }));

    act(() => result.current.removeNode(removedNode.path));

    expect(result.current.nodes).toEqual([
      { ...parentNode, children: [retainedNode] },
    ]);
    expect(result.current.nodes[0]).not.toBe(parentNode);
    expect(result.current.nodes[0]?.children).not.toBe(originalChildren);
    expect(initialNodes).toEqual([parentNode]);
    expect(parentNode.children).toBe(originalChildren);
    expect(originalChildren).toEqual([removedNode, retainedNode]);
  });
});
