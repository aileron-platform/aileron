export type JobStatus = 'active' | 'paused' | 'failed' | 'draft';

export type JobTrigger = 'cron' | 'manual' | 'webhook';

export interface JobNotifications {
  email: boolean;
  slack: boolean;
  webhook: boolean;
}

export interface AutomationJob {
  id: string;
  name: string;
  description: string;
  owner: string;
  userId: string;
  workspaceId: string;
  workspaceName?: string;
  prompt: string;
  status: JobStatus;
  trigger: JobTrigger;
  schedule: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string;
  nextRunAt?: string;
  successRate: number;
  failureRate: number;
  totalExecutions: number;
  averageDuration: number;
  lastDuration?: number;
  notifications: JobNotifications;
  metadata: Record<string, unknown>;
  webhookApiKey?: string;
}

export interface JobCreateInput {
  name: string;
  description: string;
  owner: string;
  userId: string;
  workspaceId: string;
  prompt: string;
  status: JobStatus;
  trigger: JobTrigger;
  schedule: string;
  tags: string[];
  notifications: JobNotifications;
  metadata: Record<string, unknown>;
  webhookApiKey?: string;
}

export interface JobUpdateInput extends JobCreateInput {
  id: string;
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

export type JobExecutionStatus =
  | 'queued'      // 已加入 Celery 佇列，等待 Worker 處理
  | 'waiting'     // 等待工作區鎖釋放（排隊中）
  | 'running'     // 正在執行
  | 'success'     // 執行成功
  | 'failed'      // 執行失敗
  | 'cancelled'   // 已取消（使用者主動取消）
  | 'timeout';    // 執行超時

export interface JobExecution {
  id: string;
  jobId: string;
  status: JobExecutionStatus;
  trigger: JobTrigger;
  startedAt?: string;
  finishedAt?: string;
  duration?: number;
  sessionId?: string;
  errorMessage?: string;
  summary: string;
  executionMetadata?: Record<string, unknown>;
  queuePosition?: number;  // 排隊位置（1-based）
  queuedAt?: string;       // 加入佇列時間
}

export interface JobExecutionListResponse {
  items: JobExecution[];
  total: number;
}

export interface JobCalendarEvent {
  id: string;
  jobId: string;
  title: string;
  start: string;
  end: string;
  status: JobExecutionStatus;
}

export interface JobCalendarResponse {
  items: JobCalendarEvent[];
  total: number;
}

export interface JobListResponse {
  items: AutomationJob[];
  total: number;
}

export interface JobStatusUpdateInput {
  status: JobStatus;
}

export interface QueuePosition {
  executionId: string;
  position: number;
  total: number;
  estimatedWaitSeconds?: number;
}

export interface WorkspaceQueueResponse {
  workspaceId: string;
  queueLength: number;
  executions: JobExecution[];
}

export interface ExecutionCancelResponse {
  executionId: string;
  status: string;
  message: string;
  cancelled: boolean;
}


