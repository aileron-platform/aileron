import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseFileTreeDataAdapter, knowledgeBaseFileEndpoints } from './knowledgeBaseFileTreeDataAdapter';

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

  it('keeps knowledge-base copy endpoint in feature-owned code', () => {
    expect(knowledgeBaseFileEndpoints.copy('kb-1')).toBe('/knowledge-bases/kb-1/files/copy');
  });

  it('loads the tree with hidden-entry visibility in the query string', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [] });

    const adapter = new KnowledgeBaseFileTreeDataAdapter({
      knowledgeBaseId: 'kb-1',
      includeHidden: true,
    });
    await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledWith('/knowledge-bases/kb-1/files/tree?path=%2F&includeHidden=true');
  });

  it('uses the current patch move request shape', async () => {
    apiClientMock.patch.mockResolvedValueOnce({ success: true });

    const adapter = new KnowledgeBaseFileTreeDataAdapter({ knowledgeBaseId: 'kb-1' });
    await adapter.move('/docs/a.md', '/docs/b.md');

    expect(apiClientMock.patch).toHaveBeenCalledWith('/knowledge-bases/kb-1/files', {
      sourcePath: '/docs/a.md',
      destinationPath: '/docs/b.md',
      overwrite: false,
    });
  });
});
