import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createTemplateFileWorkbenchAdapter } from './templateFileWorkbenchAdapter';

const apiGetBlobMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    getBlob: apiGetBlobMock,
  },
}));

describe('template file workbench adapter', () => {
  beforeEach(() => {
    apiGetBlobMock.mockReset();
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
});
