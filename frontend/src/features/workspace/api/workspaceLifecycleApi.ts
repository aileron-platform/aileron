import { apiClient, ApiError } from '@/shared/api/apiClient';
import { z } from 'zod';

export interface WorkspaceLifecycleCommandResponse {
  workspaceId: string;
  status: string;
  jobId: string;
  correlationId: string;
  rootCorrelationId: string;
}

export const WORKSPACE_DELETION_PHASES = [
  'queued',
  'cancelling_automations',
  'stopping_runtime',
  'deleting_resources',
  'finalizing',
] as const;

export type WorkspaceDeletionPhase = typeof WORKSPACE_DELETION_PHASES[number];

export const WORKSPACE_DELETION_ACTIONS = ['delete', 'retry'] as const;

export type WorkspaceDeletionProgressStatus = 'queued' | 'running' | 'failed';

export interface WorkspaceDeletionProgressSnapshot {
  jobId: string;
  status: WorkspaceDeletionProgressStatus;
  phase: WorkspaceDeletionPhase | null;
  errorCode: string | null;
}

export type WorkspaceLifecycleComponent = 'runtime' | 'browser' | 'canvas';

export interface WorkspaceComponentLifecycleCommandResponse
  extends WorkspaceLifecycleCommandResponse {
  component: WorkspaceLifecycleComponent;
  targetRevision: number;
}

export interface BrowserAccessResponse {
  browserUrl: string;
  password: string;
  credentialRevision: number;
  iceServers: RTCIceServer[];
}

export interface BrowserCredentialRotationResponse {
  jobId: string;
  status: string;
  credentialRevision: number;
  appliedOnNextStart: boolean;
}

export const WORKSPACE_AVAILABILITY_STATES = [
  'ready',
  'transitioning',
  'stopped',
  'blocked',
  'deleting',
  'not_found',
] as const;

export type WorkspaceAvailability = typeof WORKSPACE_AVAILABILITY_STATES[number];

export const WORKSPACE_AVAILABILITY_ACTIONS = [
  'start',
  'retry',
  'rebuild',
  'return',
] as const;

export type WorkspaceAvailabilityAction = typeof WORKSPACE_AVAILABILITY_ACTIONS[number];

export const WORKSPACE_KNOWLEDGE_MOUNT_STATES = [
  'ready',
  'syncing',
  'degraded',
] as const;

export type WorkspaceKnowledgeMountState =
  typeof WORKSPACE_KNOWLEDGE_MOUNT_STATES[number];

export const WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE =
  'WORKSPACE_EXECUTION_PLANE_DRIFT' as const;

export const WORKSPACE_AVAILABILITY_REASON_CODES = [
  'WORKSPACE_AUTHENTICATION_REQUIRED',
  'WORKSPACE_ACCESS_DENIED',
  'WORKSPACE_READY',
  'WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS',
  'WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED',
  'WORKSPACE_RUNTIME_STARTING',
  'WORKSPACE_RUNTIME_RESTARTING',
  'WORKSPACE_RUNTIME_STOPPING',
  'WORKSPACE_RUNTIME_STOPPED',
  'WORKSPACE_RUNTIME_ERROR',
  'WORKSPACE_RUNTIME_INSTANCE_UNAVAILABLE',
  'WORKSPACE_DELETING',
  'WORKSPACE_NOT_FOUND',
  'WORKSPACE_AVAILABILITY_ACTION_NOT_ALLOWED',
  'WORKSPACE_AVAILABILITY_ACTION_ACCEPTED',
  'WORKSPACE_RUNTIME_INSTANCE_MISMATCH',
  'WORKSPACE_BROWSER_WORKLOAD_NOT_READY',
  'WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE',
  'WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS',
  WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE,
] as const;

export type WorkspaceAvailabilityReasonCode =
  typeof WORKSPACE_AVAILABILITY_REASON_CODES[number];

export type WorkspaceAvailabilityMutationAction = Exclude<
  WorkspaceAvailabilityAction,
  'return'
>;

export interface WorkspaceKnowledgeMountAvailability {
  status: WorkspaceKnowledgeMountState;
  desiredRevision: number;
  observedRevision: number;
  lastKnownGoodRevision: number;
  errorCode: string | null;
  compensating: boolean;
}

export interface WorkspaceAvailabilityResponse {
  workspaceId: string;
  availability: WorkspaceAvailability;
  reasonCode: WorkspaceAvailabilityReasonCode;
  runtimeStatus: string | null;
  runtimeInstanceId: string | null;
  runtimeAccessDesiredRevision: number;
  runtimeAccessObservedRevision: number;
  retryable: boolean;
  allowedActions: WorkspaceAvailabilityAction[];
  retryAfterMs: number | null;
  knowledgeMountStatus: WorkspaceKnowledgeMountAvailability;
  deletion: WorkspaceDeletionProjection;
}

const workspaceAvailabilityResponseSchema = z.object({
  workspaceId: z.string(),
  availability: z.enum(WORKSPACE_AVAILABILITY_STATES),
  reasonCode: z.enum(WORKSPACE_AVAILABILITY_REASON_CODES),
  runtimeStatus: z.string().nullable(),
  runtimeInstanceId: z.string().nullable(),
  runtimeAccessDesiredRevision: z.number(),
  runtimeAccessObservedRevision: z.number(),
  retryable: z.boolean(),
  allowedActions: z.array(z.enum(WORKSPACE_AVAILABILITY_ACTIONS)),
  retryAfterMs: z.number().nullable(),
  knowledgeMountStatus: z.object({
    status: z.enum(WORKSPACE_KNOWLEDGE_MOUNT_STATES),
    desiredRevision: z.number(),
    observedRevision: z.number(),
    lastKnownGoodRevision: z.number(),
    errorCode: z.string().nullable(),
    compensating: z.boolean(),
  }),
  deletion: z.object({
    availability: z.enum(WORKSPACE_AVAILABILITY_STATES),
    allowedActions: z.array(z.enum(WORKSPACE_DELETION_ACTIONS)),
    phase: z.enum(WORKSPACE_DELETION_PHASES).nullable(),
    status: z.enum(['queued', 'running', 'failed']).nullable(),
    errorCode: z.string().nullable(),
  }),
});

export const parseWorkspaceAvailabilityResponse = (
  payload: unknown,
): WorkspaceAvailabilityResponse => {
  const result = workspaceAvailabilityResponseSchema.safeParse(payload);
  if (!result.success) {
    throw new Error('workspace_availability_contract_invalid');
  }
  return result.data;
};

export type WorkspaceDeletionAction = typeof WORKSPACE_DELETION_ACTIONS[number];
export type WorkspaceDeletionStatus = 'queued' | 'running' | 'failed';

export interface WorkspaceDeletionProjection {
  availability: WorkspaceAvailability;
  allowedActions: WorkspaceDeletionAction[];
  phase: WorkspaceDeletionPhase | null;
  status: WorkspaceDeletionStatus | null;
  errorCode: string | null;
}

export interface WorkspaceAvailabilityActionResponse {
  workspaceId: string;
  action: WorkspaceAvailabilityMutationAction;
  jobId: string;
  status: string;
  reasonCode: string;
}

export interface WorkspaceRuntimeJobSummary {
  id: string;
  operation?: string;
  status: string;
  phase?: WorkspaceDeletionPhase | null;
  errorCode?: string | null;
}

export interface WorkspaceDeletePollResponse {
  runtimeJob?: WorkspaceRuntimeJobSummary | null;
}

export interface WorkspaceDeletePollOptions {
  pollIntervalMs?: number;
  timeoutMs?: number;
  onProgress?: (progress: WorkspaceDeletionProgressSnapshot) => void;
}

export class WorkspaceDeleteJobError extends Error {
  readonly errorCode?: string | null;
  readonly phase?: WorkspaceDeletionPhase | null;

  constructor(errorCode?: string | null, phase?: WorkspaceDeletionPhase | null) {
    super('workspace_delete_failed');
    this.name = 'WorkspaceDeleteJobError';
    this.errorCode = errorCode;
    this.phase = phase;
  }
}

export class WorkspaceDeleteTimeoutError extends Error {
  constructor() {
    super('workspace_delete_timeout');
    this.name = 'WorkspaceDeleteTimeoutError';
  }
}

const delay = async (milliseconds: number): Promise<void> => {
  await new Promise(resolve => window.setTimeout(resolve, milliseconds));
};

export const workspaceLifecycleApi = {
  async getAvailability(
    workspaceId: string,
    signal?: AbortSignal,
  ): Promise<WorkspaceAvailabilityResponse> {
    const payload = await apiClient.get<unknown>(
      `/workspaces/${encodeURIComponent(workspaceId)}/availability`,
      { signal },
    );
    return parseWorkspaceAvailabilityResponse(payload);
  },

  async runAvailabilityAction(
    workspaceId: string,
    action: WorkspaceAvailabilityMutationAction,
  ): Promise<WorkspaceAvailabilityActionResponse> {
    return await apiClient.post<WorkspaceAvailabilityActionResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/availability/actions/${action}`,
    );
  },

  async stopWorkspace(
    workspaceId: string,
  ): Promise<WorkspaceLifecycleCommandResponse> {
    return await apiClient.post<WorkspaceLifecycleCommandResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/stop`,
    );
  },

  async deleteWorkspace(
    workspaceId: string,
    confirmationName: string,
  ): Promise<WorkspaceLifecycleCommandResponse> {
    return await apiClient.delete<WorkspaceLifecycleCommandResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}`,
      undefined,
      { confirmationName },
    );
  },

  async getWorkspaceDeletionStatus(
    workspaceId: string,
  ): Promise<WorkspaceDeletePollResponse> {
    return await apiClient.get<WorkspaceDeletePollResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}`,
    );
  },

  async waitForWorkspaceDeletion(
    workspaceId: string,
    jobId?: string,
    options: WorkspaceDeletePollOptions = {},
  ): Promise<void> {
    const pollIntervalMs = options.pollIntervalMs ?? 1000;
    const timeoutMs = options.timeoutMs ?? 120_000;
    const deadline = Date.now() + timeoutMs;
    const path = `/workspaces/${encodeURIComponent(workspaceId)}`;
    let activeJobId = jobId ?? null;

    while (Date.now() <= deadline) {
      try {
        const workspace = await apiClient.get<WorkspaceDeletePollResponse>(path);
        const runtimeJob = workspace.runtimeJob;
        const isDeletionJob = Boolean(
          runtimeJob
          && (
            runtimeJob.id === activeJobId
            || runtimeJob.operation === 'workspace_delete'
          ),
        );
        if (runtimeJob && isDeletionJob) {
          activeJobId = runtimeJob.id;
          options.onProgress?.({
            jobId: runtimeJob.id,
            status: runtimeJob.status === 'failed'
              ? 'failed'
              : runtimeJob.status === 'queued'
                ? 'queued'
                : 'running',
            phase: runtimeJob.status === 'queued'
              ? 'queued'
              : runtimeJob.phase ?? null,
            errorCode: runtimeJob.errorCode ?? null,
          });
        }
        if (
          runtimeJob
          && isDeletionJob
          && runtimeJob.status === 'failed'
        ) {
          throw new WorkspaceDeleteJobError(runtimeJob.errorCode, runtimeJob.phase);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return;
        }
        throw error;
      }

      await delay(pollIntervalMs);
    }

    throw new WorkspaceDeleteTimeoutError();
  },

  async restartComponent(
    workspaceId: string,
    component: WorkspaceLifecycleComponent,
  ): Promise<WorkspaceComponentLifecycleCommandResponse> {
    return await apiClient.post<WorkspaceComponentLifecycleCommandResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/components/${component}/restart`,
    );
  },

  async accessBrowser(workspaceId: string): Promise<BrowserAccessResponse> {
    return await apiClient.post<BrowserAccessResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/browser/access`,
    );
  },

  async rotateBrowserCredentials(
    workspaceId: string,
  ): Promise<BrowserCredentialRotationResponse> {
    return await apiClient.post<BrowserCredentialRotationResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/browser/credentials/rotate`,
    );
  },
};
