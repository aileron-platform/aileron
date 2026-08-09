import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createSlashCommandSource } from './slashCommandSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listSlashCommands: vi.fn(),
  loadSlashCommand: vi.fn(),
  createSlashCommand: vi.fn(),
  updateSlashCommand: vi.fn(),
  deleteSlashCommand: vi.fn(),
};

const doc: AgentDocument = {
  id: 'project:deploy.md',
  title: 'deploy.md',
  scope: 'project',
  content: 'Run deploy',
  metadata: { fileName: 'deploy.md' },
};

describe('createSlashCommandSource', () => {
  beforeEach(() => vi.clearAllMocks());

  it('list delegates to listSlashCommands with runtime and workspace', async () => {
    api.listSlashCommands.mockResolvedValue({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
    const source = createSlashCommandSource(api as never, 'http://rt', 'ws-1');

    const result = await source.list();

    expect(api.listSlashCommands).toHaveBeenCalledWith('http://rt', 'ws-1');
    expect(result).toEqual({
      items: [doc],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
  });

  it('loads content only for the selected command', async () => {
    const source = createSlashCommandSource(api as never, 'http://rt', 'ws-1');
    const document = { id: 'project:greet.md' } as never;
    api.loadSlashCommand.mockResolvedValue(document);

    await expect(source.loadContent!(document)).resolves.toBe(document);
    expect(api.loadSlashCommand).toHaveBeenCalledWith(
      'http://rt',
      'ws-1',
      document,
    );
  });

  it('create/update/remove delegate to the matching api methods', async () => {
    api.createSlashCommand.mockResolvedValue(doc);
    api.updateSlashCommand.mockResolvedValue(doc);
    const source = createSlashCommandSource(api as never, 'http://rt', 'ws-1');

    await source.create(doc);
    await source.update(doc);
    await source.remove(doc);

    expect(api.createSlashCommand).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
    expect(api.updateSlashCommand).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
    expect(api.deleteSlashCommand).toHaveBeenCalledWith('http://rt', 'ws-1', doc);
  });
});
