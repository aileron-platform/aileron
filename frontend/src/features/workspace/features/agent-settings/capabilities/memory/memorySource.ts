import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export const createMemorySource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): DocumentSource => ({
  list: () => api.listMemoryDocuments(runtimeBaseUrl, workspaceId),
  loadContent: (document) =>
    api.loadMemoryDocument(runtimeBaseUrl, workspaceId, document),
  create: async (document) => document,
  update: (document) => api.updateMemoryDocument(runtimeBaseUrl, workspaceId, document),
  remove: async (document) => {
    await api.deleteMemoryDocument(runtimeBaseUrl, workspaceId, document);
  },
});
