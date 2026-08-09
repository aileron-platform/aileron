import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { DocumentSource } from '@/shared/components/document-resource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export const createSlashCommandSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): DocumentSource => ({
  list: () => api.listSlashCommands(runtimeBaseUrl, workspaceId),
  loadContent: (document) =>
    api.loadSlashCommand(runtimeBaseUrl, workspaceId, document),
  create: (document) => api.createSlashCommand(runtimeBaseUrl, workspaceId, document),
  update: (document) => api.updateSlashCommand(runtimeBaseUrl, workspaceId, document),
  remove: async (document) => {
    await api.deleteSlashCommand(runtimeBaseUrl, workspaceId, document);
  },
});
