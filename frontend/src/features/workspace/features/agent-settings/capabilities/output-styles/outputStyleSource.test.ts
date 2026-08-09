import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createOutputStyleSource } from './outputStyleSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listOutputStyles: vi.fn(),
  loadOutputStyle: vi.fn(),
  createOutputStyle: vi.fn(),
  updateOutputStyle: vi.fn(),
  deleteOutputStyle: vi.fn(),
};

const doc: AgentDocument = {
  id: 'project:concise.md',
  title: 'concise.md',
  scope: 'project',
  content: '# Concise',
  metadata: { fileName: 'concise.md' },
};

describe('createOutputStyleSource', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('delegates list/create/update/remove to the agent settings api', async () => {
    api.listOutputStyles.mockResolvedValue({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
    api.createOutputStyle.mockResolvedValue(doc);
    api.updateOutputStyle.mockResolvedValue(doc);
    api.loadOutputStyle.mockResolvedValue(doc);

    const source = createOutputStyleSource(api as never, 'http://runtime.test', 'ws-1');

    await expect(source.list()).resolves.toEqual({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
    await expect(source.loadContent!(doc)).resolves.toEqual(doc);
    await source.create(doc);
    await source.update(doc);
    await source.remove(doc);

    expect(api.listOutputStyles).toHaveBeenCalledWith('http://runtime.test', 'ws-1');
    expect(api.loadOutputStyle).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      doc,
    );
    expect(api.createOutputStyle).toHaveBeenCalledWith('http://runtime.test', 'ws-1', doc);
    expect(api.updateOutputStyle).toHaveBeenCalledWith('http://runtime.test', 'ws-1', doc);
    expect(api.deleteOutputStyle).toHaveBeenCalledWith('http://runtime.test', 'ws-1', doc);
  });

  it('passes plugin scope and plugin identity to the list contract', async () => {
    api.listOutputStyles.mockResolvedValue({
      items: [],
      availableScopes: [{ scope: 'plugin', readOnly: true }],
    });
    const source = createOutputStyleSource(
      api as never,
      'http://runtime.test',
      'ws-1',
      { scope: 'plugin', pluginId: 'review@official' },
    );

    await source.list();

    expect(api.listOutputStyles).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      { scope: 'plugin', pluginId: 'review@official' },
    );
  });
});
