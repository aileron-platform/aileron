import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useFileTreeContextMenu } from './useFileTreeContextMenu';

const t = (key: string) => key;

describe('useFileTreeContextMenu', () => {
  it('shows view and copy-path in read-only mode for files', () => {
    const onClose = vi.fn();
    const onView = vi.fn();
    const onCopyPath = vi.fn();

    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads/demo.txt',
          name: 'demo.txt',
          path: '/uploads/demo.txt',
          type: 'file',
        },
        readOnly: true,
        features: {
          view: true,
          copyPath: true,
        },
        callbacks: {
          onView,
          onCopyPath,
          onClose,
        },
        t,
      })
    );

    expect(result.current.map(item => item.key)).toEqual(['view', 'copy-path']);
  });

  it('shows view and copy-path in read-only mode for directories when enabled', () => {
    const onClose = vi.fn();
    const onView = vi.fn();
    const onCopyPath = vi.fn();

    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads',
          name: 'uploads',
          path: '/uploads',
          type: 'directory',
        },
        readOnly: true,
        features: {
          view: true,
          copyPath: true,
        },
        callbacks: {
          onView,
          onCopyPath,
          onClose,
        },
        t,
      })
    );

    expect(result.current.map(item => item.key)).toEqual(['view', 'copy-path']);
  });

  it('shows copy-path and refresh in read-only mode when enabled', () => {
    const onClose = vi.fn();
    const onCopyPath = vi.fn();
    const onRefresh = vi.fn();

    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads',
          name: 'uploads',
          path: '/uploads',
          type: 'directory',
        },
        readOnly: true,
        features: {
          copyPath: true,
          refresh: true,
        },
        callbacks: {
          onCopyPath,
          onRefresh,
          onClose,
        },
        t,
      })
    );

    expect(result.current.map(item => item.key)).toEqual(['copy-path', 'refresh']);
  });

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
