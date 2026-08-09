import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '@/shared/api/apiClient';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import {
  WorkspaceDeleteJobError,
  WorkspaceDeleteTimeoutError,
  workspaceLifecycleApi,
  type WorkspaceDeletePollResponse,
  type WorkspaceDeletionProgressSnapshot,
  type WorkspaceDeletionProgressStatus,
  type WorkspaceRuntimeJobSummary,
} from '../api/workspaceLifecycleApi';
import { useWorkspaceDeleteFallback } from './useWorkspaceDeleteFallback';

const logger = createLogger('useWorkspaceDeletion');
const completedDeletionWorkspaceIds = new Set<string>();

export interface WorkspaceDeletionController {
  isDeleting: boolean;
  progress: WorkspaceDeletionProgressSnapshot | null;
  requestDelete: (confirmationName: string) => Promise<boolean>;
}

interface UseWorkspaceDeletionInput {
  workspaceId: string | null;
  workspaceName: string | null;
  runtimeBaseUrl?: string | null;
  canDelete: boolean;
  shouldDiscoverExistingJob: boolean;
  isDeletionInProgress: boolean;
}

const getErrorCode = (error: unknown): string | null => {
  if (error instanceof WorkspaceDeleteJobError) {
    return error.errorCode ?? null;
  }
  if (error instanceof ApiError) {
    return error.errorCode ?? null;
  }
  if (
    error
    && typeof error === 'object'
    && 'errorCode' in error
    && typeof error.errorCode === 'string'
  ) {
    return error.errorCode;
  }
  return null;
};

const isWorkspaceDeletionJob = (
  job: WorkspaceRuntimeJobSummary | null | undefined,
): job is WorkspaceRuntimeJobSummary => (
  Boolean(job && job.operation === 'workspace_delete')
);

const progressStatus = (status: string): WorkspaceDeletionProgressStatus => {
  if (status === 'failed') {
    return 'failed';
  }
  return status === 'queued' ? 'queued' : 'running';
};

const toProgress = (
  snapshot: WorkspaceDeletionProgressSnapshot,
): WorkspaceDeletionProgressSnapshot => ({
  ...snapshot,
  status: progressStatus(snapshot.status),
});

const snapshotFromJob = (
  job: WorkspaceRuntimeJobSummary,
): WorkspaceDeletionProgressSnapshot => ({
  jobId: job.id,
  status: progressStatus(job.status),
  phase: job.status === 'queued' ? 'queued' : job.phase ?? null,
  errorCode: job.errorCode ?? null,
});

const isNotFound = (error: unknown): boolean => (
  error instanceof ApiError && error.status === 404
);

export const useWorkspaceDeletion = ({
  workspaceId,
  workspaceName,
  runtimeBaseUrl = null,
  canDelete,
  shouldDiscoverExistingJob,
  isDeletionInProgress,
}: UseWorkspaceDeletionInput): WorkspaceDeletionController => {
  const { t } = useI18n();
  const { toast } = useToast();
  const resolveDeleteFallback = useWorkspaceDeleteFallback();
  const [progress, setProgress] = useState<WorkspaceDeletionProgressSnapshot | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);
  const progressRef = useRef<WorkspaceDeletionProgressSnapshot | null>(null);
  const activeMonitorWorkspaceRef = useRef<string | null>(null);
  const discoveryKeyRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const updateProgress = useCallback((next: WorkspaceDeletionProgressSnapshot | null) => {
    progressRef.current = next;
    if (mountedRef.current) {
      setProgress(next);
    }
  }, []);

  const showFailureToast = useCallback((error: unknown) => {
    const descriptionKey = error instanceof WorkspaceDeleteTimeoutError
      ? 'workspace.workspaceSettings.reset.delete.error.timeout'
      : getErrorCode(error) === 'RESOURCE_DELETE_CONFIRMATION_MISMATCH'
        ? 'workspace.workspaceSettings.reset.delete.error.confirmationMismatch'
        : 'workspace.workspaceSettings.reset.delete.error.description';
    toast({
      title: t('workspace.workspaceSettings.reset.delete.error.title'),
      description: t(descriptionKey),
      variant: 'destructive',
    });
  }, [t, toast]);

  const completeDeletion = useCallback(async () => {
    if (!workspaceId) {
      return;
    }
    updateProgress(null);
    if (completedDeletionWorkspaceIds.has(workspaceId)) {
      return;
    }
    completedDeletionWorkspaceIds.add(workspaceId);
    await resolveDeleteFallback({
      deletedWorkspaceId: workspaceId,
      deletedRuntimeBaseUrl: runtimeBaseUrl,
    });
    toast({
      title: t('workspace.workspaceSettings.reset.delete.success.title'),
      description: t('workspace.workspaceSettings.reset.delete.success.description'),
      variant: 'default',
    });
  }, [resolveDeleteFallback, runtimeBaseUrl, t, toast, updateProgress, workspaceId]);

  const monitorDeletion = useCallback((jobId?: string) => {
    if (!workspaceId || activeMonitorWorkspaceRef.current === workspaceId) {
      return;
    }

    activeMonitorWorkspaceRef.current = workspaceId;
    updateProgress(progressRef.current ?? {
      jobId: jobId ?? 'pending',
      status: 'queued',
      phase: null,
      errorCode: null,
    });

    void (async () => {
      try {
        await workspaceLifecycleApi.waitForWorkspaceDeletion(workspaceId, jobId, {
          onProgress: snapshot => updateProgress(toProgress(snapshot)),
        });
        await completeDeletion();
      } catch (error) {
        const previous = progressRef.current;
        updateProgress({
          jobId: previous?.jobId ?? jobId ?? 'unknown',
          status: 'failed',
          phase: previous?.phase ?? null,
          errorCode: getErrorCode(error),
        });
        showFailureToast(error);
      } finally {
        activeMonitorWorkspaceRef.current = null;
        isSubmittingRef.current = false;
        if (mountedRef.current) {
          setIsSubmitting(false);
        }
      }
    })();
  }, [completeDeletion, showFailureToast, updateProgress, workspaceId]);

  useEffect(() => {
    if (!workspaceId || !shouldDiscoverExistingJob) {
      return;
    }

    const discoveryKey = `${workspaceId}:${isDeletionInProgress ? 'deleting' : 'available'}`;
    if (discoveryKeyRef.current === discoveryKey) {
      return;
    }
    discoveryKeyRef.current = discoveryKey;
    let cancelled = false;

    if (isDeletionInProgress && !progressRef.current) {
      updateProgress({
        jobId: 'pending',
        status: 'queued',
        phase: null,
        errorCode: null,
      });
    }

    const discover = async () => {
      try {
        const snapshot: WorkspaceDeletePollResponse =
          await workspaceLifecycleApi.getWorkspaceDeletionStatus(workspaceId);
        if (cancelled) {
          return;
        }
        const job = snapshot.runtimeJob;
        if (!isWorkspaceDeletionJob(job)) {
          if (isDeletionInProgress) {
            monitorDeletion();
          }
          return;
        }
        updateProgress(snapshotFromJob(job));
        if (job.status !== 'failed') {
          monitorDeletion(job.id);
        }
      } catch (error) {
        if (cancelled || isNotFound(error)) {
          return;
        }
        logger.warn('Workspace deletion job discovery failed', {
          error,
          workspaceId,
        });
      }
    };

    void discover();
    return () => {
      cancelled = true;
    };
  }, [
    isDeletionInProgress,
    monitorDeletion,
    shouldDiscoverExistingJob,
    updateProgress,
    workspaceId,
  ]);

  const requestDelete = useCallback(async (confirmationName: string): Promise<boolean> => {
    if (
      !workspaceId
      || !workspaceName
      || !canDelete
      || confirmationName !== workspaceName
      || activeMonitorWorkspaceRef.current === workspaceId
      || isSubmitting
      || isSubmittingRef.current
    ) {
      return false;
    }

    completedDeletionWorkspaceIds.delete(workspaceId);
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      const command = await workspaceLifecycleApi.deleteWorkspace(workspaceId, confirmationName);
      updateProgress({
        jobId: command.jobId,
        status: command.status === 'queued' ? 'queued' : 'running',
        phase: null,
        errorCode: null,
      });
      monitorDeletion(command.jobId);
      return true;
    } catch (error) {
      if (isNotFound(error)) {
        await completeDeletion();
        isSubmittingRef.current = false;
        setIsSubmitting(false);
        return true;
      }
      updateProgress({
        jobId: 'request',
        status: 'failed',
        phase: null,
        errorCode: getErrorCode(error),
      });
      isSubmittingRef.current = false;
      setIsSubmitting(false);
      showFailureToast(error);
      return false;
    }
  }, [
    canDelete,
    completeDeletion,
    isSubmitting,
    monitorDeletion,
    showFailureToast,
    updateProgress,
    workspaceId,
    workspaceName,
  ]);

  const isDeleting = isSubmitting
    || activeMonitorWorkspaceRef.current === workspaceId
    || progress?.status === 'queued'
    || progress?.status === 'running';

  return {
    isDeleting,
    progress,
    requestDelete,
  };
};
