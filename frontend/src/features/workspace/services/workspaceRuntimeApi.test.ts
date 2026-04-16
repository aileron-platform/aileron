import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

const { clientGetMock } = vi.hoisted(() => ({
  clientGetMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: getMock,
  },
  ApiClient: class {
    post = postMock;
    get = clientGetMock;
  },
}));

import {
  fetchFileContent,
  fetchFileTree,
  fetchNodeChildren,
  fetchExtractArchiveStatus,
  resolveRuntimeBaseUrl,
  startExtractArchive,
  uploadFiles,
} from './workspaceRuntimeApi';

describe('workspaceRuntimeApi.resolveRuntimeBaseUrl', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    clientGetMock.mockReset();
  });

  it('在 Kubernetes public routing 下優先使用 externalUrl', async () => {
    getMock.mockResolvedValue({
      runtimeStatus: {
        externalUrl: 'https://workspace-runtime-ws-1.example.com',
        internalUrl: 'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002',
      },
    });

    const cache = new Map<string, string>();
    const result = await resolveRuntimeBaseUrl('ws-1', cache);

    expect(result).toBe('https://workspace-runtime-ws-1.example.com');
    expect(cache.get('ws-1')).toBe('https://workspace-runtime-ws-1.example.com');
  });

  it('只有 internalUrl 時才回退到 internal service URL', async () => {
    getMock.mockResolvedValue({
      runtimeStatus: {
        externalUrl: null,
        internalUrl: 'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002',
      },
    });

    const cache = new Map<string, string>();
    const result = await resolveRuntimeBaseUrl('ws-1', cache);

    expect(result).toBe('http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002');
  });

  it('上傳 ZIP 解壓時會傳遞 archive 參數並解析回應', async () => {
    postMock.mockResolvedValue({
      uploaded: [{ path: '/uploads/demo.zip', size: 12, lastModified: '2026-01-01T00:00:00Z' }],
      extracted: [{ path: '/uploads/demo/app.ts', size: 20, lastModified: '2026-01-01T00:00:00Z' }],
      skipped: [],
    });

    const file = new File(['zip'], 'demo.zip', { type: 'application/zip' });
    const result = await uploadFiles('http://runtime.local', '/uploads', [file], false, {
      archiveAction: 'extract',
      keepArchive: true,
      conflictStrategy: 'reject',
    });

    const [, formData] = postMock.mock.calls[0] ?? [];
    expect(formData).toBeInstanceOf(FormData);
    expect(formData.get('archiveAction')).toBe('extract');
    expect(formData.get('keepArchive')).toBe('true');
    expect(formData.get('conflictStrategy')).toBe('reject');
    expect(result.uploadedPaths).toEqual(['/uploads/demo.zip']);
    expect(result.extractedPaths).toEqual(['/uploads/demo/app.ts']);
    expect(result.affectedPaths).toEqual(['/uploads/demo.zip', '/uploads/demo/app.ts']);
  });

  it('未指定 archive 行為時預設保存 ZIP', async () => {
    postMock.mockResolvedValue({
      uploaded: [{ path: '/uploads/demo.zip', size: 12, lastModified: '2026-01-01T00:00:00Z' }],
      extracted: [],
      skipped: [],
    });

    const file = new File(['zip'], 'demo.zip', { type: 'application/zip' });
    await uploadFiles('http://runtime.local', '/uploads', [file]);

    const [, formData] = postMock.mock.calls[0] ?? [];
    expect(formData.get('archiveAction')).toBe('store');
    expect(formData.get('keepArchive')).toBe('false');
    expect(formData.get('conflictStrategy')).toBe('rename');
  });

  it('會把 contextId 帶到檔案樹與內容請求，且預設隱藏 hidden entries', async () => {
    clientGetMock
      .mockResolvedValueOnce({ nodes: [] })
      .mockResolvedValueOnce({ content: 'hello' });

    await fetchFileTree('http://runtime.local', '/', { contextId: 'worktree:feature-auth' });
    await fetchFileContent('http://runtime.local', '/README.md', 'worktree:feature-auth');

    expect(clientGetMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/files/tree?path=%2F&includeHidden=false&contextId=worktree%3Afeature-auth',
    );
    expect(clientGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/files/content?path=%2FREADME.md&contextId=worktree%3Afeature-auth',
    );
  });

  it('會在子節點請求沿用 active hidden visibility setting', async () => {
    clientGetMock.mockResolvedValue({ nodes: [] });

    await fetchNodeChildren('http://runtime.local', '/project', 1, {
      includeHidden: true,
      contextId: 'worktree:feature-auth',
    });

    expect(clientGetMock).toHaveBeenCalledWith(
      '/api/v1/files/tree/children?path=%2Fproject&includeHidden=true&contextId=worktree%3Afeature-auth',
    );
  });

  it('會啟動背景解壓並回傳 operation id', async () => {
    postMock.mockResolvedValue({
      operationId: 'extract-123',
      status: 'pending',
      message: '準備解壓縮 ZIP 檔案...',
      startedAt: '2026-01-01T00:00:00Z',
    });

    const result = await startExtractArchive('http://runtime.local', {
      archivePath: '/uploads/demo.zip',
      conflictStrategy: 'overwrite',
      contextId: 'worktree:feature-auth',
    });

    const [url, body] = postMock.mock.calls[0] ?? [];
    expect(url).toBe('/api/v1/files/extract?contextId=worktree%3Afeature-auth');
    expect(body).toEqual({
      archivePath: '/uploads/demo.zip',
      targetPath: undefined,
      conflictStrategy: 'overwrite',
    });
    expect(result.operationId).toBe('extract-123');
  });

  it('會查詢背景解壓狀態', async () => {
    clientGetMock.mockResolvedValue({
      operationId: 'extract-123',
      status: 'completed',
      progress: 1,
      message: '解壓完成，共 1 個項目',
      startedAt: '2026-01-01T00:00:00Z',
      completedAt: '2026-01-01T00:00:05Z',
      result: {
        extracted: [{ path: '/uploads/demo/app.ts', size: 20, lastModified: '2026-01-01T00:00:00Z' }],
        extractedPaths: ['/uploads/demo/app.ts'],
      },
    });

    const result = await fetchExtractArchiveStatus('http://runtime.local', 'extract-123');

    expect(clientGetMock).toHaveBeenCalledWith('/api/v1/files/extract/extract-123');
    expect(result.status).toBe('completed');
    expect(result.result?.extractedPaths).toEqual(['/uploads/demo/app.ts']);
  });
});
