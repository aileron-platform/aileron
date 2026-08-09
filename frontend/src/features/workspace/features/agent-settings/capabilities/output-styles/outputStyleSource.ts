import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export const createOutputStyleSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
  filter?: {
    scope?: 'project' | 'user' | 'plugin';
    pluginId?: string | null;
  },
): DocumentSource => ({
  list: () => filter
    ? api.listOutputStyles(runtimeBaseUrl, workspaceId, filter)
    : api.listOutputStyles(runtimeBaseUrl, workspaceId),
  loadContent: (document) =>
    api.loadOutputStyle(runtimeBaseUrl, workspaceId, document),
  create: (document) => api.createOutputStyle(runtimeBaseUrl, workspaceId, document),
  update: (document) => api.updateOutputStyle(runtimeBaseUrl, workspaceId, document),
  remove: async (document) => {
    await api.deleteOutputStyle(runtimeBaseUrl, workspaceId, document);
  },
});
