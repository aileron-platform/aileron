import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  getBlob: vi.fn(),
  buildUrl: vi.fn((path: string) => `/api/v1${path}`),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

import {
  buildKnowledgeBaseFileDownloadUrl,
  downloadKnowledgeBaseArchiveBlob,
  fetchKnowledgeBaseArchiveDownloadStatus,
  executeKnowledgeBaseFileConflictOperation,
  preflightKnowledgeBaseFileConflicts,
  startKnowledgeBaseArchiveDownload,
} from './knowledgeBaseApi';
import * as knowledgeBaseApi from './knowledgeBaseApi';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

describe('knowledgeBaseApi authorization normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes known allowed operations and filters malformed list entries', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      items: [
        {
          id: 'kb-1',
          accessRole: 'reader',
          accessSource: 'public',
          accessSources: ['public'],
          visibility: 'public',
          allowedOperations: [
            OPERATION_IDS.knowledgeBaseDetailRead,
            'knowledge_base.unknown',
          ],
        },
        {
          id: 'kb-invalid',
          accessRole: 'viewer',
          allowedOperations: [OPERATION_IDS.knowledgeBaseDetailRead],
        },
      ],
    });

    await expect(knowledgeBaseApi.listKnowledgeBases()).resolves.toEqual([
      expect.objectContaining({
        id: 'kb-1',
        accessRole: 'reader',
        accessSource: 'public',
        accessSources: ['public'],
        allowedOperations: [OPERATION_IDS.knowledgeBaseDetailRead],
      }),
    ]);
  });

  it('fails closed when a detail response contains a retired resource role', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      id: 'kb-1',
      accessRole: 'viewer',
      allowedOperations: [OPERATION_IDS.knowledgeBaseDetailRead],
    });

    await expect(knowledgeBaseApi.getKnowledgeBase('kb-1')).rejects.toMatchObject({
      message: 'KB_ACCESS_DENIED',
      errorCode: 'KB_ACCESS_DENIED',
    });
  });

  it('fails closed with a machine-readable code when a create response has no valid access role', async () => {
    apiClientMock.post.mockResolvedValueOnce({
      id: 'kb-1',
      accessRole: null,
      allowedOperations: [],
    });

    await expect(knowledgeBaseApi.createKnowledgeBase({
      name: 'Knowledge Base',
      slug: 'knowledge-base',
    })).rejects.toMatchObject({
      message: 'KB_ACCESS_DENIED',
      errorCode: 'KB_ACCESS_DENIED',
    });
  });
});

describe('knowledgeBaseApi file operations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts a knowledge-base archive download with zip format', async () => {
    apiClientMock.post.mockResolvedValueOnce({ operationId: 'archive-123' });

    const result = await startKnowledgeBaseArchiveDownload('kb-1', {
      paths: ['/docs', '/README.md'],
      archiveName: 'selection.zip',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/archive', {
      paths: ['/docs', '/README.md'],
      archiveName: 'selection.zip',
      archiveFormat: 'zip',
    });
    expect(result.operationId).toBe('archive-123');
  });

  it('fetches knowledge-base archive download status', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      operationId: 'archive-123',
      status: 'completed',
      progress: 1,
      message: 'Archive ready',
      startedAt: '2026-06-10T00:00:00Z',
      result: {
        archiveName: 'selection.zip',
        downloadUrl: '/api/v1/knowledge-bases/kb-1/files/archive/archive-123/download',
        size: 12,
        entryCount: 1,
        expiresAt: '2026-06-10T00:30:00Z',
      },
    });

    const result = await fetchKnowledgeBaseArchiveDownloadStatus('kb-1', 'archive-123');

    expect(apiClientMock.get).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/archive/archive-123');
    expect(result.result?.archiveName).toBe('selection.zip');
  });

  it('downloads knowledge-base archive blobs from backend download URLs', async () => {
    const blob = new Blob(['zip'], { type: 'application/zip' });
    apiClientMock.getBlob.mockResolvedValueOnce(blob);

    const result = await downloadKnowledgeBaseArchiveBlob(
      'kb-1',
      '/api/v1/knowledge-bases/kb-1/files/archive/archive-123/download',
    );

    expect(apiClientMock.getBlob).toHaveBeenCalledWith(
      '/api/v1/knowledge-bases/kb-1/files/archive/archive-123/download',
    );
    expect(result).toBe(blob);
  });

  it('preflights knowledge-base conflicts with the shared request and signal', async () => {
    const signal = new AbortController().signal;
    const request = { operation: 'extract' as const, targetPath: '/docs', sources: null, archivePath: '/docs/sample.zip' };
    apiClientMock.post.mockResolvedValueOnce({ conflicts: [], total: 1 });
    await preflightKnowledgeBaseFileConflicts('kb-1', request, { signal });
    expect(apiClientMock.post).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/conflicts/preflight', request, { signal });
  });

  it('executes knowledge-base extract with explicit cancel strategy and no aliases', async () => {
    const signal = new AbortController().signal;
    apiClientMock.post.mockResolvedValueOnce({ items: [], total: 1, succeeded: 1, skipped: 0, failed: 0 });
    await executeKnowledgeBaseFileConflictOperation('kb-1', {
      operation: 'extract', targetPath: '/docs', sources: null, archivePath: '/docs/sample.zip',
      defaultStrategy: 'cancel', resolutions: [], payload: {},
    }, { signal });
    expect(apiClientMock.post).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/extract', {
      archivePath: '/docs/sample.zip', targetPath: '/docs', defaultStrategy: 'cancel', resolutions: [],
    }, { signal });
  });

  it('builds a single-file download URL', () => {
    expect(buildKnowledgeBaseFileDownloadUrl('kb-1', '/docs/a b.md')).toBe(
      '/api/v1/knowledge-bases/kb-1/files/download?path=%2Fdocs%2Fa%20b.md',
    );
    expect(apiClientMock.buildUrl).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/files/download?path=%2Fdocs%2Fa%20b.md',
    );
  });

});

describe('knowledgeBaseApi shares', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates target-based knowledge-base shares', async () => {
    apiClientMock.post.mockResolvedValueOnce({});

    await knowledgeBaseApi.createKnowledgeBaseShare('kb-1', {
      targetType: 'user_group',
      targetId: 'group-1',
      role: 'reader',
    });

    expect(apiClientMock.post).toHaveBeenCalledWith('/knowledge-bases/kb-1/shares', {
      targetType: 'user_group',
      targetId: 'group-1',
      role: 'reader',
    });
  });

  it('encodes group candidate queries and normalizes the response', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      items: [{ id: 'group-1', name: 'Platform Operations' }],
    });

    const result = await knowledgeBaseApi.searchKnowledgeBaseShareCandidates(
      'kb-1',
      'user_group',
      'platform operations',
    );

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/share-candidate-groups?query=platform%20operations&limit=8',
    );
    expect(result).toEqual([{ id: 'group-1', label: 'Platform Operations' }]);
  });

  it('normalizes user candidates through the knowledge-base API boundary', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      items: [{
        id: 'user-3',
        email: 'candidate@example.com',
        username: 'candidate',
        displayName: 'Candidate User',
      }],
    });

    const result = await knowledgeBaseApi.searchKnowledgeBaseShareCandidates(
      'kb-1',
      'user',
      'candidate@example.com',
    );

    expect(apiClientMock.get).toHaveBeenCalledWith('/users?query=candidate%40example.com&limit=8');
    expect(result).toEqual([{
      id: 'user-3',
      label: 'Candidate User',
      description: 'candidate@example.com · candidate',
    }]);
  });
});

describe('knowledgeBaseApi workspace usage contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns the masked workspace usage projection from the KB read-only endpoint', async () => {
    const response = {
      visibleItems: [
        {
          attachmentId: 'att-1',
          workspaceId: 'ws-1',
          workspaceName: 'Workspace One',
          mountAlias: 'docs',
          attachmentStatus: 'active' as const,
        },
      ],
      hiddenWorkspaceCount: 2,
      attachmentCount: 3,
    };
    apiClientMock.get.mockResolvedValueOnce(response);

    await expect(knowledgeBaseApi.getKnowledgeBaseWorkspaceUsage('kb-1')).resolves.toEqual(response);

    expect(apiClientMock.get).toHaveBeenCalledWith('/knowledge-bases/kb-1/attachments');
  });

  it('deletes a knowledge base with exact-name confirmation', async () => {
    apiClientMock.delete.mockResolvedValueOnce({ id: 'kb-1' });

    await knowledgeBaseApi.deleteKnowledgeBase('kb-1', 'Product Docs');

    expect(apiClientMock.delete).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1',
      undefined,
      { confirmationName: 'Product Docs' },
    );
  });

  it('updates knowledge base visibility through its dedicated operation', async () => {
    apiClientMock.patch.mockResolvedValueOnce({
      id: 'kb-1',
      accessRole: 'owner',
      accessSource: 'owned',
      accessSources: ['owned'],
      visibility: 'public',
      allowedOperations: [OPERATION_IDS.knowledgeBaseDetailRead],
    });

    await expect(knowledgeBaseApi.updateKnowledgeBaseVisibility('kb-1', {
      visibility: 'public',
    })).resolves.toEqual(expect.objectContaining({ visibility: 'public' }));
    expect(apiClientMock.patch).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/visibility',
      { visibility: 'public' },
    );
  });

});
