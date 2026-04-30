import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createKnowledgeBaseFileWorkbenchAdapter,
  createTemplateFileWorkbenchAdapter,
  createWorkspaceFileWorkbenchAdapter,
  toFileWorkbenchTab,
} from './index';

const apiGetBlobMock = vi.hoisted(() => vi.fn());
const apiClientGetMock = vi.hoisted(() => vi.fn());
const apiClientPostMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    getBlob: apiGetBlobMock,
  },
  ApiClient: vi.fn().mockImplementation(() => ({
    get: apiClientGetMock,
    post: apiClientPostMock,
    getBlob: apiGetBlobMock,
  })),
}));

describe('file workbench adapters', () => {
  beforeEach(() => {
    apiGetBlobMock.mockReset();
    apiClientGetMock.mockReset();
    apiClientPostMock.mockReset();
  });

  it('normalizes domain editor tabs into public workbench tabs', () => {
    expect(toFileWorkbenchTab({
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'current',
      originalContent: 'base',
      isModified: true,
      isLoading: true,
    })).toEqual({
      id: '/docs/readme.md',
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'current',
      originalContent: 'base',
      isModified: true,
      isLoading: true,
      error: undefined,
    });
  });

  it('preserves workspace runtime blob and Draw.io behavior through the adapter', async () => {
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

  it('preserves template raw content URLs and optional editor actions', async () => {
    const saveFile = vi.fn();
    const copyPath = vi.fn();
    const revealInTree = vi.fn();

    const adapter = createTemplateFileWorkbenchAdapter({
      templateId: 'tpl-1',
      scope: 'skills',
      readFile: vi.fn().mockResolvedValue('template content'),
      saveFile,
      copyPath,
      revealInTree,
    });

    await adapter.readBlob?.('/skill/SKILL.md');
    expect(apiGetBlobMock).toHaveBeenCalledWith(
      '/api/v1/templates/tpl-1/files/content?scope=skills&path=%2Fskill%2FSKILL.md',
    );

    await adapter.saveFile?.('/skill/SKILL.md', 'next');
    await adapter.copyPath?.('/skill/SKILL.md');
    adapter.revealInTree?.('/skill/SKILL.md');

    expect(saveFile).toHaveBeenCalledWith('/skill/SKILL.md', 'next');
    expect(copyPath).toHaveBeenCalledWith('/skill/SKILL.md');
    expect(revealInTree).toHaveBeenCalledWith('/skill/SKILL.md');
  });

  it('preserves knowledge base raw content URLs and optional editor actions', async () => {
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
