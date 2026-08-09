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

export type WorkspaceOperationId =
  | typeof OPERATION_IDS.workspaceDetailRead
  | typeof OPERATION_IDS.workspaceContentWrite
  | typeof OPERATION_IDS.workspaceLifecycleExecute
  | typeof OPERATION_IDS.workspaceMetadataWrite
  | typeof OPERATION_IDS.workspaceAccessManage
  | typeof OPERATION_IDS.workspaceAttachmentWrite
  | typeof OPERATION_IDS.workspaceFirewallRead
  | typeof OPERATION_IDS.workspaceFirewallManage
  | typeof OPERATION_IDS.workspaceSensitiveSettingsManage
  | typeof OPERATION_IDS.workspaceDelete
  | typeof OPERATION_IDS.workspaceTerminalUse
  | typeof OPERATION_IDS.workspaceAgentChatUse
  | typeof OPERATION_IDS.workspaceAutomationExecute
  | typeof OPERATION_IDS.workspaceBrowserAutomationUse;

export interface WorkspacePermissions {
  accessRole: ResourceAccessRole | null;
  allowedOperations: OperationId[];
  canRead: boolean;
  canWrite: boolean;
  canRunLifecycle: boolean;
  canUpdateMetadata: boolean;
  canDelete: boolean;
  canManageSettings: boolean;
  canWriteAttachments: boolean;
  canReadFirewall: boolean;
  canManageFirewall: boolean;
  canUseChat: boolean;
  canUseTerminal: boolean;
  canUseBrowser: boolean;
  canUseSensitiveSettings: boolean;
  hasOperation: (operationId: WorkspaceOperationId) => boolean;
}

export const resolveWorkspacePermissions = (
  accessRole: unknown,
  allowedOperations: unknown,
): WorkspacePermissions => {
  const normalizedRole = normalizeResourceAccessRole(accessRole);
  const normalizedOperations = normalizeAllowedOperations(allowedOperations);
  const hasOperation = (operationId: WorkspaceOperationId): boolean => (
    normalizedRole !== null
    && hasAllowedOperation(normalizedOperations, operationId)
  );

  return {
    accessRole: normalizedRole,
    allowedOperations: normalizedOperations,
    canRead: hasOperation(OPERATION_IDS.workspaceDetailRead),
    canWrite: hasOperation(OPERATION_IDS.workspaceContentWrite),
    canRunLifecycle: hasOperation(OPERATION_IDS.workspaceLifecycleExecute),
    canUpdateMetadata: hasOperation(OPERATION_IDS.workspaceMetadataWrite),
    canDelete: hasOperation(OPERATION_IDS.workspaceDelete),
    canManageSettings: hasOperation(OPERATION_IDS.workspaceAccessManage),
    canWriteAttachments: hasOperation(OPERATION_IDS.workspaceAttachmentWrite),
    canReadFirewall: hasOperation(OPERATION_IDS.workspaceFirewallRead),
    canManageFirewall: hasOperation(OPERATION_IDS.workspaceFirewallManage),
    canUseChat: hasOperation(OPERATION_IDS.workspaceAgentChatUse),
    canUseTerminal: hasOperation(OPERATION_IDS.workspaceTerminalUse),
    canUseBrowser: hasOperation(OPERATION_IDS.workspaceBrowserAutomationUse),
    canUseSensitiveSettings: hasOperation(
      OPERATION_IDS.workspaceSensitiveSettingsManage,
    ),
    hasOperation,
  };
};
