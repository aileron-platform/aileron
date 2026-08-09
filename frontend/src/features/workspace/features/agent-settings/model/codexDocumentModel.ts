import { formatDocumentContentSize } from '@/shared/components/document-workflow';
import type {
  CodexFileSummary,
  CodexSubagentDefinition,
  CodexSubagentItem,
} from '../api/agentSettingsApi';
import type { AgentDocument, AgentScope } from './documents';

export type CodexDocumentResource = 'subagents' | 'prompts';
export type CodexEditableScope = 'project' | 'user';

export const CODEX_EDITABLE_SCOPES: CodexEditableScope[] = ['project', 'user'];

export const fileNameFromCodexDocumentPath = (path: string): string => path.split('/').filter(Boolean).pop() || path;

export const buildCodexDocumentId = (source: string, path: string): string => `${source}:${path}`;

export const buildCodexDocumentPath = (document: AgentDocument, fallback: string): string => {
  const fileName = (document.metadata?.fileName as string | undefined) || document.title || fallback;
  const namespace = (document.metadata?.namespace as string | undefined)?.trim();
  if (!namespace) {
    return fileName;
  }
  return `${namespace.replace(/^\/+|\/+$/g, '')}/${fileName}`.replace(/^\/+/, '');
};

const mapSourceToScope = (source: CodexFileSummary['source']): AgentScope => (
  source === 'user' || source === 'project' || source === 'plugin' ? source : 'plugin'
);

const mapSubagentSourceToScope = (source: CodexSubagentItem['source']): AgentScope => (
  source === 'user' || source === 'project' || source === 'plugin' ? source : 'plugin'
);

const escapeTomlString = (value: string): string => value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

export const subagentDefinitionToToml = (definition?: CodexSubagentDefinition | null): string => {
  if (!definition) {
    return '';
  }
  const lines = [
    `name = "${escapeTomlString(definition.name)}"`,
    `description = "${escapeTomlString(definition.description)}"`,
    `developer_instructions = "${escapeTomlString(definition.developer_instructions)}"`,
  ];
  if (definition.nickname_candidates?.length) {
    lines.push(`nickname_candidates = [${definition.nickname_candidates.map((item) => `"${escapeTomlString(item)}"`).join(', ')}]`);
  }
  if (definition.model) {
    lines.push(`model = "${escapeTomlString(definition.model)}"`);
  }
  if (definition.model_reasoning_effort) {
    lines.push(`model_reasoning_effort = "${escapeTomlString(definition.model_reasoning_effort)}"`);
  }
  if (definition.sandbox_mode) {
    lines.push(`sandbox_mode = "${escapeTomlString(definition.sandbox_mode)}"`);
  }
  return `${lines.join('\n')}\n`;
};

export const mapCodexFileSummaryToDocument = (summary: CodexFileSummary, content = ''): AgentDocument => ({
  id: buildCodexDocumentId(summary.source, summary.path),
  title: fileNameFromCodexDocumentPath(summary.path),
  description: '',
  content,
  scope: mapSourceToScope(summary.source),
  size: formatDocumentContentSize(content || ' '),
  metadata: {
    fileName: summary.path,
    source: summary.source,
    readOnly: summary.readOnly,
    sizeBytes: summary.sizeBytes,
    ...summary.metadata,
  },
  pluginName: typeof summary.metadata?.pluginName === 'string' ? summary.metadata.pluginName : undefined,
  marketplaceName: typeof summary.metadata?.marketplaceName === 'string' ? summary.metadata.marketplaceName : undefined,
});

export const mapCodexSubagentToDocument = (item: CodexSubagentItem): AgentDocument => {
  const content = item.content || subagentDefinitionToToml(item.definition);
  return {
    id: item.id,
    title: item.name,
    description: item.definition?.description ?? '',
    content,
    scope: mapSubagentSourceToScope(item.source),
    size: formatDocumentContentSize(content || ' '),
    metadata: {
      ...item.metadata,
      definition: item.definition,
      fileName: item.relativePath,
      relativePath: item.relativePath,
      source: item.source,
      readOnly: item.readOnly,
      editable: item.editable,
      effective: item.effective,
      overridden: item.overridden,
      format: 'toml',
    },
    pluginName: item.pluginName ?? undefined,
    marketplaceName: item.marketplaceName ?? undefined,
  };
};
