import type { ThreadStatus } from './threadModel';

export type MinimalStatus = 'draft' | 'pending' | 'active' | 'finishing' | 'complete' | 'error';

const MINIMAL_STATUS_MAP: Record<ThreadStatus, MinimalStatus> = {
  draft: 'draft',
  queued: 'pending',
  booting: 'active',
  working: 'active',
  stopping: 'finishing',
  complete: 'complete',
  stopped: 'complete',
  canceled: 'complete',
  error: 'error',
};

const RUNNING_STATUSES: ReadonlySet<ThreadStatus> = new Set(['queued', 'booting', 'working', 'stopping']);

export const toMinimalStatus = (status: ThreadStatus): MinimalStatus => MINIMAL_STATUS_MAP[status];

export const isRunning = (status: ThreadStatus): boolean => RUNNING_STATUSES.has(status);

export const canRetry = (status: ThreadStatus): boolean => status === 'error';

export const isLocked = (status: ThreadStatus): boolean => status !== 'draft';
