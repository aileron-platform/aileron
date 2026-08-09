import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WORKSPACE_FILE_REFERENCE_MIME } from '../dragPayload';
import { FileTreePanel } from './FileTreePanel';
import type { UseFileTreeStateReturn } from '../hooks/useFileTreeState';
import type { FileTreeNode } from '../types';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => values?.count ? `${key}:${values.count}` : key,
  }),
}));

const nodes: FileTreeNode[] = [
  { id: 'selected', name: 'selected.md', path: '/selected.md', type: 'file' },
  { id: 'other', name: 'other.md', path: '/other.md', type: 'file' },
  { id: 'idle', name: 'idle.md', path: '/idle.md', type: 'file' },
];

const createState = (overrides: Partial<UseFileTreeStateReturn> = {}): UseFileTreeStateReturn => ({
  nodes,
  selectedId: '/selected.md',
  selectedIds: new Set(['/selected.md', '/other.md']),
  lastSelectedId: '/other.md',
  expandedIds: new Set(),
  isLoading: false,
  error: null,
  searchQuery: '',
  contextMenu: null,
  visibleNodes: nodes,
  filteredNodes: nodes,
  flatNodes: nodes,
  selectedNodes: nodes,
  hasSelection: true,
  isSearching: false,
  setNodes: vi.fn(),
  updateNode: vi.fn(),
  removeNode: vi.fn(),
  addNode: vi.fn(),
  resetState: vi.fn(),
  selectNode: vi.fn(),
  selectNodeWithModifier: vi.fn(),
  selectAll: vi.fn(),
  clearSelection: vi.fn(),
  isNodeSelected: vi.fn(),
  isNodeMultiSelected: vi.fn(),
  expandNode: vi.fn(),
  collapseNode: vi.fn(),
  toggleNode: vi.fn(),
  expandAll: vi.fn(),
  collapseAll: vi.fn(),
  isNodeExpanded: vi.fn(),
  syncExpandedWithLoaded: vi.fn(),
  replaceExpandedIds: vi.fn(),
  setSearchQuery: vi.fn(),
  clearSearch: vi.fn(),
  setLoading: vi.fn(),
  setError: vi.fn(),
  openContextMenu: vi.fn(),
  closeContextMenu: vi.fn(),
  ...overrides,
});

describe('FileTreePanel', () => {
  it('keeps existing rows visible while refreshing the tree', () => {
    render(
      <FileTreePanel
        state={createState({ isLoading: true })}
        enableSearch={false}
        enableToolbar={false}
        enableMultiSelectBar={false}
      />,
    );

    expect(screen.getByTitle('/selected.md')).toBeInTheDocument();
    expect(screen.getByTitle('/other.md')).toBeInTheDocument();
  });

  it('does not apply hover background to multi-selected rows', () => {
    render(
      <FileTreePanel
        state={createState()}
        enableSearch={false}
        enableToolbar={false}
        enableMultiSelectBar={false}
      />,
    );

    expect(screen.getByTitle('/selected.md')).toHaveClass('bg-primary/20');
    expect(screen.getByTitle('/selected.md')).not.toHaveClass('hover:bg-muted/40');
    expect(screen.getByTitle('/idle.md')).toHaveClass('hover:bg-muted/40');
  });

  it('adds a workspace file reference payload when dragging a file row', () => {
    const dataTransfer = {
      effectAllowed: '',
      setData: vi.fn(),
    };

    render(
      <FileTreePanel
        state={createState()}
        enableSearch={false}
        enableToolbar={false}
        enableMultiSelectBar={false}
      />,
    );

    fireEvent.dragStart(screen.getByTitle('/selected.md'), { dataTransfer });

    expect(dataTransfer.setData).toHaveBeenCalledWith(
      WORKSPACE_FILE_REFERENCE_MIME,
      './selected.md',
    );
  });
});
