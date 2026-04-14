import { apiClient } from '@/shared/api/apiClient';

export type WorkspaceSetupTaskState = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

export interface WorkspaceSetupTaskStatus {
  taskKey: string;
  taskName: string;
  status: WorkspaceSetupTaskState;
  message?: string;
}

export interface WorkspaceSetupStatus {
  workspaceId: string;
  completed: boolean;
  tasks: WorkspaceSetupTaskStatus[];
}

export class WorkspaceSetupService {
  static async startInitialSync(workspaceId: string): Promise<WorkspaceSetupStatus> {
    const response = await apiClient.post<WorkspaceSetupStatus>(
      `/workspaces/${workspaceId}/setup/sync`,
      {}
    );
    return response;
  }

  static async getStatus(workspaceId: string): Promise<WorkspaceSetupStatus> {
    const response = await apiClient.get<WorkspaceSetupStatus>(
      `/workspaces/${workspaceId}/setup/status`
    );
    return response;
  }
}

export default WorkspaceSetupService;
