/**
 * Task 相關類型定義
 */

export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent';

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'queued';

export type TaskType =
  | 'execute_script'
  | 'execute_command'
  | 'run_pipeline'
  | 'create_container'
  | 'setup_workspace'
  | 'scheduled_task'
  | 'other';

export interface TaskMetadata {
  instruction?: string;
  schedule_type?: string;
  model?: string;
  [key: string]: unknown;
}

export interface TaskLog {
  timestamp: string;
  level: string;
  message: string;
  execution_id?: string;
  session_id?: string;
}

export interface Task {
  id: string;
  workspace_id: string;
  title: string;
  status: TaskStatus;
  type: TaskType;
  priority: TaskPriority;
  args: unknown[];
  env_vars: Record<string, string>;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  progress?: number;
  logs: TaskLog[];
  max_retries: number;
  retry_count: number;
  error_message?: string;
  metadata?: TaskMetadata;
}

export interface TaskLogResponse {
  success: boolean;
  logs: TaskLog[];
}
