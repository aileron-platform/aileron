import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCodexRulesSource } from './codexRulesSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listCodexRules: vi.fn(),
  getCodexRulesFile: vi.fn(),
  updateCodexRulesFile: vi.fn(),
  deleteCodexRulesFile: vi.fn(),
};

describe('createCodexRulesSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('list aggregates rules files across layers as summaries', async () => {
    api.listCodexRules.mockImplementation((_rt, _ws, layer) =>
      Promise.resolve({
        files: [{
          name: `${layer}.rules`,
          path: `${layer}.rules`,
          sizeBytes: 1,
        }],
      }),
    );
    const source = createCodexRulesSource(api as never, 'http://rt', 'ws-1');

    const docs = await source.list();

    expect(api.listCodexRules).toHaveBeenCalledWith('http://rt', 'ws-1', 'project');
    expect(api.listCodexRules).toHaveBeenCalledWith('http://rt', 'ws-1', 'user');
    expect(docs.items.map((document) => document.id)).toEqual([
      'project:project.rules',
      'user:user.rules',
    ]);
    expect(docs.items.every((document) => document.content === '')).toBe(true);
    expect(docs.availableScopes).toEqual([
      { scope: 'project', readOnly: false },
      { scope: 'user', readOnly: false },
    ]);
  });

  it('loadContent fetches the selected rule body', async () => {
    api.getCodexRulesFile.mockResolvedValue({ content: 'RULE BODY' });
    const source = createCodexRulesSource(api as never, 'http://rt', 'ws-1');
    const summary: AgentDocument = {
      id: 'project:r.md',
      title: 'r.md',
      scope: 'project',
      content: '',
      metadata: { source: 'project', relativePath: 'r.md' },
    };

    expect((await source.loadContent!(summary)).content).toBe('RULE BODY');
    expect(api.getCodexRulesFile).toHaveBeenCalledWith('http://rt', 'ws-1', 'project', 'r.md');
  });

  it('remove deletes via layer and path', async () => {
    const source = createCodexRulesSource(api as never, 'http://rt', 'ws-1');
    const doc: AgentDocument = {
      id: 'user:r.md',
      title: 'r.md',
      scope: 'user',
      content: 'x',
      metadata: { source: 'user', relativePath: 'r.md' },
    };

    await source.remove(doc);

    expect(api.deleteCodexRulesFile).toHaveBeenCalledWith('http://rt', 'ws-1', 'user', 'r.md');
  });
});
