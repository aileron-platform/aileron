import { describe, expect, it } from 'vitest';
import { basenameWithoutKnownDocumentExtension } from './documentMetadata';
import { createDocumentTemplate } from './documentTemplates';

const t = (key: string, values?: Record<string, unknown>) => {
  if (key === 'shared.documentWorkflow.templates.subagent.description') {
    return `Subagent for ${String(values?.name ?? 'new agent')}`;
  }
  if (key === 'shared.documentWorkflow.templates.subagent.developerInstructions') {
    return `Handle tasks for ${String(values?.name ?? 'new agent')}`;
  }
  if (key === 'shared.documentWorkflow.templates.outputStyle.title') {
    return 'Output style instructions';
  }
  return key;
};

describe('basenameWithoutKnownDocumentExtension', () => {
  it('strips known document template extensions from file names', () => {
    expect(basenameWithoutKnownDocumentExtension('worker.toml')).toBe('worker');
    expect(basenameWithoutKnownDocumentExtension('review.md')).toBe('review');
    expect(basenameWithoutKnownDocumentExtension('runbook.markdown')).toBe('runbook');
  });
});

describe('createDocumentTemplate', () => {
  it('creates slash command markdown that can be edited immediately', () => {
    expect(createDocumentTemplate('slashCommand', { fileName: 'review.md' }, t)).toContain('# review');
  });

  it('creates markdown subagent frontmatter with name derived from fileName and non-empty description', () => {
    const content = createDocumentTemplate('subagent', { fileName: 'incident-review.md' }, t);
    expect(content).toContain('name: incident-review');
    expect(content).toContain('description: Subagent for incident-review');
  });

  it('creates TOML subagent starter content for non-markdown subagents', () => {
    const content = createDocumentTemplate('subagent', { fileName: 'worker.toml' }, t, 'toml');
    expect(content).toContain('name = "worker"');
    expect(content).toContain('description = "Subagent for worker"');
    expect(content).toContain('developer_instructions = "Handle tasks for worker"');
  });

  it('creates output style markdown with a non-empty heading', () => {
    expect(createDocumentTemplate('outputStyle', { fileName: 'concise.md' }, t)).toContain('# Output style instructions');
  });
});
