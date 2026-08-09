import {
  OPERATION_IDS,
  hasAllowedOperation,
  type OperationId,
} from '@/shared/authorization/operationIds';

export interface PlatformResourcePermissions {
  canRead: boolean;
  canReassignOwner: boolean;
  canManageKnowledgeBaseQuota: boolean;
  canExpandWorkspaceCapacity: boolean;
}

export const resolvePlatformResourcePermissions = (
  allowedOperations: readonly OperationId[],
): PlatformResourcePermissions => ({
  canRead: hasAllowedOperation(
    allowedOperations,
    OPERATION_IDS.platformResourcesRead,
  ),
  canReassignOwner: hasAllowedOperation(
    allowedOperations,
    OPERATION_IDS.platformResourcesOwnerReassign,
  ),
  canManageKnowledgeBaseQuota: hasAllowedOperation(
    allowedOperations,
    OPERATION_IDS.platformResourcesKnowledgeBaseQuotaUpdate,
  ),
  canExpandWorkspaceCapacity: hasAllowedOperation(
    allowedOperations,
    OPERATION_IDS.platformResourcesWorkspaceCapacityExpand,
  ),
});
