import type { JobExecutionStatus } from './automationTypes';
import { ApiError } from '@/shared/api/apiClient';

export const EXECUTION_STATUS_LABEL_KEY: Record<JobExecutionStatus, string> = {
  queued: 'automation.execution.status.queued',
  running: 'automation.execution.status.running',
  success: 'automation.execution.status.success',
  failed: 'automation.execution.status.failed',
  cancelled: 'automation.execution.status.cancelled',
};

export const getExecutionStatusLabelKey = (status: JobExecutionStatus): string => {
  return EXECUTION_STATUS_LABEL_KEY[status];
};

export const getAutomationRunErrorKey = (error: unknown): string =>
  error instanceof ApiError &&
  error.status === 409 &&
  error.errorCode === 'automation_queue_full'
    ? 'automation.errors.automation_queue_full'
    : 'automation.errors.runFailed';

export const POLLING_CONFIG = {
  /** Polling interval in milliseconds. */
  INTERVAL_MS: 3000,
} as const;
