import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCodexDocumentSource } from './codexDocumentSource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listCodexFiles: vi.fn(),
  getCodexFile: vi.fn(),
  updateCodexFile: vi.fn(),
  deleteCodexFile: vi.fn(),
};

describe('createCodexDocumentSource("prompts")', () => {
  beforeEach(() => vi.clearAllMocks());

  it('list aggregates files across editable scopes as summaries', async () => {
    api.listCodexFiles.mockResolvedValue({
      files: ['project', 'user'].map((source) => ({
          name: `${source}.md`,
          path: `${source}.md`,
          sizeBytes: 1,
          source,
          readOnly: false,
          metadata: {},
      })),
    });
    const source = createCodexDocumentSource(api as never, 'http://rt', 'ws-1', 'prompts');

    const result = await source.list();

    expect(api.listCodexFiles).toHaveBeenCalledTimes(1);
    expect(api.listCodexFiles).toHaveBeenCalledWith(
      'http://rt',
      'ws-1',
      'prompts',
      'all',
    );
    expect(result.availableScopes).toEqual([
      { scope: 'project', readOnly: false },
      { scope: 'user', readOnly: false },
    ]);
    expect(result.items.map((d) => d.id)).toEqual(['project:project.md', 'user:user.md']);
    expect(result.items.map((d) => d.title)).toEqual(['project.md', 'user.md']);
    expect(result.items.every((d) => d.content === '')).toBe(true);
  });

  it('is lazy and loadContent fetches the selected file body', async () => {
    api.getCodexFile.mockResolvedValue({ content: 'PROMPT BODY' });
    const source = createCodexDocumentSource(api as never, 'http://rt', 'ws-1', 'prompts');
    const summary: AgentDocument = {
      id: 'project:greet.md',
      title: 'greet.md',
      scope: 'project',
      content: '',
      metadata: { source: 'project', relativePath: 'greet.md' },
    };

    const loaded = await source.loadContent!(summary);

    expect(api.getCodexFile).toHaveBeenCalledWith('http://rt', 'ws-1', 'prompts', 'project', 'greet.md');
    expect(loaded.content).toBe('PROMPT BODY');
  });

  it('remove deletes via scope and path derived from the document', async () => {
    const source = createCodexDocumentSource(api as never, 'http://rt', 'ws-1', 'prompts');
    const doc: AgentDocument = {
      id: 'user:old.md',
      title: 'old.md',
      scope: 'user',
      content: 'x',
      metadata: { source: 'user', relativePath: 'old.md' },
    };

    await source.remove(doc);

    expect(api.deleteCodexFile).toHaveBeenCalledWith('http://rt', 'ws-1', 'prompts', 'user', 'old.md');
  });
});
