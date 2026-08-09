export const OPERATION_IDS = {
  marketplaceCatalogRead: 'marketplace.catalog.read',
  marketplaceInstallExecute: 'marketplace.install.execute',
  marketplaceUserCopyManage: 'marketplace.user_copy.manage',
  marketplaceContentPublish: 'marketplace.content.publish',
  marketplaceContentManage: 'marketplace.content.manage',
  marketplaceDeleteExecute: 'marketplace.delete.execute',
  marketplaceRegistryManage: 'marketplace.registry.manage',
  workspaceCollectionRead: 'workspace.collection.read',
  workspaceCreate: 'workspace.create',
  knowledgeBaseCollectionRead: 'knowledge_base.collection.read',
  knowledgeBaseCreate: 'knowledge_base.create',
  userManagementManage: 'user_management.manage',
  platformResourcesRead: 'platform_resources.read',
  platformResourcesOwnerReassign: 'platform_resources.owner.reassign',
  platformResourcesKnowledgeBaseQuotaUpdate: 'platform_resources.knowledge_base.quota.update',
  platformResourcesWorkspaceCapacityExpand: 'platform_resources.workspace.capacity.expand',
  workspaceDetailRead: 'workspace.detail.read',
  workspaceContentWrite: 'workspace.content.write',
  workspaceLifecycleExecute: 'workspace.lifecycle.execute',
  workspaceMetadataWrite: 'workspace.metadata.write',
  workspaceAccessManage: 'workspace.access.manage',
  workspaceAttachmentWrite: 'workspace.attachment.write',
  workspaceFirewallRead: 'workspace.firewall.read',
  workspaceFirewallManage: 'workspace.firewall.manage',
  workspaceSensitiveSettingsRead: 'workspace.sensitive_settings.read',
  workspaceSensitiveSettingsManage: 'workspace.sensitive_settings.manage',
  workspaceTerminalUse: 'workspace.terminal.use',
  workspaceAgentChatUse: 'workspace.agent_chat.use',
  workspaceAutomationExecute: 'workspace.automation.execute',
  workspaceBrowserAutomationUse: 'workspace.browser_automation.use',
  workspaceDelete: 'workspace.delete',
  knowledgeBaseDetailRead: 'knowledge_base.detail.read',
  knowledgeBaseContentWrite: 'knowledge_base.content.write',
  knowledgeBaseSettingsManage: 'knowledge_base.settings.manage',
  knowledgeBaseShareManage: 'knowledge_base.share.manage',
  knowledgeBaseVisibilityManage: 'knowledge_base.visibility.manage',
  knowledgeBaseDelete: 'knowledge_base.delete',
} as const;

export type OperationId = typeof OPERATION_IDS[keyof typeof OPERATION_IDS];

const KNOWN_OPERATION_IDS = new Set<string>(Object.values(OPERATION_IDS));

export const isOperationId = (value: unknown): value is OperationId => (
  typeof value === 'string' && KNOWN_OPERATION_IDS.has(value)
);

export const normalizeAllowedOperations = (
  value: unknown,
): OperationId[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return [...new Set(value.filter(isOperationId))];
};

export const hasAllowedOperation = (
  allowedOperations: readonly OperationId[],
  operationId: OperationId,
): boolean => allowedOperations.includes(operationId);
