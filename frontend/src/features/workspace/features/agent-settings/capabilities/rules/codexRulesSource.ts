import { formatDocumentContentSize } from '@/shared/components/document-workflow';
import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';
import type { AgentDocument } from '../../model/documents';
import { CODEX_EDITABLE_SCOPES } from '../../model/codexDocumentModel';
import type { CodexRulesFileSummary } from '../../api/agentSettingsApi';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

const fileNameFromPath = (path: string): string => path.split('/').filter(Boolean).pop() || path;

const mapRulesSummaryToDocument = (
  layer: 'user' | 'project',
  summary: CodexRulesFileSummary,
): AgentDocument => ({
  id: `${layer}:${summary.path}`,
  title: fileNameFromPath(summary.path),
  description: '',
  content: '',
  scope: layer,
  size: formatDocumentContentSize(' '),
  metadata: {
    fileName: summary.path,
    relativePath: summary.path,
    source: layer,
    sizeBytes: summary.sizeBytes,
  },
});

const scopeOf = (document: AgentDocument): 'user' | 'project' =>
  document.scope === 'user' ? 'user' : 'project';

const pathOf = (document: AgentDocument): string =>
  (document.metadata?.relativePath as string | undefined)
  ?? (document.metadata?.fileName as string | undefined)
  ?? document.title;

export const createCodexRulesSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): DocumentSource => ({
  list: async () => {
    const byId = new Map<string, AgentDocument>();
    for (const layer of CODEX_EDITABLE_SCOPES) {
      const response = await api.listCodexRules(runtimeBaseUrl, workspaceId, layer);
      for (const summary of response.files) {
        const id = `${layer}:${summary.path}`;
        if (!byId.has(id)) {
          byId.set(id, mapRulesSummaryToDocument(layer, summary));
        }
      }
    }
    return {
      items: [...byId.values()],
      availableScopes: CODEX_EDITABLE_SCOPES.map(scope => ({
        scope,
        readOnly: false,
      })),
    };
  },
  loadContent: async (document) => {
    const source = (document.metadata?.source as string | undefined) ?? document.scope;
    if (source !== 'project' && source !== 'user') {
      return document;
    }
    const response = await api.getCodexRulesFile(runtimeBaseUrl, workspaceId, source, pathOf(document));
    return { ...document, content: response.content };
  },
  create: async (document) => {
    const response = await api.updateCodexRulesFile(
      runtimeBaseUrl,
      workspaceId,
      scopeOf(document),
      pathOf(document),
      document.content,
    );
    return { ...document, content: response.content };
  },
  update: async (document) => {
    const response = await api.updateCodexRulesFile(
      runtimeBaseUrl,
      workspaceId,
      scopeOf(document),
      pathOf(document),
      document.content,
    );
    return { ...document, content: response.content };
  },
  remove: async (document) => {
    await api.deleteCodexRulesFile(runtimeBaseUrl, workspaceId, scopeOf(document), pathOf(document));
  },
});
