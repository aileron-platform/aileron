import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export const createSubagentSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): DocumentSource => ({
  list: () => api.listSubagents(runtimeBaseUrl, workspaceId),
  loadContent: (document) =>
    api.loadSubagent(runtimeBaseUrl, workspaceId, document),
  create: (document) => api.createSubagent(runtimeBaseUrl, workspaceId, document),
  update: (document) => api.updateSubagent(runtimeBaseUrl, workspaceId, document),
  move: (document, nextPath) => {
    const nextDocument = {
      ...document,
      id: `${document.scope}:${nextPath}`,
      title: nextPath,
      metadata: {
        ...document.metadata,
        fileName: nextPath,
        relativePath: nextPath,
      },
    };
    return api.updateSubagent(runtimeBaseUrl, workspaceId, nextDocument);
  },
  remove: async (document) => {
    await api.deleteSubagent(runtimeBaseUrl, workspaceId, document);
  },
});
