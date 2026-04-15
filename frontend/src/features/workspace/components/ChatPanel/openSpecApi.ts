import { ApiClient } from '@/shared/api/apiClient';

export type OpenSpecActionAvailability =
  | 'enabled'
  | 'disabled'
  | 'hidden'
  | 'setup_required'
  | 'sync_required'
  | 'blocked';

export type OpenSpecActionGroup = 'start' | 'plan' | 'implement' | 'finalize' | 'learn';
export type OpenSpecActionProfile = 'core' | 'expanded';
export type OpenSpecWorkspaceProfile = 'core' | 'expanded' | 'custom';
export type OpenSpecChangeStatus = 'in-progress' | 'complete' | 'archived';
export type OpenSpecActionInputKind = 'none' | 'change' | 'structured';

export interface OpenSpecChangeSummary {
  name: string;
  status?: string | null;
  completedTasks: number;
  totalTasks: number;
  lastModified?: string | null;
}

export interface OpenSpecActionItem {
  id: string;
  title: string;
  description: string;
  group: OpenSpecActionGroup;
  profile: OpenSpecActionProfile;
  availability: OpenSpecActionAvailability;
  reason?: string | null;
  recommended: boolean;
  recommendedReason?: string | null;
  requiresChange: boolean;
  supportsChangeArgument: boolean;
  inputKind: OpenSpecActionInputKind;
  exampleCommand?: string | null;
  draftTemplate: string;
}

export interface OpenSpecSpecDocument {
  capabilityName: string;
  path: string;
}

export interface OpenSpecNavigationChange {
  name: string;
  status: OpenSpecChangeStatus;
  archived: boolean;
  proposalPath?: string | null;
  designPath?: string | null;
  tasksPath?: string | null;
  specs: OpenSpecSpecDocument[];
  completedTasks: number;
  totalTasks: number;
  lastModified?: string | null;
}

export interface OpenSpecWorkspaceState {
  cliInstalled: boolean;
  cliVersion?: string | null;
  initialized: boolean;
  profile: OpenSpecWorkspaceProfile;
  projectSynced?: boolean | null;
  activeChanges: OpenSpecChangeSummary[];
}

export interface OpenSpecWorkspaceResponse {
  workspaceId: string;
  state: OpenSpecWorkspaceState;
  actions: OpenSpecActionItem[];
  changes: OpenSpecNavigationChange[];
}

export interface OpenSpecWorkspaceActionContext {
  subview?: OpenSpecChangeStatus;
  focusedChangeName?: string | null;
}

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

export const openSpecApi = {
  async getWorkspaceState(
    runtimeBaseUrl: string,
    workspaceId: string,
    context?: OpenSpecWorkspaceActionContext,
  ): Promise<OpenSpecWorkspaceResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const params = new URLSearchParams();
    if (context?.subview) {
      params.set('subview', context.subview);
    }
    if (context?.focusedChangeName) {
      params.set('focusedChangeName', context.focusedChangeName);
    }
    const query = params.toString();
    return client.get<OpenSpecWorkspaceResponse>(
      `/api/v1/workspaces/${workspaceId}/openspec${query ? `?${query}` : ''}`,
    );
  },
};
