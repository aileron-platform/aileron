import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createSubagentSource } from './subagentSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listSubagents: vi.fn(),
  loadSubagent: vi.fn(),
  createSubagent: vi.fn(),
  updateSubagent: vi.fn(),
  deleteSubagent: vi.fn(),
};

const doc: AgentDocument = {
  id: 'project:worker.md',
  title: 'worker.md',
  scope: 'project',
  content: 'x',
  metadata: { fileName: 'worker.md' },
};

describe('createSubagentSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists summaries and loads content only for the selected subagent', async () => {
    api.listSubagents.mockResolvedValue({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
    const source = createSubagentSource(api as never, 'http://rt', 'ws-1');

    expect(await source.list()).toEqual({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
    expect(api.listSubagents).toHaveBeenCalledWith('http://rt', 'ws-1');
    const document = { id: 'project:review.md' } as never;
    api.loadSubagent.mockResolvedValue(document);
    await expect(source.loadContent!(document)).resolves.toBe(document);
    expect(api.loadSubagent).toHaveBeenCalledWith(
      'http://rt',
      'ws-1',
      document,
    );
  });

  it('create/update/remove delegate', async () => {
    api.createSubagent.mockResolvedValue(doc);
    api.updateSubagent.mockResolvedValue(doc);
    const source = createSubagentSource(api as never, 'http://rt', 'ws-1');

    await source.create(doc);
    await source.update(doc);
    await source.remove(doc);

    expect(api.createSubagent).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
    expect(api.updateSubagent).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
    expect(api.deleteSubagent).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
  });

  it('moves by updating the path metadata without the legacy previous file name contract', async () => {
    api.updateSubagent.mockResolvedValue({ ...doc, title: 'worker-new.md' });
    const source = createSubagentSource(api as never, 'http://rt', 'ws-1');

    await source.move?.(doc, 'team/worker-new.md');

    expect(api.updateSubagent).toHaveBeenCalledWith(
      'http://rt',
      'ws-1',
      expect.objectContaining({
        title: 'team/worker-new.md',
        metadata: expect.objectContaining({
          fileName: 'team/worker-new.md',
          relativePath: 'team/worker-new.md',
        }),
      }),
    );
    expect(api.updateSubagent.mock.calls[0]).toHaveLength(3);
  });
});
