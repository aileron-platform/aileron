import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createWorkspaceFileWorkbenchAdapter } from './workspaceFileWorkbenchAdapter';

const apiGetBlobMock = vi.hoisted(() => vi.fn());
const apiClientGetMock = vi.hoisted(() => vi.fn());
const apiClientPostMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    get: apiClientGetMock,
    post: apiClientPostMock,
    getBlob: apiGetBlobMock,
  })),
}));

describe('workspace file workbench adapter', () => {
  beforeEach(() => {
    apiGetBlobMock.mockReset();
    apiClientGetMock.mockReset();
    apiClientPostMock.mockReset();
  });

  it('preserves workspace runtime blob and Draw.io behavior', async () => {
    const saveDrawio = vi.fn();
    apiClientGetMock.mockResolvedValue({ url: 'http://drawio.local/view' });

    const adapter = createWorkspaceFileWorkbenchAdapter({
      runtimeBaseUrl: 'http://runtime.local',
      readFile: vi.fn().mockResolvedValue('workspace content'),
      saveFile: vi.fn(),
      saveDrawio,
      copyPath: vi.fn(),
      revealInTree: vi.fn(),
    });

    await adapter.readBlob?.('/src/logo.png');
    expect(apiGetBlobMock).toHaveBeenCalledWith('/api/v1/files/content?path=%2Fsrc%2Flogo.png&raw=true');

    await expect(adapter.getDrawioViewerUrl?.('/docs/flow.drawio', 'edit')).resolves.toBe('http://drawio.local/view');
    expect(apiClientGetMock).toHaveBeenCalledWith('/api/v1/drawio/viewer?file_path=%2Fdocs%2Fflow.drawio&mode=edit');

    await adapter.saveDrawio?.('/docs/flow.drawio', '<mxfile />');
    expect(apiClientPostMock).toHaveBeenCalledWith('/api/v1/drawio/save?file_path=%2Fdocs%2Fflow.drawio', {
      content: '<mxfile />',
    });
    expect(saveDrawio).toHaveBeenCalledWith('/docs/flow.drawio', '<mxfile />');
  });
});
