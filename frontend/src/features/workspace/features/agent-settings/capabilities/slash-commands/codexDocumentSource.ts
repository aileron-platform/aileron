import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';
import type { AgentDocument } from '../../model/documents';
import {
  buildCodexDocumentId,
  buildCodexDocumentPath,
  mapCodexFileSummaryToDocument,
  type CodexDocumentResource,
} from '../../model/codexDocumentModel';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

const CODEX_EDITABLE_SCOPES = ['project', 'user'] as const;

const scopeOf = (document: AgentDocument): 'project' | 'user' =>
  document.scope === 'user' ? 'user' : 'project';

const pathOf = (document: AgentDocument): string =>
  (document.metadata?.relativePath as string | undefined)
  ?? (document.metadata?.fileName as string | undefined)
  ?? document.title;

export const createCodexDocumentSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
  resource: CodexDocumentResource,
): DocumentSource => ({
  list: async () => {
    const byId = new Map<string, AgentDocument>();
    const response = await api.listCodexFiles(
      runtimeBaseUrl,
      workspaceId,
      resource,
      'all',
    );
    for (const summary of response.files) {
      if (summary.source !== 'project' && summary.source !== 'user') continue;
      const id = buildCodexDocumentId(summary.source, summary.path);
      if (!byId.has(id)) {
        byId.set(id, mapCodexFileSummaryToDocument(summary, ''));
      }
    }
    return {
      items: [...byId.values()],
      availableScopes: CODEX_EDITABLE_SCOPES.map((scope) => ({
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
    const response = await api.getCodexFile(runtimeBaseUrl, workspaceId, resource, source, pathOf(document));
    return { ...document, content: response.content };
  },
  create: async (document) => {
    const scope = scopeOf(document);
    const path = buildCodexDocumentPath(document, pathOf(document));
    const response = await api.updateCodexFile(runtimeBaseUrl, workspaceId, resource, scope, path, document.content);
    return { ...document, content: response.content };
  },
  update: async (document) => {
    const scope = scopeOf(document);
    const path = buildCodexDocumentPath(document, pathOf(document));
    const response = await api.updateCodexFile(runtimeBaseUrl, workspaceId, resource, scope, path, document.content);
    return { ...document, content: response.content };
  },
  remove: async (document) => {
    await api.deleteCodexFile(runtimeBaseUrl, workspaceId, resource, scopeOf(document), pathOf(document));
  },
});
