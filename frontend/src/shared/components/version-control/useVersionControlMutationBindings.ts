import type { createKnowledgeBaseChangesCapability } from '@/shared/version-control/versionControlChangesCapability';
import type { createKnowledgeBaseHistoryCapability } from '@/shared/version-control/versionControlHistoryCapability';

type ChangesCapability = ReturnType<typeof createKnowledgeBaseChangesCapability>;
type HistoryCapability = Pick<
  ReturnType<typeof createKnowledgeBaseHistoryCapability>,
  | 'useCreateBranchMutation'
  | 'useSwitchBranchMutation'
  | 'useRenameBranchMutation'
  | 'useDeleteBranchMutation'
  | 'usePublishBranchMutation'
>;

export const useVersionControlChangeMutationBindings = (
  changes: ChangesCapability,
) => ({
  stageMutation: changes.useStageMutation(),
  unstageMutation: changes.useUnstageMutation(),
  commitMutation: changes.useCommitMutation(),
  discardMutation: changes.useDiscardMutation(),
  markResolvedMutation: changes.useMarkResolvedMutation(),
  abortConflictMutation: changes.useAbortConflictMutation(),
  forceUnlockMutation: changes.useForceUnlockMutation(),
});

export const useVersionControlBranchMutationBindings = (
  history: HistoryCapability,
) => ({
  createBranchMutation: history.useCreateBranchMutation(),
  switchBranchMutation: history.useSwitchBranchMutation(),
  renameBranchMutation: history.useRenameBranchMutation(),
  deleteBranchMutation: history.useDeleteBranchMutation(),
  publishBranchMutation: history.usePublishBranchMutation(),
});
