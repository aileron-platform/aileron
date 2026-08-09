/**
 *
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import { GitContextSelector } from './GitContextSelector';
import { RepositoryNotInitializedEmptyState } from './RepositoryNotInitializedEmptyState';
import {
  type VersionControlCommitSummary,
  type VersionControlFileChange,
} from '@/shared/version-control';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { isVersionControlNotInitializedError } from '../model/versionControlModel';
import { useI18n } from '@/shared/hooks/useI18n';
import { VersionControlHistorySidebar, VersionControlRevertCommitDialog } from '@/shared/components/version-control';

interface CommitHistoryPanelProps {
  selectedCommitId?: string;
  onCommitSelect?: (commit: VersionControlCommitSummary | null) => void;
  onFileSelect?: (file: VersionControlFileChange | null) => void;
}

/**
 */
export const CommitHistoryPanel: React.FC<CommitHistoryPanelProps> = ({
  selectedCommitId: externalSelectedCommitId,
  onCommitSelect,
  onFileSelect,
}) => {
  const [internalSelectedCommitId, setInternalSelectedCommitId] = useState(externalSelectedCommitId || '');
  const [selectedFile, setSelectedFile] = useState<VersionControlFileChange | null>(null);
  const [searchText, setSearchText] = useState('');
  const [branchFilter, setBranchFilter] = useState<string | null>(null);
  const [revertCommit, setRevertCommit] = useState<VersionControlCommitSummary | null>(null);

  const { t } = useI18n();
  const { workspaceRuntime, state, permissions } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const selectedGitContextId = state.versionControl.selectedGitContextId;
  const vc = useWorkspaceVersionControlSession({
    workspaceId,
    runtimeBaseUrl,
    contextId: selectedGitContextId,
  });

  const branchesQuery = vc.history.useBranchesQuery({
    includeRemote: true,
    includeMetadata: false,
  });
  const statusQuery = vc.changes.useStatusQuery();

  // React Query Infinite Query
  const commitsQuery = vc.history.useCommitsInfiniteQuery({
    limit: 20,
    branch: branchFilter ?? undefined,
    search: searchText.trim() || undefined,
  });

  // Commit Files Query
  const filesQuery = vc.history.useCommitFilesQuery(internalSelectedCommitId);
  const revertCommitMutation = vc.history.useRevertCommitMutation();

  const allCommits = useMemo(() => {
    return commitsQuery.data?.pages.flatMap(page => page.items ?? []) ?? [];
  }, [commitsQuery.data]);

  const branchFilterOptions = useMemo(() => {
    const branches = branchesQuery.data ?? [];
    const knownBranchNames = new Set(branches.map((branch) => branch.name));
    const currentBranch = statusQuery.data?.currentBranch;

    if (currentBranch && !knownBranchNames.has(currentBranch)) {
      return [
        { name: currentBranch, displayName: currentBranch, kind: 'local', isCurrent: true },
        ...branches,
      ];
    }

    return branches;
  }, [branchesQuery.data, statusQuery.data?.currentBranch]);

  React.useEffect(() => {
    if (externalSelectedCommitId) {
      setInternalSelectedCommitId(externalSelectedCommitId);
    }
  }, [externalSelectedCommitId]);

  React.useEffect(() => {
    setInternalSelectedCommitId('');
    setSelectedFile(null);
    onFileSelect?.(null);
  }, [branchFilter, onFileSelect, searchText]);

  React.useEffect(() => {
    if (internalSelectedCommitId) {
      const commit = allCommits.find(c => c.id === internalSelectedCommitId) ?? null;
      onCommitSelect?.(commit);
    }
  }, [internalSelectedCommitId, allCommits, onCommitSelect]);

  const handleCommitSelect = useCallback((commit: VersionControlCommitSummary) => {
    setInternalSelectedCommitId(commit.id);
    setSelectedFile(null);
    onFileSelect?.(null);
  }, [onFileSelect]);

  const handleFileSelect = useCallback((file: VersionControlFileChange | null) => {
    setSelectedFile(file);
    onFileSelect?.(file);
  }, [onFileSelect]);

  if (commitsQuery.isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (commitsQuery.error) {
    if (isVersionControlNotInitializedError(commitsQuery.error)) {
      return <RepositoryNotInitializedEmptyState />;
    }

    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-destructive">{commitsQuery.error.message}</div>
      </div>
    );
  }

  return (
    <>
    <VersionControlHistorySidebar
      contextSlot={<GitContextSelector />}
      commits={allCommits}
      files={filesQuery.data ?? []}
      selectedCommitId={internalSelectedCommitId}
      selectedFile={selectedFile}
      isFilesLoading={filesQuery.isLoading}
      filesError={filesQuery.error?.message ?? null}
      onCommitSelect={handleCommitSelect}
      onFileSelect={handleFileSelect}
      hasMore={commitsQuery.hasNextPage}
      isLoadingMore={commitsQuery.isFetchingNextPage}
      onLoadMore={() => void commitsQuery.fetchNextPage()}
      searchValue={searchText}
      onSearchChange={setSearchText}
      branchFilter={branchFilter}
      branches={branchFilterOptions}
      onBranchFilterChange={setBranchFilter}
      mutationDisabled={!permissions.canWrite || revertCommitMutation.isPending}
      onRevertCommit={setRevertCommit}
    />
    <VersionControlRevertCommitDialog
      open={revertCommit !== null}
      commit={revertCommit}
      onOpenChange={(open) => { if (!open) setRevertCommit(null); }}
      onConfirm={(sha) => revertCommitMutation.mutateAsync(sha)}
    />
    </>
  );
};
