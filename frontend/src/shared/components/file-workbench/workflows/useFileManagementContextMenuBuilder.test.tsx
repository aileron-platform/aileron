import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useFileManagementContextMenuBuilder } from './useFileManagementContextMenuBuilder';

const useFileTreeContextMenuMock = vi.hoisted(() => vi.fn(() => []));

vi.mock('../hooks/useFileTreeContextMenu', () => ({
  useFileTreeContextMenu: useFileTreeContextMenuMock,
}));

describe('useFileManagementContextMenuBuilder', () => {
  it('fills shared multi-select and clipboard defaults before delegating', () => {
    const selectedIds = new Set(['/docs/readme.md', '/docs/guide.md']);
    const node = {
      id: '/docs/readme.md',
      name: 'readme.md',
      path: '/docs/readme.md',
      type: 'file' as const,
    };
    const onClose = vi.fn();
    const t = vi.fn((key: string) => key);

    renderHook(() => useFileManagementContextMenuBuilder({
      node,
      selectedIds,
      clipboardItem: { path: '/docs/readme.md' },
      features: {
        open: true,
      },
      callbacks: {
        onClose,
      },
      t,
    }));

    expect(useFileTreeContextMenuMock).toHaveBeenCalledWith(expect.objectContaining({
      node,
      enableMultiSelect: true,
      selectedCount: 2,
      selectedIds,
      hasClipboard: true,
      features: {
        open: true,
      },
      callbacks: {
        onClose,
      },
      t,
    }));
  });
});
