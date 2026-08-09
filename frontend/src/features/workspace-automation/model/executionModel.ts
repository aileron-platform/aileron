import type { JobExecution, JobExecutionStatus } from './automationTypes';

const ACTIVE_EXECUTION_STATUSES: JobExecutionStatus[] = ['running', 'queued'];

export const hasActiveExecutions = (executions: JobExecution[]): boolean => {
  return executions.some(exec => ACTIVE_EXECUTION_STATUSES.includes(exec.status));
};
