import type {
  MarketplaceDeliveryMethod,
  MarketplaceTargetClient,
  MarketplaceResourceType,
  MarketplaceUserCopyBlockingIssue,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';

export const MARKETPLACE_DELIVERY_METHODS: MarketplaceDeliveryMethod[] = [
  'plugin',
  'user-copy',
];

export const marketplaceResourceTypeCounts = (
  preflight: MarketplaceUserCopyPreflightResult | null,
): Array<[MarketplaceResourceType, number]> => {
  const counts = new Map<MarketplaceResourceType, number>();
  for (const resource of preflight?.resources ?? []) {
    counts.set(resource.resourceType, (counts.get(resource.resourceType) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right));
};

export interface MarketplaceBlockingIssueGroup {
  errorCode: MarketplaceUserCopyBlockingIssue['errorCode'];
  count: number;
}

export const marketplaceBlockingIssueGroups = (
  preflight: MarketplaceUserCopyPreflightResult | null,
): MarketplaceBlockingIssueGroup[] => {
  const groups = new Map<
    MarketplaceUserCopyBlockingIssue['errorCode'],
    MarketplaceBlockingIssueGroup
  >();
  for (const issue of preflight?.blockingIssues ?? []) {
    const current = groups.get(issue.errorCode);
    groups.set(issue.errorCode, {
      errorCode: issue.errorCode,
      count: (current?.count ?? 0) + 1,
    });
  }
  return Array.from(groups.values());
};

export const getMarketplaceInstallResourceTypeLabelKey = (
  targetClient: MarketplaceTargetClient,
  resourceType: MarketplaceResourceType,
): string => (
  targetClient === 'codex' && resourceType === 'prompt'
    ? 'marketplace.install.resourceTypes.slashCommand'
    : `marketplace.install.resourceTypes.${resourceType}`
);

const MARKETPLACE_SKIPPED_REASON_KEYS: Record<string, string> = {
  'format-unsupported': 'marketplace.install.skipped.reasons.formatUnsupported',
  'source-not-allowed': 'marketplace.install.skipped.reasons.sourceNotAllowed',
};

export const getMarketplaceSkippedReasonKey = (code: string): string => (
  MARKETPLACE_SKIPPED_REASON_KEYS[code]
  ?? 'marketplace.install.skipped.reasons.unsupported'
);

const MARKETPLACE_INSTALL_ERROR_KEYS: Record<string, string> = {
  'marketplace.install.target_client_invalid': 'marketplace.install.errors.targetClientInvalid',
  'marketplace.install.target_client_not_enabled': 'marketplace.install.errors.targetClientNotEnabled',
  'marketplace.install.runtime_contract_invalid': 'marketplace.install.errors.runtimeContractInvalid',
  'marketplace.install.runtime_delegation_unavailable': 'marketplace.install.errors.runtimeDelegationUnavailable',
  'marketplace.install.runtime_url_missing': 'marketplace.install.errors.runtimeUrlMissing',
  'marketplace.install.branch_mismatch': 'marketplace.install.errors.branchMismatch',
  'marketplace.install.remote_url_credentials_forbidden': 'marketplace.install.errors.remoteUrlCredentialsForbidden',
  'marketplace.install.remote_url_invalid': 'marketplace.install.errors.remoteUrlInvalid',
  'marketplace.install.workspace_not_found': 'marketplace.install.errors.workspaceNotFound',
  'marketplace.install.workspace_not_running': 'marketplace.install.errors.workspaceNotRunning',
  'marketplace.user_copy.package_not_found':
    'marketplace.install.errors.packageNotFound',
  'marketplace.user_copy.revision_conflict':
    'marketplace.install.errors.packageRevisionConflict',
  'marketplace.user_copy.runtime_unavailable':
    'marketplace.install.errors.runtimeUnavailable',
  'marketplace.user_copy.runtime_contract_invalid':
    'marketplace.install.errors.runtimeContractInvalid',
  'marketplace.user_copy.source_invalid':
    'marketplace.install.errors.userCopySourceInvalid',
  'marketplace.user_copy.plan_stale':
    'marketplace.install.errors.userCopyPlanStale',
  'marketplace.user_copy.confirmation_required':
    'marketplace.install.errors.userCopyConfirmationRequired',
  'marketplace.user_copy.apply_failed':
    'marketplace.install.errors.userCopyApplyFailed',
  'marketplace.user_copy.workspace_access_denied':
    'marketplace.install.errors.userCopyWorkspaceAccessDenied',
  'marketplace.user_copy.rollback_failed':
    'marketplace.install.errors.userCopyRollbackFailed',
  'marketplace.user_copy.inventory_unavailable':
    'marketplace.install.errors.userCopyInventoryUnavailable',
  'marketplace.user_copy.duplicate_target':
    'marketplace.install.errors.userCopyDuplicateTarget',
  'marketplace.user_copy.dependency_payload_unprojectable':
    'marketplace.install.errors.userCopyDependencyPayloadUnprojectable',
  'marketplace.user_copy.effective_identity_conflict':
    'marketplace.install.errors.userCopyEffectiveIdentityConflict',
  'marketplace.user_copy.profile_empty':
    'marketplace.install.errors.userCopyProfileEmpty',
  'marketplace.user_copy.target_not_writable':
    'marketplace.install.errors.userCopyTargetNotWritable',
  'marketplace.user_copy.target_unsafe':
    'marketplace.install.errors.userCopyTargetUnsafe',
  'marketplace.user_copy.target_document_invalid':
    'marketplace.install.errors.userCopyTargetDocumentInvalid',
  'marketplace.user_copy.profile_invalid':
    'marketplace.install.errors.userCopyProfileInvalid',
  'marketplace.user_copy.source_reference_invalid':
    'marketplace.install.errors.userCopySourceReferenceInvalid',
  'marketplace.user_copy.source_not_allowed':
    'marketplace.install.errors.userCopySourceNotAllowed',
  'marketplace.user_copy.unsupported_resource':
    'marketplace.install.errors.userCopyUnsupportedResource',
  'marketplace.git.operation_failed': 'marketplace.install.errors.gitOperationFailed',
  'marketplace.git.remote_required': 'marketplace.install.errors.remoteRequired',
  'marketplace.git.repository_not_initialized': 'marketplace.install.errors.repositoryNotInitialized',
  'marketplace.git.publish_branch_invalid': 'marketplace.install.errors.publishBranchInvalid',
  'marketplace.import.validation.ssh_key_required': 'marketplace.install.errors.sshKeyRequired',
  'marketplace.package.not_found': 'marketplace.install.errors.packageNotFound',
  'marketplace.install.package_revision_conflict_refreshed':
    'marketplace.install.errors.packageRevisionConflictRefreshed',
  'marketplace.install.runtime_unavailable': 'marketplace.install.errors.runtimeUnavailable',
  'marketplace.install.command_failed': 'marketplace.install.errors.commandFailed',
};

export const getMarketplaceInstallErrorKey = (
  errorCode: string | null | undefined,
) => (
  errorCode
    ? MARKETPLACE_INSTALL_ERROR_KEYS[errorCode] ?? 'marketplace.install.errors.unknown'
    : 'marketplace.install.errors.unknown'
);
