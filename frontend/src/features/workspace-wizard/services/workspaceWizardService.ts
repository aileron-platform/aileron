import { CreateWorkspacePayload, WizardCLIInfo } from '../types';
import { apiClient } from '@/shared/api/apiClient';

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

interface WorkspaceRuntimeStatus {
  status?: string;
}

interface WorkspaceDetailResponse {
  id: string;
  branch?: string;
  runtimeStatus?: WorkspaceRuntimeStatus;
}

interface WorkspaceCliInstructionsResponse {
  workspaceId?: string;
  instructions?: string[];
  commands?: string[];
}

export interface CreateWorkspaceResult {
  workspaceId: string;
}

const API_BASE = '/workspaces';
const DEFAULT_BRANCH = 'main';
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 10;

// Helper function to build API URLs with proper trailing slashes
const buildApiUrl = (path?: string): string => {
  if (path) {
    return `${API_BASE}/${path}`;
  }
  return `${API_BASE}/`;
};
const READY_RUNTIME_STATUSES = new Set(['running', 'stopped']);

const buildDefaultCliInstructions = (workspaceId: string, branch?: string): WizardCLIInfo => ({
  workspaceId,
  instructions: ['login', 'enterCode', 'pull'],
  commands: [`workspace login`, `workspace pull ${workspaceId}`, `git checkout ${branch ?? DEFAULT_BRANCH}`],
});


interface RuntimeLogEntry {
  id: string;
  workspaceId: string;
  stage: string;
  message: string;
  metadata: Record<string, any>;
  createdAt: string;
}

export const workspaceWizardService = {
  async createWorkspace(payload: CreateWorkspacePayload): Promise<CreateWorkspaceResult> {
    // ownerId 不需要在前端指定，後端會從認證 token 中自動獲取當前用戶 ID
    const workspace = await apiClient.post<WorkspaceDetailResponse>(buildApiUrl(), {
      name: payload.name,
      description: payload.description,
      gitUrl: payload.gitUrl,
      runtime: payload.runtime,
      targetNamespace: payload.targetNamespace,
      setupScript: payload.setupScript,
      envVars: payload.envVars,
      portMappings: payload.portMappings,
      // 使用用戶選擇的分支，如果沒有則使用預設值
      branch: payload.branch || DEFAULT_BRANCH,
      cliType: payload.cliType,
    });

    return { workspaceId: workspace.id };
  },

  async pollWorkspaceReady(workspaceId: string): Promise<'ready'> {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      const workspace = await apiClient.get<WorkspaceDetailResponse>(buildApiUrl(workspaceId));
      const status = workspace.runtimeStatus?.status ?? 'stopped';
      if (READY_RUNTIME_STATUSES.has(status)) {
        return 'ready';
      }

      if (attempt < MAX_POLL_ATTEMPTS - 1) {
        await delay(POLL_INTERVAL_MS);
      }
    }

    throw new Error('Workspace is not ready in time');
  },

  async getCliInstructions(workspaceId: string): Promise<WizardCLIInfo> {
    try {
      const data = await apiClient.get<WorkspaceCliInstructionsResponse>(buildApiUrl(`${workspaceId}/cli-instructions`));
      return {
        workspaceId: data.workspaceId ?? workspaceId,
        instructions: data.instructions && data.instructions.length > 0 ? data.instructions : ['login', 'enterCode', 'pull'],
        commands: data.commands && data.commands.length > 0 ? data.commands : [`workspace login`, `workspace pull ${workspaceId}`],
      };
    } catch (error) {
      // 如果 404 或其他錯誤，回退到預設指令
      const workspace = await apiClient.get<WorkspaceDetailResponse>(buildApiUrl(workspaceId));
      return buildDefaultCliInstructions(workspace.id, workspace.branch);
    }
  },

  async getRuntimeLogs(workspaceId: string, limit: number = 50): Promise<RuntimeLogEntry[]> {
    return await apiClient.get<RuntimeLogEntry[]>(buildApiUrl(`${workspaceId}/runtime-logs?limit=${limit}`));
  },
};

export { MAX_POLL_ATTEMPTS, POLL_INTERVAL_MS };
