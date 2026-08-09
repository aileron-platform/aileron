import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createKnowledgeBaseFileTreeDataAdapter,
  knowledgeBaseFileEndpoints,
} from './knowledgeBaseFileTreeDataAdapter';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

describe('KnowledgeBaseFileTreeDataAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the initial tree with hidden-entry visibility and full depth in the query string', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [] });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({
      knowledgeBaseId: 'kb-1',
      includeHidden: true,
    });
    await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/tree?path=%2F&includeHidden=true&maxDepth=5');
  });

  it('loads directory children from the tree endpoint when a directory expands', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      nodes: [{ id: '/raw/sources/file.md', name: 'file.md', path: '/raw/sources/file.md', type: 'file' }],
    });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({
      knowledgeBaseId: 'kb-1',
      includeHidden: false,
    });

    await expect(adapter.getChildren('/raw/sources')).resolves.toHaveLength(1);

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/files/tree?path=%2Fraw%2Fsources&includeHidden=false&maxDepth=1',
    );
  });

  it('uses the current move endpoint request shape', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });
    await adapter.move('/docs/a.md', '/docs/b.md');

    expect(apiClientMock.post).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/move', {
      sourcePath: '/docs/a.md',
      destinationPath: '/docs/b.md',
    });
  });

  it('preserves version tokens when loading file content', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      content: 'Hello',
      revision: 'version-1',
      readable: true,
    });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });

    await expect(adapter.getContent('/README.md')).resolves.toEqual({
      content: 'Hello',
      revision: 'version-1',
      readable: true,
      unreadableReason: undefined,
    });

    expect(apiClientMock.get).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/content?path=%2FREADME.md');
  });

  it('preserves binary readability metadata without treating the path as invalid', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      content: '',
      revision: 'version-zip',
      readable: false,
      unreadableReason: 'binary',
    });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });

    await expect(adapter.getContent('/cube-web-design-style (1).zip')).resolves.toEqual({
      content: '',
      revision: 'version-zip',
      readable: false,
      unreadableReason: 'binary',
    });

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/files/content?path=%2Fcube-web-design-style%20(1).zip',
    );
  });

  it('sends expected version tokens on update and preserves response version tokens', async () => {
    apiClientMock.put.mockResolvedValueOnce({ success: true, revision: 'version-2' });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });

    await expect(
      adapter.update('/README.md', 'Updated', { revision: 'version-1' }),
    ).resolves.toEqual({
      success: true,
      revision: 'version-2',
      data: { revision: 'version-2' },
    });

    expect(apiClientMock.put).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/content', {
      path: '/README.md',
      type: 'file',
      content: 'Updated',
      revision: 'version-1',
    });
  });

  it('preflights once and uploads with explicit cancel strategy when there are no conflicts', async () => {
    apiClientMock.post
      .mockResolvedValueOnce({ conflicts: [], total: 1 })
      .mockResolvedValueOnce({ items: [{ sourcePath: 'guide.md', finalPath: '/docs/guide.md', status: 'created', size: 7, type: 'file', error: null }], total: 1, succeeded: 1, skipped: 0, failed: 0 });

    const adapter = createKnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });
    const file = new File(['content'], 'guide.md', { type: 'text/markdown' });
    await adapter.upload({
      targetPath: '/docs',
      files: [file],
    });

    expect(apiClientMock.post.mock.calls[0]?.[0]).toBe('/knowledge-bases/kb-1/files/conflicts/preflight');
    const [url, formData] = apiClientMock.post.mock.calls[1] ?? [];
    expect(url).toBe('/knowledge-bases/kb-1/files/upload');
    expect(formData).toBeInstanceOf(FormData);
    expect(formData.get('targetPath')).toBe('/docs');
    expect(formData.get('defaultStrategy')).toBe('cancel');
    expect(formData.get('resolutions')).toBe('[]');
  });
});
