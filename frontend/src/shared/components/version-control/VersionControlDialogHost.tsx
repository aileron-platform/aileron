import React from 'react';
import { VersionControlAbortConflictDialog } from './VersionControlAbortConflictDialog';
import {
  VersionControlDeleteBranchDialog,
  VersionControlPublishBranchDialog,
  VersionControlRenameBranchDialog,
} from './VersionControlBranchDialogs';
import { VersionControlCreateBranchDialog } from './VersionControlCreateBranchDialog';
import type { VersionControlCreateBranchPayload } from './VersionControlCreateBranchDialog';
import { VersionControlDiscardDialog } from './VersionControlDiscardDialog';
import { VersionControlRemoteSettingsDialog } from './VersionControlRemoteSettingsDialog';
import type { VersionControlRemoteSettingsState } from './VersionControlRemoteSettingsDialog';
import { VersionControlLfsDialog } from './VersionControlLfsDialog';
import type { VersionControlLfsDialogProps } from './VersionControlLfsDialog';
import { VersionControlRevertCommitDialog } from './VersionControlRevertCommitDialog';
import type { VersionControlWorkbenchController } from './useVersionControlWorkbenchController';

interface VersionControlDialogHostProps {
  controller: VersionControlWorkbenchController;
  activeBranch: string;
  repository?: VersionControlRemoteSettingsState | null;
  canManageRemote?: boolean;
  isCreatingBranch?: boolean;
  supportsBranchStartPoint?: boolean;
  isSavingRemoteUrl?: boolean;
  onSaveRemoteUrl?: (remoteUrl: string) => void | Promise<void>;
  onDiscard?: (paths: string[]) => void | Promise<void>;
  onAbortConflict?: () => void | Promise<void>;
  onRevertCommit?: (sha: string) => void | Promise<void>;
  onCreateBranch?: (payload: VersionControlCreateBranchPayload) => void | Promise<void>;
  onRenameBranch?: (newName: string) => void | Promise<void>;
  onDeleteBranch?: () => void | Promise<void>;
  onPublishBranch?: (remote: string, remoteName?: string) => void | Promise<void>;
  lfs?: Omit<VersionControlLfsDialogProps, 'open' | 'onOpenChange'>;
}

export const VersionControlDialogHost: React.FC<VersionControlDialogHostProps> = ({
  controller,
  activeBranch,
  repository,
  canManageRemote = false,
  isCreatingBranch = false,
  supportsBranchStartPoint = false,
  isSavingRemoteUrl = false,
  onSaveRemoteUrl,
  onDiscard,
  onAbortConflict,
  onRevertCommit,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  onPublishBranch,
  lfs,
}) => {
  const { dialogs } = controller;

  return (
    <>
      {canManageRemote && onSaveRemoteUrl ? (
        <VersionControlRemoteSettingsDialog
          open={dialogs.remoteSettingsOpen}
          onOpenChange={dialogs.setRemoteSettingsOpen}
          repository={repository ?? null}
          onSaveRemoteUrl={onSaveRemoteUrl}
          isSavingRemoteUrl={isSavingRemoteUrl}
        />
      ) : null}
      {lfs ? (
        <VersionControlLfsDialog
          {...lfs}
          open={dialogs.lfsSettingsOpen}
          onOpenChange={dialogs.setLfsSettingsOpen}
        />
      ) : null}
      {onDiscard ? (
        <VersionControlDiscardDialog
          open={dialogs.discardPaths.length > 0}
          paths={dialogs.discardPaths}
          onOpenChange={(open) => {
            if (!open) dialogs.setDiscardPaths([]);
          }}
          onConfirm={onDiscard}
        />
      ) : null}
      {onAbortConflict ? (
        <VersionControlAbortConflictDialog
          open={dialogs.abortConflictOpen}
          onOpenChange={dialogs.setAbortConflictOpen}
          onConfirm={onAbortConflict}
        />
      ) : null}
      {onRevertCommit ? (
        <VersionControlRevertCommitDialog
          open={dialogs.revertCommit !== null}
          commit={dialogs.revertCommit}
          onOpenChange={(open) => {
            if (!open) dialogs.setRevertCommit(null);
          }}
          onConfirm={onRevertCommit}
        />
      ) : null}
      {onCreateBranch ? (
        <VersionControlCreateBranchDialog
          open={dialogs.createBranchOpen || dialogs.trackingBranch !== null}
          onOpenChange={(open) => {
            dialogs.setCreateBranchOpen(open);
            if (!open) dialogs.setTrackingBranch(null);
          }}
          onCreate={onCreateBranch}
          isCreating={isCreatingBranch}
          supportsStartPoint={supportsBranchStartPoint}
          initialBranchName={dialogs.trackingBranch?.name.split('/').slice(1).join('/') ?? ''}
          initialStartPoint={dialogs.trackingBranch?.name ?? ''}
        />
      ) : null}
      {onRenameBranch ? (
        <VersionControlRenameBranchDialog
          open={dialogs.renameBranch !== null}
          branch={dialogs.renameBranch?.name ?? ''}
          onOpenChange={(open) => {
            if (!open) dialogs.setRenameBranch(null);
          }}
          onConfirm={onRenameBranch}
        />
      ) : null}
      {onDeleteBranch ? (
        <VersionControlDeleteBranchDialog
          open={dialogs.deleteBranch !== null}
          branch={dialogs.deleteBranch?.name ?? ''}
          onOpenChange={(open) => {
            if (!open) dialogs.setDeleteBranch(null);
          }}
          onConfirm={onDeleteBranch}
        />
      ) : null}
      {onPublishBranch ? (
        <VersionControlPublishBranchDialog
          open={dialogs.publishBranchOpen}
          branch={activeBranch}
          onOpenChange={dialogs.setPublishBranchOpen}
          onConfirm={onPublishBranch}
        />
      ) : null}
    </>
  );
};
