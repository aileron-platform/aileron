/**
 * WorkspaceShell owns runtime gates and shared shell-layout state.
 */

import React, { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { WorkspaceShellAdapter, type WorkspaceShellAdapterProps } from './WorkspaceShellAdapter';
import { WorkspaceRuntimeErrorPage } from './WorkspaceRuntimeErrorPage';

const logger = createLogger('WorkspaceShell');

type WorkspaceShellProps = WorkspaceShellAdapterProps;

export const WorkspaceShell: React.FC<WorkspaceShellProps> = (props) => {
  const { workspaceRuntime } = useWorkspace();
  const navigate = useNavigate();
  const workspaceId = workspaceRuntime.workspaceId;
  const handleRetryConnection = useCallback(async () => {
    await workspaceRuntime.reload();
  }, [workspaceRuntime]);

  const handleCreateWorkspace = useCallback(() => {
    navigate(ROUTES.workspace.wizard);
  }, [navigate]);

  const shouldShowRuntimeError =
    workspaceRuntime.error
    && !workspaceRuntime.isLoading
    && !workspaceRuntime.runtimeBaseUrl;

  if (shouldShowRuntimeError) {
    return (
      <WorkspaceShellAdapter
        {...props}
        stateContent={(
          <WorkspaceRuntimeErrorPage
            error={workspaceRuntime.error}
            isLoading={workspaceRuntime.isLoading}
            onRetry={handleRetryConnection}
            onCreateWorkspace={handleCreateWorkspace}
          />
        )}
      />
    );
  }

  logger.debug('Rendering with workspaceRuntime', {
    workspaceId: workspaceRuntime.workspaceId,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
  });

  return <WorkspaceShellAdapter key={workspaceId ?? 'no-workspace'} {...props} />;
};
