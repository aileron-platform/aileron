import { describe, expect, it, vi } from 'vitest';
import { createMarketplaceDocumentSource } from './marketplaceDocumentSources';
import * as api from '../../../api/marketplaceApi';
import { MarketplaceResourceSession } from '../../../model/marketplaceResourceSession';

vi.mock('../../../api/marketplaceApi');

const mutationResult = (
  path: string,
  revision: string,
  ownerFilePath: string | null = null,
  baseEntryFingerprint: string | null = null,
) => ({
  success: true as const,
  path,
  revision,
  ownerFilePath,
  baseEntryFingerprint,
});

const createSource = () => {
  const session = new MarketplaceResourceSession({
    targetClient: 'claude-code',
    packageId: 'pkg',
    resourceType: 'commands',
  }, 'rev1');
  return {
    session,
    source: createMarketplaceDocumentSource(
      'claude-code',
      'pkg',
      'commands',
      session,
      session.identityGeneration,
    ),
  };
};

describe('createMarketplaceDocumentSource', () => {
  it('list returns ResourceListResult and hides owner/fingerprint from items', async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([
      {
        id: 'a',
        title: 'a',
        path: 'a.md',
        resourceType: 'commands',
        content: '',
        ownerFilePath: 'CLAUDE.md',
        baseEntryFingerprint: 'fp1',
      },
    ]);

    const { source } = createSource();
    const out = await source.list();

    expect(out.availableScopes).toEqual([]);
    expect(out.items[0]).not.toHaveProperty('ownerFilePath');
    expect(out.items[0]).not.toHaveProperty('baseEntryFingerprint');
  });

  it('move sends recorded owner/fingerprint back to api', async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([
      {
        id: 'a',
        title: 'a',
        path: 'a.md',
        resourceType: 'commands',
        content: '',
        ownerFilePath: 'CLAUDE.md',
        baseEntryFingerprint: 'fp1',
      },
    ]);
    vi.mocked(api.renameDocument).mockResolvedValue(
      mutationResult('commands/b.md', 'rev2'),
    );

    const { source } = createSource();
    await source.list();
    await source.move!({
      id: 'a',
      path: 'a.md',
      scope: 'project',
      title: 'a',
      content: '',
    }, 'b.md');

    expect(api.renameDocument).toHaveBeenCalledWith('claude-code', 'pkg', 'commands', expect.objectContaining({
      previousPath: 'a.md',
      nextPath: 'commands/b.md',
      revision: 'rev1',
      ownerFilePath: 'CLAUDE.md',
      baseEntryFingerprint: 'fp1',
    }));
  });

  it('roots create and move paths under the marketplace resource directory', async () => {
    vi.mocked(api.createDocument).mockResolvedValue(
      mutationResult('commands/greet.md', 'rev2'),
    );
    vi.mocked(api.renameDocument).mockResolvedValue(
      mutationResult('commands/new.md', 'rev3'),
    );

    const { session, source } = createSource();

    const created = await source.create({
      id: 'greet.md',
      title: 'greet',
      scope: 'project',
      content: '# greet',
      metadata: { fileName: 'greet.md' },
    });
    await source.move!({
      id: 'commands/old.md',
      title: 'old',
      scope: 'project',
      content: '',
      metadata: { fileName: 'commands/old.md', previousFileName: 'commands/old.md' },
    }, 'new.md');

    expect(api.createDocument).toHaveBeenCalledWith('claude-code', 'pkg', 'commands', expect.objectContaining({
      path: 'commands/greet.md',
    }));
    expect(created).toEqual({
      document: expect.objectContaining({
        id: 'commands/greet.md',
        description: 'commands/greet.md',
        metadata: expect.objectContaining({ fileName: 'commands/greet.md' }),
      }),
      result: mutationResult('commands/greet.md', 'rev2'),
    });
    expect(session.revision).toBe('rev3');
    expect(api.renameDocument).toHaveBeenCalledWith('claude-code', 'pkg', 'commands', expect.objectContaining({
      previousPath: 'commands/old.md',
      nextPath: 'commands/new.md',
      revision: 'rev2',
    }));
  });

  it('uses the API result for canonical identity and the next source token', async () => {
    vi.mocked(api.createDocument).mockResolvedValue(
      mutationResult('commands/canonical.md', 'rev2', 'CLAUDE.md', 'fp2'),
    );
    vi.mocked(api.renameDocument).mockResolvedValue(
      mutationResult('commands/renamed.md', 'rev3'),
    );
    const { source } = createSource();

    const created = await source.create({
      id: 'draft.md',
      title: 'draft',
      scope: 'project',
      content: '# draft',
      metadata: { fileName: 'draft.md' },
    });
    await source.move(created.document, 'renamed.md');

    expect(created.document).toEqual(expect.objectContaining({
      id: 'commands/canonical.md',
      description: 'commands/canonical.md',
      metadata: expect.objectContaining({ fileName: 'commands/canonical.md' }),
    }));
    expect(api.renameDocument).toHaveBeenCalledWith(
      'claude-code',
      'pkg',
      'commands',
      expect.objectContaining({
        previousPath: 'commands/canonical.md',
        revision: 'rev2',
        ownerFilePath: 'CLAUDE.md',
        baseEntryFingerprint: 'fp2',
      }),
    );
  });

  it('returns update and remove results while advancing revision and tokens', async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([{
      id: 'commands/a.md',
      title: 'a',
      path: 'commands/a.md',
      resourceType: 'commands',
      content: '# a',
      ownerFilePath: 'CLAUDE.md',
      baseEntryFingerprint: 'fp1',
    }]);
    vi.mocked(api.updateDocument).mockResolvedValue(
      mutationResult('commands/a.md', 'rev2', 'CLAUDE.md', 'fp2'),
    );
    vi.mocked(api.removeDocument).mockResolvedValue(
      mutationResult('commands/a.md', 'rev3'),
    );
    const { session, source } = createSource();
    const listed = await source.list();
    const listedDocument = listed.items[0];
    if (!listedDocument) {
      throw new Error('Expected one listed document');
    }

    const updated = await source.update({
      ...listedDocument,
      content: '# updated',
    });
    const removed = await source.remove(updated.document);

    expect(api.updateDocument).toHaveBeenCalledWith(
      'claude-code',
      'pkg',
      'commands',
      'commands/a.md',
      {
        path: 'commands/a.md',
        revision: 'rev1',
        content: '# updated',
        ownerFilePath: 'CLAUDE.md',
        baseEntryFingerprint: 'fp1',
      },
    );
    expect(api.removeDocument).toHaveBeenCalledWith(
      'claude-code',
      'pkg',
      'commands',
      'commands/a.md',
      {
        revision: 'rev2',
        ownerFilePath: 'CLAUDE.md',
        baseEntryFingerprint: 'fp2',
      },
    );
    expect(removed).toEqual(mutationResult('commands/a.md', 'rev3'));
    expect(session.revision).toBe('rev3');
  });

  it('uses the Codex-native prompts root for the Slash Command resource', async () => {
    const session = new MarketplaceResourceSession({
      targetClient: 'codex',
      packageId: 'pkg',
      resourceType: 'commands',
    }, 'rev1');
    const source = createMarketplaceDocumentSource(
      'codex',
      'pkg',
      'commands',
      session,
      session.identityGeneration,
    );
    vi.mocked(api.listDocuments).mockResolvedValue([{
      id: 'prompts/review.md',
      title: 'review',
      path: 'prompts/review.md',
      resourceType: 'commands',
      content: '# review',
    }]);
    vi.mocked(api.createDocument).mockResolvedValue(
      mutationResult('prompts/new.md', 'rev2'),
    );

    const listed = await source.list();
    const created = await source.create({
      id: 'new.md',
      title: 'new',
      scope: 'project',
      content: '# new',
      metadata: { fileName: 'new.md' },
    });

    expect(listed.items[0]).toEqual(expect.objectContaining({
      id: 'prompts/review.md',
      description: 'prompts/review.md',
    }));
    expect(api.createDocument).toHaveBeenCalledWith(
      'codex',
      'pkg',
      'commands',
      expect.objectContaining({ path: 'prompts/new.md' }),
    );
    expect(created.document).toEqual(expect.objectContaining({
      id: 'prompts/new.md',
      description: 'prompts/new.md',
    }));
  });
});
