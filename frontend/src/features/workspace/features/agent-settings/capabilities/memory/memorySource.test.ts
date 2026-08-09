import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemorySource } from './memorySource';
import type { AgentDocument } from '../../model/documents';

const api = {
  listMemoryDocuments: vi.fn(),
  loadMemoryDocument: vi.fn(),
  updateMemoryDocument: vi.fn(),
  deleteMemoryDocument: vi.fn(),
};

const doc: AgentDocument = {
  id: 'user:CLAUDE.md',
  title: 'CLAUDE.md',
  scope: 'user',
  content: '# Memory',
  metadata: { fileName: 'CLAUDE.md' },
};

describe('createMemorySource', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('delegates list/update/remove and keeps create as a no-op', async () => {
    api.listMemoryDocuments.mockResolvedValue({
      items: [doc],
      availableScopes: [{ scope: 'user', readOnly: false }],
    });
    api.updateMemoryDocument.mockResolvedValue(doc);
    api.loadMemoryDocument.mockResolvedValue(doc);

    const source = createMemorySource(api as never, 'http://runtime.test', 'ws-1');

    await expect(source.list()).resolves.toEqual({
      items: [doc],
      availableScopes: [{ scope: 'user', readOnly: false }],
    });
    await expect(source.create(doc)).resolves.toEqual(doc);
    await expect(source.loadContent!(doc)).resolves.toEqual(doc);
    await source.update(doc);
    await source.remove(doc);

    expect(api.listMemoryDocuments).toHaveBeenCalledWith('http://runtime.test', 'ws-1');
    expect(api.loadMemoryDocument).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      doc,
    );
    expect(api.updateMemoryDocument).toHaveBeenCalledWith('http://runtime.test', 'ws-1', doc);
    expect(api.deleteMemoryDocument).toHaveBeenCalledWith('http://runtime.test', 'ws-1', doc);
  });
});
