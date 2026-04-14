import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useFileTreeContextMenu } from './useFileTreeContextMenu';

const t = (key: string) => key;

describe('useFileTreeContextMenu', () => {
  it('shows extract action for zip files only', () => {
    const onClose = vi.fn();
    const onExtractArchive = vi.fn();

    const { result: zipResult } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads/demo.zip',
          name: 'demo.zip',
          path: '/uploads/demo.zip',
          type: 'file',
        },
        features: {
          extractArchive: true,
        },
        callbacks: {
          onExtractArchive,
          onClose,
        },
        t,
      })
    );

    expect(zipResult.current.some(item => item.key === 'extract-archive')).toBe(true);

    const { result: textResult } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads/demo.txt',
          name: 'demo.txt',
          path: '/uploads/demo.txt',
          type: 'file',
        },
        features: {
          extractArchive: true,
        },
        callbacks: {
          onExtractArchive,
          onClose,
        },
        t,
      })
    );

    expect(textResult.current.some(item => item.key === 'extract-archive')).toBe(false);
  });
});
