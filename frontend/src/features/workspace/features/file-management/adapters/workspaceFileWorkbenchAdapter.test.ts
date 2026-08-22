import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createWorkspaceFileWorkbenchAdapter } from './workspaceFileWorkbenchAdapter';

const apiGetBlobMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    getBlob: apiGetBlobMock,
  })),
}));

describe('workspace file workbench adapter', () => {
  beforeEach(() => {
    apiGetBlobMock.mockReset();
  });

  it('loads workspace runtime blobs', async () => {
    const adapter = createWorkspaceFileWorkbenchAdapter({
      runtimeBaseUrl: 'http://runtime.local',
      readFile: vi.fn().mockResolvedValue('workspace content'),
      saveFile: vi.fn(),
      copyPath: vi.fn(),
      revealInTree: vi.fn(),
    });

    await adapter.readBlob?.('/src/logo.png');
    expect(apiGetBlobMock).toHaveBeenCalledWith('/api/v1/files/content?path=%2Fsrc%2Flogo.png&raw=true');
  });
});
