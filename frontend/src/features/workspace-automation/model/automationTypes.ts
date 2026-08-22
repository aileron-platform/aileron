export type JobStatus = 'active' | 'paused' | 'completed';

export type JobTrigger = 'cron' | 'manual' | 'webhook' | 'at' | 'every';

export interface AutomationAgentConfigInput {
  mode?: string | null;
}

export interface AutomationAgentConfigSnapshot {
  mode: string | null;
  permissionMode: 'bypassPermissions';
}

export interface AutomationJob {
  id: string;
  name: string;
  description: string | null;
  workspaceId: string;
  creatorUserId: string;
  creatorDisplayName: string;
  workspaceName?: string;
  prompt: string;
  status: JobStatus;
  trigger: JobTrigger;
  schedule: string;
  exact?: boolean;
  agenticTool: string;
  model: string;
  agentConfig: AutomationAgentConfigSnapshot;
  worktreeKey: string;
  worktreeBranch: string;
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string;
  nextRunAt?: string;
  successRate: number;
  totalExecutions: number;
  averageDuration: number;
  lastDuration?: number;
  webhookConfigured: boolean;
  deliveryWebhookUrl: string | null;
  failureDestination: string | null;
  deletedAt: string | null;
}

export interface JobCreateInput {
  name: string;
  description?: string | null;
  workspaceId: string;
  prompt: string;
  trigger: JobTrigger;
  schedule: string;
  exact?: boolean;
  agenticTool?: string | null;
  model?: string | null;
  agentConfig?: AutomationAgentConfigInput | null;
  webhookApiKey?: string | null;
  deliveryWebhookUrl?: string | null;
  failureDestination?: string | null;
}

export interface JobUpdateInput extends Omit<JobCreateInput, 'workspaceId'> {
  id: string;
  status?: 'active' | 'paused';
}

export interface AutomationMetrics {
  activeCount: number;
  pausedCount: number;
  failedCount: number;
  draftCount: number;
  successRate: number;
  runningExecutions: number;
  queuedExecutions: number;
  averageDuration: number;
}

export interface AutomationWorkspaceSummary {
  id: string;
  name: string;
  accessSource?: 'owned' | 'shared';
  runtimeUrl?: string;
}

export type JobExecutionStatus =
  | 'queued'
  | 'running'
  | 'success'
  | 'failed'
  | 'cancelled';

export interface JobExecution {
  id: string;
  jobId: string;
  workspaceId: string;
  status: JobExecutionStatus;
  trigger: JobTrigger;
  scheduledFor: string;
  queuedAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  cancelRequestedAt: string | null;
  queuePosition: number | null;
  errorCode: string | null;
  errorMessage: string | null;
}

export interface JobExecutionListResponse {
  items: JobExecution[];
  total: number;
  page: number;
  pageSize: number;
}

export interface JobExecutionPageParams {
  page: number;
  pageSize: number;
  rangeStart?: string;
  rangeEnd?: string;
}

export interface JobListResponse {
  items: AutomationJob[];
  total: number;
}
