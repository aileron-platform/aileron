import type { createKnowledgeBaseChangesCapability } from '@/shared/version-control/versionControlChangesCapability';
import type { createKnowledgeBaseHistoryCapability } from '@/shared/version-control/versionControlHistoryCapability';

type ChangesCapability = Pick<
  ReturnType<typeof createKnowledgeBaseChangesCapability>,
  'useChangesQuery' | 'useStatusQuery' | 'useOperationStatusQuery'
>;
type HistoryCapability = Pick<
  ReturnType<typeof createKnowledgeBaseHistoryCapability>,
  'useBranchesQuery' | 'useCommitsQuery'
>;

interface VersionControlProductQueryOptions {
  commitsLimit: number;
  includeRemoteBranches?: boolean;
  includeBranchMetadata?: boolean;
}

export const useVersionControlStatusQueryBindings = (
  changes: Pick<ChangesCapability, 'useStatusQuery' | 'useOperationStatusQuery'>,
) => ({
  statusQuery: changes.useStatusQuery(),
  operationStatusQuery: changes.useOperationStatusQuery(),
});

export const useVersionControlProductQueryBindings = (
  changes: ChangesCapability,
  history: HistoryCapability,
  {
    commitsLimit,
    includeRemoteBranches,
    includeBranchMetadata,
  }: VersionControlProductQueryOptions,
) => {
  const changesQuery = changes.useChangesQuery();
  const { statusQuery, operationStatusQuery } = useVersionControlStatusQueryBindings(changes);
  const branchesQuery = history.useBranchesQuery({
    ...(includeRemoteBranches == null ? {} : { includeRemote: includeRemoteBranches }),
    ...(includeBranchMetadata == null ? {} : { includeMetadata: includeBranchMetadata }),
  });
  const commitsQuery = history.useCommitsQuery({ limit: commitsLimit, queryScope: 'current' });

  return {
    changesQuery,
    statusQuery,
    operationStatusQuery,
    branchesQuery,
    commitsQuery,
  };
};
