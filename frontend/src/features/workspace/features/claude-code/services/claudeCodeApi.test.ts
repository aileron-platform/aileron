import { beforeEach, describe, expect, it, vi } from 'vitest';
import { claudeCodeApi } from './claudeCodeApi';
import type { ClaudeDocument } from '../data';

describe('claudeCodeApi memory documents', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('lists memory documents from the fixed memory endpoints', async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspaceId: 'ws-1',
            documents: [
              { fileName: 'zeta.md', name: 'Zeta', description: 'last', size: '30 B' },
              { fileName: 'alpha.md', name: 'Alpha', description: 'first', size: '10 B' },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspaceId: 'ws-1',
            document: {
              fileName: 'zeta.md',
              name: 'Zeta',
              description: 'last',
              content: '# zeta',
              size: '30 B',
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspaceId: 'ws-1',
            document: {
              fileName: 'alpha.md',
              name: 'Alpha',
              description: 'first',
              content: '# alpha',
              size: '10 B',
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );

    const documents = await claudeCodeApi.listMemoryDocuments('http://runtime.test', 'ws-1');

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/memory',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/memory/zeta.md',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/memory/alpha.md',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(documents).toEqual([
      expect.objectContaining({
        id: 'user:alpha.md',
        title: 'Alpha',
        scope: 'user',
        metadata: { fileName: 'alpha.md' },
      }),
      expect.objectContaining({
        id: 'user:zeta.md',
        title: 'Zeta',
        scope: 'user',
        metadata: { fileName: 'zeta.md' },
      }),
    ]);
  });

  it('updates and deletes memory documents without scope segments', async () => {
    const document: ClaudeDocument = {
      id: 'user:notes.md',
      scope: 'user',
      title: 'notes.md',
      description: '',
      content: '# notes',
      metadata: { fileName: 'notes.md' },
    };

    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            workspaceId: 'ws-1',
            document: {
              fileName: 'notes.md',
              name: 'notes.md',
              description: '',
              content: '# updated',
              size: '14 B',
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const updated = await claudeCodeApi.updateMemoryDocument('http://runtime.test', 'ws-1', {
      ...document,
      content: '# updated',
    });
    await claudeCodeApi.deleteMemoryDocument('http://runtime.test', 'ws-1', document);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/memory/notes.md',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ content: '# updated' }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/memory/notes.md',
      expect.objectContaining({ method: 'DELETE' }),
    );
    expect(updated.content).toBe('# updated');
  });

  it('reads and writes raw settings for the selected scope', async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ content: { model: 'claude-sonnet-4-5' } }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ content: { model: 'claude-opus-4-1' } }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );

    const raw = await claudeCodeApi.getRawSettings('http://runtime.test', 'ws-1', 'local');
    const updated = await claudeCodeApi.updateRawSettings(
      'http://runtime.test',
      'ws-1',
      'user',
      { model: 'claude-opus-4-1' },
    );

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/settings/raw?scope=local',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://runtime.test/api/v1/workspaces/ws-1/claude-code/settings/raw?scope=user',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ content: { model: 'claude-opus-4-1' } }),
      }),
    );
    expect(raw.content).toEqual({ model: 'claude-sonnet-4-5' });
    expect(updated.content).toEqual({ model: 'claude-opus-4-1' });
  });
});
