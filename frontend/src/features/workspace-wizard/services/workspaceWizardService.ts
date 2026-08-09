import type { CreateWorkspacePayload } from '../model/workspaceWizardTypes';
import { apiClient } from '@/shared/api/apiClient';

interface WorkspaceDetailResponse {
  id: string;
}

export interface CreateWorkspaceResult {
  workspaceId: string;
}

export interface StartWorkspaceResult {
  workspaceId: string;
  status: string;
  jobId: string;
}

const API_BASE = '/workspaces';
const DEFAULT_RUNTIME = 'universal';

const buildApiUrl = (path?: string): string => {
  if (path) {
    return `${API_BASE}/${path}`;
  }
  return API_BASE;
};
interface RuntimeLogEntry {
  id: string;
  workspaceId: string;
  stage: string;
  message: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

export const workspaceWizardService = {
  async createWorkspace(payload: CreateWorkspacePayload): Promise<CreateWorkspaceResult> {
    // The backend derives ownerId from the authenticated user context.
    const workspace = await apiClient.post<WorkspaceDetailResponse>(buildApiUrl(), {
      name: payload.name,
      description: payload.description,
      runtime: payload.runtime || DEFAULT_RUNTIME,
      agenticTools: payload.agenticTools,
    });
    if (payload.setupScript.trim() || payload.envVars.length > 0) {
      await apiClient.put(
        buildApiUrl(`${encodeURIComponent(workspace.id)}/sensitive-settings`),
        {
          setupScript: payload.setupScript.trim()
            ? payload.setupScript
            : null,
          envVars: payload.envVars,
        },
      );
    }

    return { workspaceId: workspace.id };
  },

  async startWorkspace(workspaceId: string): Promise<StartWorkspaceResult> {
    return await apiClient.post<StartWorkspaceResult>(
      buildApiUrl(`${encodeURIComponent(workspaceId)}/start`),
    );
  },

  async getRuntimeLogs(workspaceId: string, limit: number = 50): Promise<RuntimeLogEntry[]> {
    return await apiClient.get<RuntimeLogEntry[]>(buildApiUrl(`${workspaceId}/runtime-logs?limit=${limit}`));
  },
};
