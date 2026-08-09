export {
  createKnowledgeBaseVersionControlSession,
  createMarketplaceVersionControlSession,
  useKnowledgeBaseVersionControlSession,
  useMarketplaceVersionControlSession,
  type KnowledgeBaseVersionControlSession,
  type MarketplaceVersionControlSession,
  type VersionControlCapabilityGroup,
} from './versionControlSession';
export {
  addPathsToSet,
  removePathsFromSet,
} from './versionControlOptimisticUpdates';
export {
  getConflictSource,
  getVersionControlErrorMessageKey,
  isHttpStatusError,
  isVersionControlOperationInProgressError,
} from './errors';
export {
  useRepositorySetupWorkflow,
  type RepositorySetupCapability,
  type RepositorySetupMutationKind,
  type RepositorySetupOperationResult,
  type RepositorySetupRemoteEffects,
  type RepositorySetupTarget,
} from './repositorySetupWorkflow';
export type {
  VersionControlActionCapability,
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitSummary,
  VersionControlConflictSource,
  VersionControlFileChange,
  VersionControlOperationStatus,
  VersionControlRemoteBranches,
  VersionControlRepositoryStatus,
  VersionControlStatus,
} from './types';
export {
  getLfsConversionProgress,
  isCompleteLfsSnapshotPreview,
  normalizeLfsPatterns,
  type VersionControlLfsPatterns,
  type VersionControlLfsPatternsUpdatePayload,
  type VersionControlLfsSnapshotConvertPayload,
  type VersionControlLfsSnapshotPreview,
} from './versionControlLfs';
