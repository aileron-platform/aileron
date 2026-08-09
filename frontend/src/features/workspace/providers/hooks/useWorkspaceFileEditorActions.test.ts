import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FileTreeActions } from '../../features/file-management/model/fileManagementTypes';
import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';
import { FILE_EDITOR_ERROR_KEYS } from '../workspaceProviderModel';
import { useWorkspaceFileEditorActions } from './useWorkspaceFileEditorActions';

const createFileManagementState = (
  overrides: Partial<WorkspaceState['fileManagement']> = {},
): WorkspaceState['fileManagement'] => ({
  selectedFile: null,
  openTabs: [],
  activeTabId: null,
  modifiedTabs: [],
  originalContents: {},
  revisions: {},
  mermaidCanvasMode: {},
  markdownCanvasMode: {},
  ...overrides,
});

const createFileTreeActions = () => ({
  saveFileContent: vi.fn(),
  readFileContent: vi.fn(),
}) as unknown as FileTreeActions;

const renderActions = (
  fileManagement: WorkspaceState['fileManagement'],
  fileTreeActions = createFileTreeActions(),
) => {
  const dispatch = vi.fn<(action: WorkspaceAction) => void>();
  const rendered = renderHook(() => useWorkspaceFileEditorActions({
    fileManagement,
    fileTreeActions,
    dispatch,
  }));

  return { ...rendered, dispatch, fileTreeActions };
};

describe('useWorkspaceFileEditorActions', () => {
  it('opens a new file and refreshes an existing tab without changing the public action contract', () => {
    const newFile = renderActions(createFileManagementState());

    act(() => {
      newFile.result.current.openFileInTab('/docs/new.md', '# New');
    });

    expect(newFile.dispatch.mock.calls.map(([action]) => action)).toEqual([
      {
        type: 'OPEN_FILE_TAB',
        payload: {
          id: '/docs/new.md',
          name: 'new.md',
          path: '/docs/new.md',
          content: '# New',
        },
      },
      {
        type: 'SET_ORIGINAL_CONTENT',
        payload: {
          tabId: '/docs/new.md',
          content: '# New',
        },
      },
    ]);

    const existingFile = renderActions(createFileManagementState({
      openTabs: [{
        id: '/docs/guide.md',
        name: 'guide.md',
        path: '/docs/guide.md',
        content: '# Old',
      }],
    }));

    act(() => {
      existingFile.result.current.openFileInTab('/docs/guide.md', '# Refreshed');
    });

    expect(existingFile.dispatch.mock.calls.map(([action]) => action)).toEqual([
      {
        type: 'SET_ACTIVE_TAB',
        payload: { tabId: '/docs/guide.md' },
      },
      {
        type: 'UPDATE_TAB_CONTENT',
        payload: {
          tabId: '/docs/guide.md',
          content: '# Refreshed',
        },
      },
    ]);
  });

  it('saves the current tab with its revision and clears the modified state', async () => {
    const fileTreeActions = createFileTreeActions();
    vi.mocked(fileTreeActions.saveFileContent).mockResolvedValue({
      success: true,
      message: 'saved',
      revision: 'revision-2',
    });
    const rendered = renderActions(createFileManagementState({
      openTabs: [{
        id: '/docs/guide.md',
        name: 'guide.md',
        path: '/docs/guide.md',
        content: '# Updated',
      }],
      modifiedTabs: ['/docs/guide.md'],
      revisions: { '/docs/guide.md': 'revision-1' },
    }), fileTreeActions);

    let saveResult: Awaited<ReturnType<typeof rendered.result.current.saveFile>> | undefined;
    await act(async () => {
      saveResult = await rendered.result.current.saveFile('/docs/guide.md');
    });

    expect(saveResult).toEqual({ success: true });
    expect(fileTreeActions.saveFileContent).toHaveBeenCalledWith(
      '/docs/guide.md',
      '# Updated',
      'revision-1',
    );
    expect(rendered.dispatch.mock.calls.map(([action]) => action)).toEqual([
      {
        type: 'SET_ORIGINAL_CONTENT',
        payload: {
          tabId: '/docs/guide.md',
          content: '# Updated',
        },
      },
      {
        type: 'SET_FILE_VERSION_ID',
        payload: {
          tabId: '/docs/guide.md',
          revision: 'revision-2',
        },
      },
      {
        type: 'SET_TAB_MODIFIED',
        payload: {
          tabId: '/docs/guide.md',
          isModified: false,
        },
      },
    ]);
  });

  it('reports missing and failed saves with the existing i18n error keys', async () => {
    const missing = renderActions(createFileManagementState());

    await expect(missing.result.current.saveFile('/missing.md')).resolves.toEqual({
      success: false,
      error: FILE_EDITOR_ERROR_KEYS.saveFileMissing,
    });

    const fileTreeActions = createFileTreeActions();
    vi.mocked(fileTreeActions.saveFileContent).mockResolvedValue({
      success: false,
      message: '',
    });
    const failed = renderActions(createFileManagementState({
      openTabs: [{
        id: '/docs/guide.md',
        name: 'guide.md',
        path: '/docs/guide.md',
        content: '# Updated',
      }],
    }), fileTreeActions);

    await expect(failed.result.current.saveFile('/docs/guide.md')).resolves.toEqual({
      success: false,
      error: FILE_EDITOR_ERROR_KEYS.saveFailed,
    });
  });

  it('saves only modified tabs and reports individual failures', async () => {
    const fileTreeActions = createFileTreeActions();
    vi.mocked(fileTreeActions.saveFileContent)
      .mockResolvedValueOnce({ success: true, message: 'saved', revision: 'revision-a2' })
      .mockResolvedValueOnce({ success: false, message: 'conflict' });
    const rendered = renderActions(createFileManagementState({
      openTabs: [
        { id: '/a.md', name: 'a.md', path: '/a.md', content: 'A' },
        { id: '/b.md', name: 'b.md', path: '/b.md', content: 'B' },
        { id: '/clean.md', name: 'clean.md', path: '/clean.md', content: 'Clean' },
      ],
      modifiedTabs: ['/a.md', '/b.md'],
    }), fileTreeActions);

    let saveResult: Awaited<ReturnType<typeof rendered.result.current.saveAllFiles>> | undefined;
    await act(async () => {
      saveResult = await rendered.result.current.saveAllFiles();
    });

    expect(saveResult).toEqual({ success: false, failed: ['/b.md'] });
    expect(fileTreeActions.saveFileContent).toHaveBeenCalledTimes(2);
    expect(fileTreeActions.saveFileContent).not.toHaveBeenCalledWith(
      '/clean.md',
      expect.anything(),
      expect.anything(),
    );
  });

  it('reloads and reverts files while preserving failure behavior', async () => {
    const fileTreeActions = createFileTreeActions();
    vi.mocked(fileTreeActions.readFileContent).mockResolvedValue({
      content: '# Server',
      encoding: 'utf-8',
      size: 8,
      lastModified: '2026-07-16T00:00:00Z',
      revision: 'revision-3',
    });
    const rendered = renderActions(createFileManagementState({
      openTabs: [
        { id: '/a.md', name: 'a.md', path: '/a.md', content: '# Local A' },
        { id: '/b.md', name: 'b.md', path: '/b.md', content: '# Local B' },
      ],
      activeTabId: '/a.md',
      modifiedTabs: ['/a.md', '/b.md'],
      originalContents: { '/a.md': '# Original A' },
    }), fileTreeActions);

    let reloadResult: Awaited<ReturnType<typeof rendered.result.current.reloadCurrentFile>> | undefined;
    await act(async () => {
      reloadResult = await rendered.result.current.reloadCurrentFile();
    });

    expect(reloadResult).toEqual({ success: true });
    expect(rendered.dispatch.mock.calls.map(([action]) => action)).toEqual([
      {
        type: 'UPDATE_TAB_CONTENT',
        payload: { tabId: '/a.md', content: '# Server' },
      },
      {
        type: 'SET_ORIGINAL_CONTENT',
        payload: { tabId: '/a.md', content: '# Server' },
      },
      {
        type: 'SET_FILE_VERSION_ID',
        payload: { tabId: '/a.md', revision: 'revision-3' },
      },
      {
        type: 'SET_TAB_MODIFIED',
        payload: { tabId: '/a.md', isModified: false },
      },
    ]);

    rendered.dispatch.mockClear();
    act(() => {
      expect(rendered.result.current.revertAllFiles()).toEqual({
        success: false,
        failed: ['/b.md'],
      });
    });
    expect(rendered.dispatch.mock.calls.map(([action]) => action)).toEqual([
      {
        type: 'UPDATE_TAB_CONTENT',
        payload: { tabId: '/a.md', content: '# Original A' },
      },
      {
        type: 'SET_TAB_MODIFIED',
        payload: { tabId: '/a.md', isModified: false },
      },
    ]);
  });
});
