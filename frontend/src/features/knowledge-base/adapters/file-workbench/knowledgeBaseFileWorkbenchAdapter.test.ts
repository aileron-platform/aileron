import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createKnowledgeBaseFileWorkbenchAdapter } from './knowledgeBaseFileWorkbenchAdapter';

const apiGetBlobMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    getBlob: apiGetBlobMock,
  },
}));

describe('knowledge-base file workbench adapter', () => {
  beforeEach(() => {
    apiGetBlobMock.mockReset();
  });

  it('builds the knowledge base raw content URL', async () => {
    const adapter = createKnowledgeBaseFileWorkbenchAdapter({
      knowledgeBaseId: 'kb-1',
      readFile: vi.fn().mockResolvedValue('kb content'),
      saveFile: vi.fn(),
      copyPath: vi.fn(),
      revealInTree: vi.fn(),
    });

    await adapter.readBlob?.('/docs/readme.md');

    expect(apiGetBlobMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/files/content?path=%2Fdocs%2Freadme.md&raw=true',
    );
  });
});
