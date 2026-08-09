import type React from 'react';
import { AuthorizationDeniedState } from '@/features/auth/public';
import type { WorkspaceOperationId } from '../model/workspacePermissions';
import { useWorkspace } from '../providers/WorkspaceProvider';
import { WorkspaceFeatureLoading } from './WorkspaceFeatureLoading';

interface RequireWorkspaceOperationProps {
  operation: WorkspaceOperationId;
  children: React.ReactElement;
}

export const RequireWorkspaceOperation: React.FC<
  RequireWorkspaceOperationProps
> = ({ operation, children }) => {
  const { permissions, workspaceRuntime } = useWorkspace();

  if (workspaceRuntime.isLoading) {
    return <WorkspaceFeatureLoading labelKey="workspace.layout.loading.workspace" />;
  }

  if (!permissions.hasOperation(operation)) {
    return <AuthorizationDeniedState />;
  }

  return children;
};
