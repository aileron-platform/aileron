import React from 'react';
import {
  type VersionControlFileChange,
} from '@/shared/version-control';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { VersionControlDiffContent } from '@/shared/components/version-control';
import { useI18n } from '@/shared/hooks/useI18n';

interface DiffViewerProps {
  selectedFile?: VersionControlFileChange | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ selectedFile }) => {
  const { t } = useI18n();
  const { workspaceRuntime, state } = useWorkspace();
  const vc = useWorkspaceVersionControlSession({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
    contextId: state.versionControl.selectedGitContextId,
  });
  const inlineDiff = selectedFile?.diff ?? selectedFile?.patch ?? '';
  const diffQuery = vc.changes.useDiffQuery({
    path: selectedFile?.path ?? null,
    head: selectedFile?.changeType === 'staged' ? 'INDEX' : 'WORKTREE',
    enabled: !inlineDiff,
  });
  const diffContent = inlineDiff || diffQuery.data?.patch || diffQuery.data?.diff || '';
  const error = diffQuery.error instanceof Error
    ? diffQuery.error.message
    : (!workspaceRuntime.isLoading && workspaceRuntime.error)
      ? workspaceRuntime.error
      : diffQuery.error
        ? t('workspace.versionControl.diff.loadFailed')
        : null;

  return (
    <VersionControlDiffContent
      diffContent={diffContent}
      selectedPath={selectedFile?.path ?? null}
      isLoading={!inlineDiff && diffQuery.isLoading}
      error={error}
    />
  );
};
