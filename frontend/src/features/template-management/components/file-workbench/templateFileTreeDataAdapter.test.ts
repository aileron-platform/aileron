import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TemplateFileTreeDataAdapter } from './templateFileTreeDataAdapter';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

describe('TemplateFileTreeDataAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads template files from the feature-owned endpoint shape', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [] });

    const adapter = new TemplateFileTreeDataAdapter({ templateId: 'tpl-1', scope: 'skills' });
    await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledWith('/templates/tpl-1/files/tree?scope=skills&include_hidden=true');
  });

  it('uses the current move endpoint for rename-style UI operations', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new TemplateFileTreeDataAdapter({ templateId: 'tpl-1', scope: 'scripts' });
    await adapter.move('/old.ts', '/new.ts');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/templates/tpl-1/files/move?scope=scripts&source_path=%2Fold.ts&dest_path=%2Fnew.ts',
    );
  });
});
