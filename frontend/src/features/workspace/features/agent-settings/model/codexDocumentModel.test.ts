import { describe, expect, it } from 'vitest';
import type {
  CodexFileSummary,
  CodexSubagentItem,
} from '../api/agentSettingsApi';
import type { AgentDocument } from './documents';
import {
  buildCodexDocumentId,
  buildCodexDocumentPath,
  fileNameFromCodexDocumentPath,
  mapCodexFileSummaryToDocument,
  mapCodexSubagentToDocument,
  subagentDefinitionToToml,
} from './codexDocumentModel';

describe('codexDocumentModel', () => {
  it('builds stable document ids and file names from paths', () => {
    expect(buildCodexDocumentId('project', 'prompts/deploy.md')).toBe('project:prompts/deploy.md');
    expect(fileNameFromCodexDocumentPath('/prompts/deploy.md')).toBe('deploy.md');
    expect(fileNameFromCodexDocumentPath('')).toBe('');
  });

  it('builds document paths from namespace metadata and fallback names', () => {
    const document: AgentDocument = {
      id: 'project:team/a/release.md',
      title: 'deploy.md',
      scope: 'project',
      content: '# Deploy',
      metadata: { namespace: '/team/a/', fileName: 'release.md' },
    };

    expect(buildCodexDocumentPath(document, 'prompt.md')).toBe('team/a/release.md');
    expect(buildCodexDocumentPath({ ...document, metadata: {} }, 'prompt.md')).toBe('deploy.md');
  });

  it('maps Codex file summaries to document metadata', () => {
    const summary: CodexFileSummary = {
      name: 'deploy.md',
      path: 'prompts/deploy.md',
      sizeBytes: 10,
      source: 'project',
      readOnly: false,
      metadata: { marketplaceName: 'local', pluginName: 'agent-pack' },
    };

    expect(mapCodexFileSummaryToDocument(summary, '# Deploy')).toMatchObject({
      id: 'project:prompts/deploy.md',
      title: 'deploy.md',
      content: '# Deploy',
      scope: 'project',
      pluginName: 'agent-pack',
      marketplaceName: 'local',
      metadata: {
        fileName: 'prompts/deploy.md',
        source: 'project',
        readOnly: false,
        sizeBytes: 10,
      },
    });
  });

  it('serializes subagent definitions to TOML with escaped strings', () => {
    expect(subagentDefinitionToToml({
      name: 'reviewer',
      description: 'Review "code"',
      developer_instructions: 'Use backslash \\ carefully',
      nickname_candidates: ['review'],
      model: 'gpt-5.6-sol',
    })).toContain('description = "Review \\"code\\""');
  });

  it('maps subagents to documents with TOML fallback content', () => {
    const item: CodexSubagentItem = {
      id: 'built_in:worker',
      name: 'worker',
      source: 'built_in',
      editable: false,
      readOnly: true,
      path: 'worker.toml',
      relativePath: 'worker.toml',
      content: '',
      definition: {
        name: 'worker',
        description: 'Worker',
        developer_instructions: 'Do work.',
      },
      effective: true,
      overridden: false,
      metadata: { pluginId: 'core' },
    };

    expect(mapCodexSubagentToDocument(item)).toMatchObject({
      id: 'built_in:worker',
      title: 'worker',
      scope: 'plugin',
      content: 'name = "worker"\ndescription = "Worker"\ndeveloper_instructions = "Do work."\n',
      metadata: {
        fileName: 'worker.toml',
        relativePath: 'worker.toml',
        source: 'built_in',
        readOnly: true,
        editable: false,
        effective: true,
        overridden: false,
        format: 'toml',
      },
    });
  });

});
