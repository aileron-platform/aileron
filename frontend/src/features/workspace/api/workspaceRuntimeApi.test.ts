import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

const { clientGetMock, clientGetBlobMock, patchMock, deleteMock } = vi.hoisted(() => ({
  clientGetMock: vi.fn(),
  clientGetBlobMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  registerCsrfTokenProvider: vi.fn(),
  registerExecutionGrantProvider: vi.fn(),
  registerExecutionGrantRejectionHandler: vi.fn(),
  apiClient: {
    get: getMock,
  },
  ApiClient: class {
    post = postMock;
    get = clientGetMock;
    getBlob = clientGetBlobMock;
    patch = patchMock;
    delete = deleteMock;
  },
}));

import {
  fetchFileContent,
  fetchArchiveDownloadStatus,
  createCanvasReviewNote,
  deleteCanvasReviewNote,
  fetchCanvasReviewNotes,
  fetchDefaultWorkspaceId,
  resolveRuntimeBaseUrlWithDetail,
  startArchiveDownload,
  preflightRuntimeFileConflicts,
  executeRuntimeFileConflictOperation,
  buildArchiveDownloadUrl,
  downloadFile,
  downloadArchiveBlob,
  updateCanvasReviewNoteStatus,
} from './workspaceRuntimeApi';

describe('workspaceRuntimeApi.resolveRuntimeBaseUrlWithDetail', () => {
  const workspaceId = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';

  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    clientGetMock.mockReset();
    clientGetBlobMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
  });

  it('loads the default workspace through the canonical collection route', async () => {
    getMock.mockResolvedValue({
      items: [{ id: 'ws-1', name: 'Workspace 1' }],
    });

    await expect(fetchDefaultWorkspaceId()).resolves.toBe('ws-1');

    expect(getMock).toHaveBeenCalledWith('/workspaces?page=1&pageSize=1');
  });

  it('derives the Runtime base path from the workspace identity', async () => {
    const runtimeUrl = `/workspaces/${workspaceId}/runtime`;
    getMock.mockResolvedValue({
      runtimeStatus: {
        status: 'running',
        runtimeUrl,
        browserUrl: `/workspaces/${workspaceId}/browser`,
        canvasUrl: `/workspaces/${workspaceId}/canvas`,
      },
    });

    const result = await resolveRuntimeBaseUrlWithDetail(workspaceId);

    expect(result.url).toBe(runtimeUrl);
  });

  it('returns no Runtime URL while the Runtime is stopped', async () => {
    const runtimeUrl = `/workspaces/${workspaceId}/runtime`;
    const detail = {
      id: workspaceId,
      runtimeStatus: {
        status: 'stopped',
        runtimeUrl,
        browserUrl: `/workspaces/${workspaceId}/browser`,
        canvasUrl: `/workspaces/${workspaceId}/canvas`,
      },
    };
    getMock.mockResolvedValue({
      ...detail,
    });

    const result = await resolveRuntimeBaseUrlWithDetail(workspaceId);

    expect(result).toEqual({
      url: null,
      detail,
    });
  });

  it('propagates workspace detail failures without a URL cache fallback', async () => {
    getMock.mockRejectedValue(new Error('Network unavailable'));

    await expect(resolveRuntimeBaseUrlWithDetail(workspaceId)).rejects.toThrow(
      'Network unavailable',
    );
  });

  it('preflights workspace conflicts with context id and abort signal', async () => {
    const signal = new AbortController().signal;
    const request = { operation: 'upload' as const, targetPath: '/uploads', sources: [{ sourcePath: 'demo.zip', entryType: 'file' as const }], archivePath: null };
    postMock.mockResolvedValue({ conflicts: [], total: 1 });
    await preflightRuntimeFileConflicts('http://runtime.local', request, { signal, contextId: 'worktree:feature-auth' });
    expect(postMock).toHaveBeenCalledWith('/api/v1/files/conflicts/preflight?contextId=worktree%3Afeature-auth', request, { signal });
  });

  it('executes workspace upload with explicit cancel strategy and canonical batch result', async () => {
    const signal = new AbortController().signal;
    const file = new File(['zip'], 'demo.zip');
    postMock.mockResolvedValue({ items: [], total: 1, succeeded: 1, skipped: 0, failed: 0 });
    await executeRuntimeFileConflictOperation('http://runtime.local', {
      operation: 'upload', targetPath: '/uploads', sources: [{ sourcePath: file.name, entryType: 'file' }], archivePath: null,
      defaultStrategy: 'cancel', resolutions: [], payload: { files: [file], contextId: 'worktree:feature-auth' },
    }, { signal });
    const [path, formData, options] = postMock.mock.calls[0] as [string, FormData, { signal: AbortSignal }];
    expect(path).toBe('/api/v1/files/upload?contextId=worktree%3Afeature-auth');
    expect(formData.get('defaultStrategy')).toBe('cancel');
    expect(formData.get('resolutions')).toBe('[]');
    expect(options).toEqual({ signal });
  });

  it('\u6703\u628a contextId \u5e36\u5230\u6a94\u6848\u5167\u5bb9\u8acb\u6c42', async () => {
    clientGetMock.mockResolvedValue({ content: 'hello' });

    await fetchFileContent('http://runtime.local', '/README.md', 'worktree:feature-auth');

    expect(clientGetMock).toHaveBeenCalledWith(
      '/api/v1/files/content?path=%2FREADME.md&contextId=worktree%3Afeature-auth',
    );
  });

  it('starts an archive download operation with context id', async () => {
    postMock.mockResolvedValue({
      operationId: 'archive-123',
      status: 'pending',
      message: 'Preparing ZIP download...',
      startedAt: '2026-01-01T00:00:00Z',
    });

    const result = await startArchiveDownload('http://runtime.local', {
      paths: ['/src', '/README.md'],
      archiveName: 'selection.zip',
      contextId: 'worktree:feature-auth',
    });

    expect(postMock).toHaveBeenCalledWith('/api/v1/files/archive?contextId=worktree%3Afeature-auth', {
      paths: ['/src', '/README.md'],
      archiveName: 'selection.zip',
      archiveFormat: 'zip',
    });
    expect(result.operationId).toBe('archive-123');
  });

  it('fetches archive download status', async () => {
    clientGetMock.mockResolvedValue({
      operationId: 'archive-123',
      status: 'completed',
      progress: 1,
      message: 'Archive ready',
      startedAt: '2026-01-01T00:00:00Z',
      result: {
        archiveName: 'selection.zip',
        size: 123,
        downloadUrl: '/api/v1/files/archive/archive-123/download',
        expiresAt: '2026-01-01T00:30:00Z',
      },
    });

    const result = await fetchArchiveDownloadStatus('http://runtime.local', 'archive-123');

    expect(clientGetMock).toHaveBeenCalledWith('/api/v1/files/archive/archive-123');
    expect(result.result?.archiveName).toBe('selection.zip');
  });

  it('builds archive download URLs from API paths', () => {
    expect(buildArchiveDownloadUrl('http://runtime.local', '/api/v1/files/archive/archive-123/download'))
      .toBe('http://runtime.local/api/v1/files/archive/archive-123/download');
  });

  it('builds a same-origin relative archive download URL from a relative Runtime base path', () => {
    expect(buildArchiveDownloadUrl(
      `/workspaces/${workspaceId}/runtime`,
      '/api/v1/files/archive/archive-123/download',
    )).toBe(
      `/workspaces/${workspaceId}/runtime/api/v1/files/archive/archive-123/download`,
    );
  });

  it('builds a same-origin relative file download URL from a relative Runtime base path', async () => {
    await expect(downloadFile(
      `/workspaces/${workspaceId}/runtime`,
      '/README.md',
      'worktree:feature-auth',
    )).resolves.toBe(
      `/workspaces/${workspaceId}/runtime/api/v1/files/download?path=%2FREADME.md&contextId=worktree%3Afeature-auth`,
    );
  });

  it('preserves absolute Runtime bases when building file download URLs', async () => {
    await expect(downloadFile(
      'https://runtime.example.com/workspace',
      '/README.md',
    )).resolves.toBe(
      'https://runtime.example.com/workspace/api/v1/files/download?path=%2FREADME.md',
    );
  });

  it('downloads archive with authenticated blob request', async () => {
    clientGetBlobMock.mockResolvedValue(new Blob(['zip-content'], { type: 'application/zip' }));

    await downloadArchiveBlob('http://runtime.local', '/api/v1/files/archive/archive-123/download');
    expect(clientGetBlobMock).toHaveBeenCalledWith('/api/v1/files/archive/archive-123/download');
  });

  it('\u6703\u547c\u53eb Canvas review note API', async () => {
    clientGetMock.mockResolvedValue({ workspaceId: 'ws-1', notes: [], total: 0 });
    postMock.mockResolvedValue({ id: 'note-1', status: 'open' });
    patchMock.mockResolvedValue({ id: 'note-1', status: 'seen' });
    deleteMock.mockResolvedValue(undefined);

    await fetchCanvasReviewNotes('http://runtime.local', 'ws-1', {
      status: 'open',
      routePath: '/',
    });
    await createCanvasReviewNote('http://runtime.local', 'ws-1', {
      routePath: '/',
      canvasUrl: 'http://canvas.local/',
      instruction: 'Move it',
      target: {
        type: 'area',
        rect: { x: 0, y: 0, width: 100, height: 80, coordinateSpace: 'viewport' },
      },
    });
    await updateCanvasReviewNoteStatus('http://runtime.local', 'ws-1', 'note-1', 'seen');
    await deleteCanvasReviewNote('http://runtime.local', 'ws-1', 'note-1');

    expect(clientGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/canvas/review-notes?status=open&routePath=%2F',
    );
    expect(postMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/canvas/review-notes', expect.any(Object));
    expect(patchMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/canvas/review-notes/note-1/status',
      { status: 'seen' },
    );
    expect(deleteMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/canvas/review-notes/note-1');
  });
});
