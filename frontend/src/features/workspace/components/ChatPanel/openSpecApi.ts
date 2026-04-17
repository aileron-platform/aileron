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
export type OpenSpecDesignerSection = 'overview' | 'project-config' | 'schemas' | 'validation';
export type OpenSpecCustomizationFileKind = 'config' | 'schema' | 'template';

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

export interface OpenSpecCustomizationTemplateFile {
  name: string;
  path: string;
}

export interface OpenSpecCustomizationSchema {
  name: string;
  path: string;
  schemaPath: string;
  isDefault: boolean;
  isInvalid: boolean;
  templateFiles: OpenSpecCustomizationTemplateFile[];
}

export interface OpenSpecCustomizationState {
  workspaceId: string;
  configPath: string;
  configPresent: boolean;
  defaultSchema?: string | null;
  builtInSchemas: string[];
  schemas: OpenSpecCustomizationSchema[];
}

export interface OpenSpecCustomizationFileResponse {
  workspaceId: string;
  path: string;
  name: string;
  kind: OpenSpecCustomizationFileKind;
  content: string;
  editable: boolean;
  language: 'yaml' | 'markdown';
  schemaName?: string | null;
  metadata: Record<string, unknown>;
}

export interface OpenSpecCustomizationActionResponse {
  success: boolean;
  message: string;
  schemaName?: string | null;
  path?: string | null;
}

export interface OpenSpecCustomizationDiagnostic {
  level: 'info' | 'warning' | 'error';
  message: string;
}

export interface OpenSpecCustomizationValidationResult {
  workspaceId: string;
  targetPath: string;
  schemaName?: string | null;
  valid: boolean;
  diagnostics: OpenSpecCustomizationDiagnostic[];
}

export interface OpenSpecCustomizationResolutionStep {
  order: number;
  label: string;
  value?: string | null;
  selected: boolean;
}

export interface OpenSpecCustomizationDebugResult {
  workspaceId: string;
  targetPath: string;
  schemaName?: string | null;
  resolvedName?: string | null;
  source?: string | null;
  path?: string | null;
  resolutionOrder: OpenSpecCustomizationResolutionStep[];
}

export interface OpenSpecDesignerSchemaDetail {
  name: string;
  source: 'project' | 'package';
  path: string;
  description?: string | null;
  version?: number | null;
  isDefault: boolean;
  artifacts: Array<Record<string, unknown>>;
  apply: {
    requires: string[];
    tracks?: string | null;
  };
  rawSchema: string;
}

export interface OpenSpecDesignerValidationResult {
  valid: boolean;
  diagnostics: OpenSpecCustomizationDiagnostic[];
  resolutionSource?: string | null;
  resolutionPath?: string | null;
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

  async getCustomizationState(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<OpenSpecCustomizationState> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return client.get<OpenSpecCustomizationState>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization`,
    );
  },

  async getCustomizationFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    path: string,
  ): Promise<OpenSpecCustomizationFileResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const params = new URLSearchParams({ path });
    return client.get<OpenSpecCustomizationFileResponse>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/file?${params.toString()}`,
    );
  },

  async updateCustomizationFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    path: string,
    content: string,
  ): Promise<OpenSpecCustomizationActionResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const params = new URLSearchParams({ path });
    return client.put<OpenSpecCustomizationActionResponse>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/file?${params.toString()}`,
      { content },
    );
  },

  async forkCustomizationSchema(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: {
      sourceSchema: string;
      destinationSchema: string;
    },
  ): Promise<OpenSpecCustomizationActionResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return client.post<OpenSpecCustomizationActionResponse>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/schemas/fork`,
      payload,
    );
  },

  async initCustomizationSchema(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: {
      name: string;
      description?: string;
      artifacts?: string[];
    },
  ): Promise<OpenSpecCustomizationActionResponse> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return client.post<OpenSpecCustomizationActionResponse>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/schemas`,
      payload,
    );
  },

  async validateCustomization(
    runtimeBaseUrl: string,
    workspaceId: string,
    path: string,
  ): Promise<OpenSpecCustomizationValidationResult> {
    const client = createRuntimeClient(runtimeBaseUrl);
    return client.post<OpenSpecCustomizationValidationResult>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/validate`,
      { path },
    );
  },

  async debugCustomization(
    runtimeBaseUrl: string,
    workspaceId: string,
    path: string,
  ): Promise<OpenSpecCustomizationDebugResult> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const params = new URLSearchParams({ path });
    return client.get<OpenSpecCustomizationDebugResult>(
      `/api/v1/workspaces/${workspaceId}/openspec/customization/debug?${params.toString()}`,
    );
  },
};
