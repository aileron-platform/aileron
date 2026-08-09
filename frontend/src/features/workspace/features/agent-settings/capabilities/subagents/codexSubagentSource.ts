import {
  createAgentSettingsApi,
  type CodexSubagentRegistrySource,
  type CodexSubagentSource as CodexSubagentSourceType,
} from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';
import type { AgentDocument } from '../../model/documents';
import { mapCodexSubagentToDocument } from '../../model/codexDocumentModel';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export interface CodexSubagentSource extends DocumentSource {
  getRegistry(): CodexSubagentRegistrySource[];
}

const scopeOf = (document: AgentDocument): 'user' | 'project' =>
  document.scope === 'user' ? 'user' : 'project';

const pathOf = (document: AgentDocument): string =>
  (document.metadata?.relativePath as string | undefined)
  ?? (document.metadata?.fileName as string | undefined)
  ?? document.title;

const detailSourceOf = (document: AgentDocument): CodexSubagentSourceType | null => {
  const source = (document.metadata?.source as string | undefined) ?? document.scope;
  if (source === 'project' || source === 'user' || source === 'plugin' || source === 'built_in') {
    return source;
  }
  return null;
};

export const createCodexSubagentSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): CodexSubagentSource => {
  let registry: CodexSubagentRegistrySource[] = [];
  return {
    list: async () => {
      const response = await api.listCodexSubagents(runtimeBaseUrl, workspaceId);
      registry = response.registry ?? [];
      return {
        items: response.items.map(mapCodexSubagentToDocument),
        availableScopes: [
          { scope: 'project', readOnly: false },
          { scope: 'user', readOnly: false },
          { scope: 'plugin', readOnly: true },
        ],
      };
    },
    loadContent: async (document) => {
      const source = detailSourceOf(document);
      if (!source) {
        return document;
      }
      const item = await api.getCodexSubagent(
        runtimeBaseUrl,
        workspaceId,
        source,
        pathOf(document),
        typeof document.metadata?.pluginId === 'string' ? document.metadata.pluginId : undefined,
      );
      return mapCodexSubagentToDocument(item);
    },
    create: async (document) => {
      const item = await api.saveCodexSubagent(runtimeBaseUrl, workspaceId, {
        scope: scopeOf(document),
        path: pathOf(document),
        content: document.content,
      });
      return mapCodexSubagentToDocument(item);
    },
    update: async (document) => {
      const item = await api.saveCodexSubagent(runtimeBaseUrl, workspaceId, {
        scope: scopeOf(document),
        path: pathOf(document),
        previousPath: (document.metadata?.previousFileName as string | undefined) ?? null,
        content: document.content,
      });
      return mapCodexSubagentToDocument(item);
    },
    move: async (document, nextPath) => {
      const previousPath = (document.metadata?.previousFileName as string | undefined) ?? pathOf(document);
      const nextDocument = {
        ...document,
        title: nextPath.split('/').filter(Boolean).pop() ?? nextPath,
        metadata: {
          ...document.metadata,
          fileName: nextPath,
          relativePath: nextPath,
          previousFileName: previousPath,
        },
      };
      const item = await api.saveCodexSubagent(runtimeBaseUrl, workspaceId, {
        scope: scopeOf(nextDocument),
        path: nextPath,
        previousPath,
        content: nextDocument.content,
      });
      return mapCodexSubagentToDocument(item);
    },
    remove: async (document) => {
      await api.deleteCodexSubagent(runtimeBaseUrl, workspaceId, scopeOf(document), pathOf(document));
    },
    getRegistry: () => registry,
  };
};
