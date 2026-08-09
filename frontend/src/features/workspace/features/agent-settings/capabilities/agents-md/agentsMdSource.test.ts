import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createAgentsMdSource } from './agentsMdSource';

const api = {
  getAgentsMd: vi.fn(),
  updateAgentsMd: vi.fn(),
};

describe('createAgentsMdSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('load and save delegate with scope', async () => {
    api.getAgentsMd.mockResolvedValue({ content: 'X', revision: 'project-r1' });
    const source = createAgentsMdSource(api as never, 'http://rt', 'ws-1');

    expect(await source.load('project')).toEqual({ content: 'X', metadata: { revision: 'project-r1' } });
    expect(api.getAgentsMd).toHaveBeenCalledWith('http://rt', 'ws-1', 'project');

    await source.save('user', 'Y');
    expect(api.getAgentsMd).toHaveBeenLastCalledWith('http://rt', 'ws-1', 'user');
    expect(api.updateAgentsMd).toHaveBeenCalledWith('http://rt', 'ws-1', {
      scope: 'user',
      content: 'Y',
      revision: 'project-r1',
    });
  });
});
