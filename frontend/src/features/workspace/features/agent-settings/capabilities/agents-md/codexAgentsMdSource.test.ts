import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCodexAgentsMdSource } from './codexAgentsMdSource';

const api = {
  getCodexAgentsMd: vi.fn(),
  updateCodexAgentsMd: vi.fn(),
};

describe('createCodexAgentsMdSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('load maps content, metadata, and caveats', async () => {
    api.getCodexAgentsMd.mockResolvedValue({
      content: 'CODEX',
      path: '/workspace/AGENTS.md',
      exists: true,
      maxBytes: 200,
      sizeBytes: 5,
      revision: 'project-r1',
      caveats: [{ type: 'override', path: 'AGENTS.md', messageKey: 'msg', metadata: {} }],
    });
    const source = createCodexAgentsMdSource(api as never, 'http://rt', 'ws-1');

    expect(await source.load('project')).toEqual({
      content: 'CODEX',
      metadata: {
        path: '/workspace/AGENTS.md',
        exists: true,
        activePath: undefined,
        maxBytes: 200,
        sizeBytes: 5,
        revision: 'project-r1',
      },
    });
    expect(source.getCaveats()).toEqual([{ type: 'override', path: 'AGENTS.md', messageKey: 'msg', metadata: {} }]);
  });

  it('save delegates to the codex API with scope and content', async () => {
    api.getCodexAgentsMd.mockResolvedValue({
      content: 'CODEX',
      path: '/workspace/AGENTS.md',
      exists: true,
      maxBytes: 200,
      sizeBytes: 5,
      revision: 'user-r1',
      caveats: [],
    });
    const source = createCodexAgentsMdSource(api as never, 'http://rt', 'ws-1');

    await source.save('user', 'Y');

    expect(api.getCodexAgentsMd).toHaveBeenCalledWith('http://rt', 'ws-1', 'user');
    expect(api.updateCodexAgentsMd).toHaveBeenCalledWith('http://rt', 'ws-1', {
      scope: 'user',
      content: 'Y',
      revision: 'user-r1',
    });
  });
});
