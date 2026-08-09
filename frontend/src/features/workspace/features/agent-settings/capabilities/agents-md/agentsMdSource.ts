import { createAgentSettingsApi } from '../../api/agentSettingsApi';
import type { SingleDocumentSource } from '../../model/singleDocumentSource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export const createAgentsMdSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): SingleDocumentSource => {
  const revisions = new Map<string, string>();
  const loadRevision = async (scope: string): Promise<string> => {
    const response = await api.getAgentsMd(runtimeBaseUrl, workspaceId, scope);
    if (response.revision) {
      revisions.set(scope, response.revision);
    }
    return response.revision ?? '';
  };

  return {
    load: async (scope) => {
      const response = await api.getAgentsMd(runtimeBaseUrl, workspaceId, scope);
      if (response.revision) {
        revisions.set(scope, response.revision);
      }
      return {
        content: response.content,
        metadata: {
          revision: response.revision,
        },
      };
    },
    save: async (scope, content) => {
      const revision = revisions.get(scope) ?? await loadRevision(scope);
      const response = await api.updateAgentsMd(runtimeBaseUrl, workspaceId, { scope, content, revision });
      if (response?.revision) {
        revisions.set(scope, response.revision);
      }
    },
  };
};
