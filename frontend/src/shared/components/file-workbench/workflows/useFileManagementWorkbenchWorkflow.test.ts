import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FileTreeNode } from '../types';
import { useFileManagementWorkbenchWorkflow } from './useFileManagementWorkbenchWorkflow';

const buildNode = (
  path: string,
  type: 'file' | 'directory',
  children?: FileTreeNode[],
): FileTreeNode => ({
  id: path,
  name: path.split('/').pop() || path,
  path,
  type,
  children,
});

describe('useFileManagementWorkbenchWorkflow', () => {
  it('selects files, opens them on plain click, and keeps a flat node ref in sync', () => {
    const onOpenFile = vi.fn();
    const initialNodes = [
      buildNode('/docs', 'directory', [
        buildNode('/docs/readme.md', 'file'),
      ]),
    ];

    const { result } = renderHook(() => useFileManagementWorkbenchWorkflow({
      initialNodes,
      initialSelectedId: '/docs/readme.md',
      enableMultiSelect: true,
      onOpenFile,
    }));

    act(() => {
      result.current.handleNodeClick(initialNodes[0].children![0], 'none');
    });

    expect(result.current.treeState.selectedId).toBe('/docs/readme.md');
    expect(onOpenFile).toHaveBeenCalledWith(initialNodes[0].children![0]);
    expect(result.current.flatNodesRef.current.map(node => node.path)).toEqual([
      '/docs',
      '/docs/readme.md',
    ]);
  });

  it('does not open a file tab for modified selection clicks and toggles directories on double click', () => {
    const onOpenFile = vi.fn();
    const fileNode = buildNode('/docs/readme.md', 'file');
    const directoryNode = buildNode('/docs', 'directory', [fileNode]);

    const { result } = renderHook(() => useFileManagementWorkbenchWorkflow({
      initialNodes: [directoryNode],
      enableMultiSelect: true,
      onOpenFile,
    }));

    act(() => {
      result.current.handleNodeClick(fileNode, 'ctrl');
    });

    expect(onOpenFile).not.toHaveBeenCalled();

    act(() => {
      result.current.handleNodeDoubleClick(directoryNode);
    });

    expect(result.current.treeState.expandedIds.has('/docs')).toBe(true);

    act(() => {
      result.current.handleNodeDoubleClick(directoryNode);
    });

    expect(result.current.treeState.expandedIds.has('/docs')).toBe(false);
  });

  it('opens the context menu with the clicked node metadata', () => {
    const fileNode = buildNode('/docs/readme.md', 'file');
    const { result } = renderHook(() => useFileManagementWorkbenchWorkflow({
      initialNodes: [fileNode],
      onOpenFile: vi.fn(),
    }));

    act(() => {
      result.current.handleContextMenu(fileNode, {
        clientX: 12,
        clientY: 34,
      } as React.MouseEvent);
    });

    expect(result.current.treeState.contextMenu).toMatchObject({
      x: 12,
      y: 34,
      node: fileNode,
    });
  });
});
