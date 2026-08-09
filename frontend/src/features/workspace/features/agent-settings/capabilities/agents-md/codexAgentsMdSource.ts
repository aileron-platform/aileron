import {
  createAgentSettingsApi,
  type CodexAgentsMdCaveat,
} from '../../api/agentSettingsApi';
import type { SingleDocumentSource } from '../../model/singleDocumentSource';

type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;

export interface CodexAgentsMdSource extends SingleDocumentSource {
  getCaveats(): CodexAgentsMdCaveat[];
}

export const createCodexAgentsMdSource = (
  api: AgentSettingsApi,
  runtimeBaseUrl: string,
  workspaceId: string,
): CodexAgentsMdSource => {
  let caveats: CodexAgentsMdCaveat[] = [];
  const revisions = new Map<string, string>();
  const loadRevision = async (scope: string): Promise<string> => {
    const response = await api.getCodexAgentsMd(runtimeBaseUrl, workspaceId, scope);
    caveats = response.caveats ?? [];
    if (response.revision) {
      revisions.set(scope, response.revision);
    }
    return response.revision ?? '';
  };

  return {
    load: async (scope) => {
      const response = await api.getCodexAgentsMd(runtimeBaseUrl, workspaceId, scope);
      caveats = response.caveats ?? [];
      if (response.revision) {
        revisions.set(scope, response.revision);
      }
      return {
        content: response.content,
        metadata: {
          path: response.path,
          exists: response.exists,
          activePath: response.activePath,
          maxBytes: response.maxBytes,
          sizeBytes: response.sizeBytes,
          revision: response.revision,
        },
      };
    },
    save: async (scope, content) => {
      const revision = revisions.get(scope) ?? await loadRevision(scope);
      const response = await api.updateCodexAgentsMd(runtimeBaseUrl, workspaceId, { scope, content, revision });
      if (response?.revision) {
        revisions.set(scope, response.revision);
      }
    },
    getCaveats: () => caveats,
  };
};
