import { JobExecutionStatus } from './types';

export const EXECUTION_STATUS_LABEL_KEY: Record<JobExecutionStatus, string> = {
  queued: 'automation.execution.status.queued',
  waiting: 'automation.execution.status.waiting',
  running: 'automation.execution.status.running',
  success: 'automation.execution.status.success',
  failed: 'automation.execution.status.failed',
  cancelled: 'automation.execution.status.cancelled',
  timeout: 'automation.execution.status.timeout',
};

export const getExecutionStatusLabelKey = (status: JobExecutionStatus): string => {
  return EXECUTION_STATUS_LABEL_KEY[status] ?? 'automation.execution.status.unknown';
};

/**
 * 輪詢設定
 */
export const POLLING_CONFIG = {
  /** 輪詢間隔（毫秒） */
  INTERVAL_MS: 3000,
  /** 手動重新整理動畫持續時間（毫秒） */
  REFRESH_ANIMATION_DURATION_MS: 500,
} as const;
