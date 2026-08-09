import { describe, expect, it } from 'vitest';
import { createDocumentMetadataAdapter } from './documentMetadataAdapters';

describe('createDocumentMetadataAdapter', () => {
  it('with scope=false omits scope capability and ids by path', () => {
    const adapter = createDocumentMetadataAdapter('slashCommand', { scope: false });
    expect(adapter.capabilities).toEqual({ scope: false, namespace: true });

    const created = adapter.buildCreate({ fileName: 'do.md', namespace: 'git' }, 'body');

    expect(created.id).toBe('git/do.md');
    expect((created as { path?: string }).path ?? created.metadata?.fileName).toBe('git/do.md');
  });

  it('with scope=true ids by scope:path', () => {
    const adapter = createDocumentMetadataAdapter('subagent', { scope: true });
    expect(adapter.capabilities.scope).toBe(true);

    const created = adapter.buildCreate({ fileName: 'x.md', scope: 'user' }, 'body');

    expect(created.id).toBe('user:x.md');
  });

  it('builds slash commands with namespace metadata', () => {
    const adapter = createDocumentMetadataAdapter('slashCommand');
    const document = adapter.buildCreate(
      { fileName: 'review.md', scope: 'project', namespace: 'team' },
      '# review\n',
    );

    expect(document).toMatchObject({
      id: 'project:team/review.md',
      title: 'review.md',
      scope: 'project',
      content: '# review\n',
      metadata: { fileName: 'team/review.md' },
    });
  });

  it('prefers a slash-command namespace over a normalized create path', () => {
    const adapter = createDocumentMetadataAdapter('slashCommand');
    const document = adapter.buildCreate(
      {
        fileName: 'review.md',
        path: 'review.md',
        scope: 'project',
        namespace: 'team',
      },
      '# review\n',
    );

    expect(document.id).toBe('project:team/review.md');
    expect(document.metadata?.fileName).toBe('team/review.md');
  });

  it('renames only the file name for nested slash-command paths', () => {
    const adapter = createDocumentMetadataAdapter('slashCommand');
    const renamed = adapter.applyRename({
      id: 'project:team/review.md',
      title: 'review.md',
      scope: 'project',
      content: '# review',
      metadata: { fileName: 'team/review.md' },
    }, 'qa.md');

    expect(renamed).toMatchObject({
      id: 'project:team/qa.md',
      title: 'qa.md',
      scope: 'project',
      metadata: { fileName: 'team/qa.md' },
    });
  });

  it('stores the previous file name for subagent renames', () => {
    const adapter = createDocumentMetadataAdapter('subagent');
    const renamed = adapter.applyRename({
      id: 'project:old.md',
      title: 'old.md',
      scope: 'project',
      content: '# old',
      metadata: { fileName: 'old.md' },
    }, 'new.md');

    expect(renamed.metadata).toMatchObject({
      fileName: 'new.md',
      previousFileName: 'old.md',
    });
  });

  it('does not expose namespace for output styles', () => {
    const adapter = createDocumentMetadataAdapter('outputStyle');

    expect(adapter.capabilities.namespace).toBe(false);
  });
});
