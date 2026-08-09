import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCodexSubagentSource } from './codexSubagentSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listCodexSubagents: vi.fn(),
  getCodexSubagent: vi.fn(),
  saveCodexSubagent: vi.fn(),
  deleteCodexSubagent: vi.fn(),
};

describe('createCodexSubagentSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('list maps items to documents and captures the registry', async () => {
    api.listCodexSubagents.mockResolvedValue({
      items: [{
        id: 'project:a.toml',
        source: 'project',
        path: 'a.toml',
        relativePath: 'a.toml',
        name: 'a',
        content: 'name = "a"',
        editable: true,
        effective: true,
        overridden: false,
        readOnly: false,
        metadata: {},
      }, {
        id: 'user:b.toml',
        source: 'user',
        path: 'team/b.toml',
        relativePath: 'team/b.toml',
        name: 'b',
        content: 'name = "b"',
        editable: true,
        effective: true,
        overridden: false,
        readOnly: false,
        metadata: {},
      }],
      registry: [{ scope: 'project', path: 'r', settings: { max_threads: 4 } }],
    });
    const source = createCodexSubagentSource(api as never, 'http://rt', 'ws-1');

    const result = await source.list();

    expect(api.listCodexSubagents).toHaveBeenCalledWith('http://rt', 'ws-1');
    expect(result.items).toHaveLength(2);
    expect(result.items[0]).toEqual(expect.objectContaining({ id: 'project:a.toml', title: 'a' }));
    expect(result.items.map((item) => item.title)).toEqual(['a', 'b']);
    expect(result.availableScopes).toEqual([
      { scope: 'project', readOnly: false },
      { scope: 'user', readOnly: false },
      { scope: 'plugin', readOnly: true },
    ]);
    expect(source.getRegistry()).toEqual([{ scope: 'project', path: 'r', settings: { max_threads: 4 } }]);
  });

  it('remove deletes via scope and path', async () => {
    const source = createCodexSubagentSource(api as never, 'http://rt', 'ws-1');
    const doc: AgentDocument = {
      id: 'user:a.toml',
      title: 'a.toml',
      scope: 'user',
      content: 'x',
      metadata: { source: 'user', relativePath: 'a.toml' },
    };

    await source.remove(doc);

    expect(api.deleteCodexSubagent).toHaveBeenCalledWith('http://rt', 'ws-1', 'user', 'a.toml');
  });

  it('renames using previousPath while preserving nested relative paths', async () => {
    api.saveCodexSubagent.mockResolvedValue({
      id: 'project:team/new.md',
      source: 'project',
      path: 'team/new.md',
      relativePath: 'team/new.md',
      name: 'new',
      content: 'name = "new"',
      editable: true,
      effective: true,
      overridden: false,
      readOnly: false,
      metadata: {},
    });
    const source = createCodexSubagentSource(api as never, 'http://rt', 'ws-1');
    const doc: AgentDocument = {
      id: 'project:team/new.md',
      title: 'new.md',
      scope: 'project',
      content: 'name = "new"',
      metadata: {
        source: 'project',
        relativePath: 'team/new.md',
        previousFileName: 'team/old.md',
      },
    };

    await source.move?.(doc, 'team/new.md');

    expect(api.saveCodexSubagent).toHaveBeenCalledWith('http://rt', 'ws-1', {
      scope: 'project',
      path: 'team/new.md',
      previousPath: 'team/old.md',
      content: 'name = "new"',
    });
  });
});
