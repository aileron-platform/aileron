import {
  OPERATION_IDS,
  hasAllowedOperation,
  normalizeAllowedOperations,
  type OperationId,
} from '@/shared/authorization/operationIds';
import {
  normalizeResourceAccessRole,
  type ResourceAccessRole,
} from '@/shared/authorization/resourceAccessRole';

export interface KnowledgeBasePermissions {
  accessRole: ResourceAccessRole | null;
  allowedOperations: OperationId[];
  canRead: boolean;
  canWrite: boolean;
  canManageSettings: boolean;
  canManageShares: boolean;
  canManageVisibility: boolean;
  canManage: boolean;
  canDelete: boolean;
}

export const resolveKnowledgeBasePermissions = (
  accessRole: unknown,
  allowedOperations: unknown,
): KnowledgeBasePermissions => {
  const normalizedRole = normalizeResourceAccessRole(accessRole);
  const normalizedOperations = normalizeAllowedOperations(allowedOperations);
  const hasOperation = (operationId: OperationId): boolean => (
    normalizedRole !== null
    && hasAllowedOperation(normalizedOperations, operationId)
  );
  const canManageSettings = hasOperation(
    OPERATION_IDS.knowledgeBaseSettingsManage,
  );
  const canManageShares = hasOperation(OPERATION_IDS.knowledgeBaseShareManage);

  return {
    accessRole: normalizedRole,
    allowedOperations: normalizedOperations,
    canRead: hasOperation(OPERATION_IDS.knowledgeBaseDetailRead),
    canWrite: hasOperation(OPERATION_IDS.knowledgeBaseContentWrite),
    canManageSettings,
    canManageShares,
    canManageVisibility: hasOperation(OPERATION_IDS.knowledgeBaseVisibilityManage),
    canManage: canManageSettings && canManageShares,
    canDelete: hasOperation(OPERATION_IDS.knowledgeBaseDelete),
  };
};
