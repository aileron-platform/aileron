import React from 'react';
import { EntryFrame } from '@/shared/components/entry/EntryFrame';
import { WorkspaceDeletionAction } from '../components/WorkspaceDeletionProgress';
import { WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE } from '../api/workspaceLifecycleApi';
import { WorkspaceProvider } from '../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspaceEntryController } from './useWorkspaceEntryController';

export interface WorkspaceEntryGateProps {
  workspaceId: string;
  navigationSlot: React.ReactNode;
  children: React.ReactNode;
}

const WorkspaceEntryGateController: React.FC<WorkspaceEntryGateProps> = ({
  workspaceId,
  navigationSlot,
  children,
}) => {
  const { t } = useI18n();
  const {
    workspaceRuntime,
    projection,
    isPending,
    onAction,
    deletion,
  } = useWorkspaceEntryController(workspaceId);

  const showDeletionAction = deletion.canShowEntry
    || deletion.isDeletionInProgress
    || Boolean(deletion.progress);
  const showExecutionPlaneDriftContact = projection.reasonCode
    === WORKSPACE_EXECUTION_PLANE_DRIFT_REASON_CODE
    && !showDeletionAction;

  return (
    <EntryFrame
      isPending={isPending}
      transitionKey={`workspace-${workspaceId}`}
      projection={projection}
      navigationSlot={navigationSlot}
      onAction={onAction}
      disableMutationActions={deletion.isDeletionInProgress || deletion.isDeleting}
      auxiliaryActions={showDeletionAction
        ? (
          <WorkspaceDeletionAction
            workspaceName={workspaceRuntime.workspaceName}
            canDelete={deletion.canShowEntry}
            isDeleting={deletion.isDeleting}
            progress={deletion.progress}
            requestDelete={deletion.requestDelete}
          />
        )
        : showExecutionPlaneDriftContact
          ? (
            <p className="text-sm text-muted-foreground">
              {t('common.entry.executionPlaneDrift.contactOwner')}
            </p>
          )
          : undefined}
    >
      <WorkspaceProvider
        workspaceId={workspaceId}
        runtimeSnapshot={workspaceRuntime}
      >
        {children}
      </WorkspaceProvider>
    </EntryFrame>
  );
};

export const WorkspaceEntryGate: React.FC<WorkspaceEntryGateProps> = props => (
  <WorkspaceEntryGateController key={props.workspaceId} {...props} />
);
