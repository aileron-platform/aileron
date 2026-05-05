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

  it('shows download action for a single file', () => {
    const onClose = vi.fn();
    const onDownload = vi.fn();

    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads/demo.txt',
          name: 'demo.txt',
          path: '/uploads/demo.txt',
          type: 'file',
        },
        features: {
          download: true,
        },
        callbacks: {
          onDownload,
          onClose,
        },
        t,
      })
    );

    const item = result.current.find(action => action.key === 'download');
    expect(item?.label).toBe('common.fileTree.contextMenu.download');
    item?.onSelect();
    expect(onDownload).toHaveBeenCalledWith(expect.objectContaining({ path: '/uploads/demo.txt' }), ['/uploads/demo.txt']);
  });

  it('shows ZIP download label for a directory', () => {
    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/uploads',
          name: 'uploads',
          path: '/uploads',
          type: 'directory',
        },
        features: {
          download: true,
        },
        callbacks: {
          onDownload: vi.fn(),
          onClose: vi.fn(),
        },
        t,
      })
    );

    expect(result.current.find(action => action.key === 'download')?.label)
      .toBe('common.fileTree.contextMenu.downloadAsZip');
  });

  it('passes selected paths for multi-select download', () => {
    const onDownload = vi.fn();
    const selectedIds = new Set(['/a.txt', '/b.txt']);

    const { result } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: '/a.txt',
          name: 'a.txt',
          path: '/a.txt',
          type: 'file',
        },
        enableMultiSelect: true,
        selectedCount: 2,
        selectedIds,
        features: {
          download: true,
        },
        callbacks: {
          onDownload,
          onClose: vi.fn(),
        },
        t,
      })
    );

    const item = result.current.find(action => action.key === 'download');
    expect(item?.label).toBe('common.fileTree.contextMenu.downloadSelected');
    item?.onSelect();
    expect(onDownload).toHaveBeenCalledWith(expect.objectContaining({ path: '/a.txt' }), ['/a.txt', '/b.txt']);
  });

  it('keeps write actions enabled by default and disables them when the writable rule rejects the node', () => {
    const callbacks = {
      onUpload: vi.fn(),
      onCreateFile: vi.fn(),
      onCreateFolder: vi.fn(),
      onCopy: vi.fn(),
      onPaste: vi.fn(),
      onRename: vi.fn(),
      onDelete: vi.fn(),
      onClose: vi.fn(),
    };

    const { result: defaultResult } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: 'b/x.md',
          name: 'x.md',
          path: 'b/x.md',
          type: 'directory',
        },
        hasClipboard: true,
        callbacks,
        t,
      })
    );

    expect(defaultResult.current.filter(item => item.disabled).map(item => item.key)).toEqual([]);

    const { result: rejectedResult } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: 'b/x.md',
          name: 'x.md',
          path: 'b/x.md',
          type: 'directory',
        },
        hasClipboard: true,
        isPathWritable: path => path.startsWith('a/'),
        callbacks,
        t,
      })
    );

    expect(rejectedResult.current.filter(item => item.disabled).map(item => item.key)).toEqual([
      'upload',
      'create-folder',
      'create-file',
      'copy',
      'paste',
      'rename',
      'delete',
    ]);

    const { result: acceptedResult } = renderHook(() =>
      useFileTreeContextMenu({
        node: {
          id: 'a/x.md',
          name: 'x.md',
          path: 'a/x.md',
          type: 'directory',
        },
        hasClipboard: true,
        isPathWritable: path => path.startsWith('a/'),
        callbacks,
        t,
      })
    );

    expect(acceptedResult.current.filter(item => item.disabled).map(item => item.key)).toEqual([]);
  });
});
