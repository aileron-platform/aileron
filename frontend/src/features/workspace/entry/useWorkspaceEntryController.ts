import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '@/shared/api/apiClient';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';
import { useAuth } from '@/features/auth/public';
import type {
  WorkspaceEntryActionId,
  WorkspaceEntryProjection,
  WorkspaceEntryProjectionInput,
} from '@/shared/components/entry/workspaceEntryTypes';
import { projectWorkspaceEntry } from './workspaceEntryProjection';
import { useWorkspaceAvailabilityController } from '../availability/useWorkspaceAvailabilityController';
import {
  WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE,
  type WorkspaceAvailabilityResponse,
} from '../api/workspaceLifecycleApi';
import { useWorkspaceRuntime, type UseWorkspaceRuntimeReturn } from '../hooks/useWorkspaceRuntime';
import { resolveWorkspacePermissions } from '../model/workspacePermissions';
import {
  useWorkspaceDeletion,
  type WorkspaceDeletionController,
} from '../hooks/useWorkspaceDeletion';

export interface WorkspaceEntryController {
  workspaceRuntime: UseWorkspaceRuntimeReturn;
  projection: WorkspaceEntryProjection;
  isPending: boolean;
  onAction: (action: WorkspaceEntryActionId) => void;
  deletion: WorkspaceDeletionController & {
    canShowEntry: boolean;
    isDeletionInProgress: boolean;
  };
}

const getLoadErrorReasonCode = (error: Error | null): string => (
  error instanceof ApiError && error.errorCode
    ? error.errorCode
    : 'WORKSPACE_AVAILABILITY_UNCERTAIN'
);

const getWorkspaceStatus = (
  isAuthorizationResolved: boolean,
  canRead: boolean,
  errorCode: string | null,
): WorkspaceEntryProjectionInput['workspace'] => {
  if (!isAuthorizationResolved) {
    return { status: 'checking' };
  }
  if (canRead) {
    return { status: 'ready', canCreate: false };
  }
  return {
    status: errorCode === 'WORKSPACE_NOT_FOUND' ? 'not_found' : 'denied',
    allowedActions: ['return'],
    reasonCode: errorCode ?? 'WORKSPACE_ACCESS_DENIED',
  };
};

const getAvailabilitySource = (
  view: {
    kind: string;
    availability?: WorkspaceAvailabilityResponse | null;
    loadError?: Error | null;
    actionErrorCode?: string | null;
  },
): {
  workspaceOverride?: WorkspaceEntryProjectionInput['workspace'];
  execution: WorkspaceEntryProjectionInput['execution'];
} => {
  if (view.kind === 'execution') {
    return {
      execution: {
        status: 'ready',
        allowedActions: [],
      },
    };
  }

  if (
    view.kind === 'authorization-check'
    || view.kind === 'pending-shell'
    || view.kind === 'redirecting'
  ) {
    return {
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }

  const availability = view.availability;
  if (availability?.deletion?.status === 'failed') {
    return {
      workspaceOverride: {
        status: 'failed',
        allowedActions: availability.allowedActions.filter(action => action === 'return'),
        reasonCode: availability.deletion.errorCode ?? availability.reasonCode,
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }
  if (availability?.deletion?.availability === 'deleting') {
    return {
      workspaceOverride: {
        status: 'deleting',
        allowedActions: availability.allowedActions,
        reasonCode: availability.reasonCode,
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }
  if (availability?.availability === 'deleting') {
    return {
      workspaceOverride: {
        status: 'deleting',
        allowedActions: availability.allowedActions,
        reasonCode: availability.reasonCode,
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }
  if (availability?.availability === 'not_found') {
    return {
      workspaceOverride: {
        status: 'not_found',
        allowedActions: availability.allowedActions,
        reasonCode: availability.reasonCode,
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }

  if (availability?.availability === 'transitioning') {
    return {
      execution: {
        status: 'transitioning',
        allowedActions: availability.allowedActions,
        reasonCode: availability.reasonCode,
      },
    };
  }
  if (availability?.availability === 'stopped') {
    return {
      execution: {
        status: 'stopped',
        allowedActions: availability.allowedActions,
        reasonCode: availability.reasonCode,
      },
    };
  }
  if (availability?.availability === 'blocked') {
    const allowedActions = availability.reasonCode === WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE
      ? []
      : availability.allowedActions;
    return {
      execution: {
        status: 'blocked',
        allowedActions,
        reasonCode: view.actionErrorCode ?? availability.reasonCode,
      },
    };
  }

  if (view.loadError instanceof ApiError && view.loadError.status === 404) {
    return {
      workspaceOverride: {
        status: 'not_found',
        allowedActions: ['return'],
        reasonCode: getLoadErrorReasonCode(view.loadError),
      },
      execution: {
        status: 'checking',
        allowedActions: [],
      },
    };
  }

  return {
    execution: {
      status: 'uncertain',
      allowedActions: [],
      reasonCode: view.actionErrorCode
        ?? (availability?.reasonCode ?? getLoadErrorReasonCode(view.loadError ?? null)),
    },
  };
};

export const useWorkspaceEntryController = (
  workspaceId: string,
): WorkspaceEntryController => {
  const navigate = useNavigate();
  const { t } = useI18n();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const workspaceRuntime = useWorkspaceRuntime(workspaceId);
  const permissions = resolveWorkspacePermissions(
    workspaceRuntime.accessRole,
    workspaceRuntime.allowedOperations,
  );
  const controller = useWorkspaceAvailabilityController({
    workspaceId,
    authorizationResolved: workspaceRuntime.isAuthorizationResolved,
    canRead: permissions.canRead,
    canRunLifecycle: permissions.canRead && permissions.canRunLifecycle,
  });

  const availability = controller.view.kind === 'unavailable'
    ? controller.view.availability
    : null;
  const isNotFound = availability?.availability === 'not_found'
    || (controller.view.kind === 'unavailable'
      && controller.view.loadError instanceof ApiError
      && controller.view.loadError.status === 404);
  const isDeletionInProgress = availability?.deletion?.availability === 'deleting'
    || (!availability?.deletion && availability?.availability === 'deleting');
  const deletionActions = availability?.deletion?.allowedActions;
  const isExecutionPlaneDrift = availability?.reasonCode
    === WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE;
  const canIssueDeletion = permissions.canDelete
    && !isNotFound
    && (!deletionActions
      || deletionActions.includes('delete')
      || deletionActions.includes('retry'));
  const deletion = useWorkspaceDeletion({
    workspaceId,
    workspaceName: workspaceRuntime.workspaceName,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    canDelete: canIssueDeletion,
    shouldDiscoverExistingJob: controller.view.kind === 'unavailable'
      && !isNotFound
      && (!isExecutionPlaneDrift || canIssueDeletion),
    isDeletionInProgress,
  });

  const workspaceSource = getWorkspaceStatus(
    workspaceRuntime.isAuthorizationResolved,
    permissions.canRead,
    workspaceRuntime.errorCode,
  );
  const availabilitySource = getAvailabilitySource(controller.view);
  const projection = projectWorkspaceEntry({
    identity: isAuthLoading
      ? { status: 'checking' }
      : isAuthenticated
        ? { status: 'authenticated' }
        : { status: 'unauthenticated' },
    workspace: availabilitySource.workspaceOverride ?? workspaceSource,
    execution: availabilitySource.execution,
  });

  const onAction = useCallback((action: WorkspaceEntryActionId) => {
    if (action === 'refresh') {
      controller.refresh();
      return;
    }
    if (action === 'return') {
      controller.returnToWorkspaceList();
      return;
    }
    if (action === 'create') {
      navigate(ROUTES.workspace.wizard);
      return;
    }
    if (action === 'login') {
      navigate(ROUTES.login, { replace: true });
      return;
    }
    if (action === 'rebuild' && !window.confirm(t('common.entry.confirmRebuild'))) {
      return;
    }
    if (action === 'start' || action === 'retry' || action === 'rebuild') {
      controller.runAction(action);
    }
  }, [controller, navigate, t]);

  return {
    workspaceRuntime,
    projection,
    isPending: controller.view.kind !== 'execution',
    onAction,
    deletion: {
      ...deletion,
      canShowEntry: controller.view.kind === 'unavailable'
        && !isNotFound
        && (!isDeletionInProgress || deletion.progress?.status === 'failed')
        && canIssueDeletion
        && Boolean(workspaceRuntime.workspaceName),
      isDeletionInProgress,
    },
  };
};
