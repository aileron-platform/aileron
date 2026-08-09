import { describe, expect, it } from 'vitest';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import { resolveWorkspacePermissions } from '../model/workspacePermissions';
import { getNavigationItems } from './workspaceNavigationModel';

describe('workspaceNavigationModel', () => {
  it('builds the feature navigation from canonical workspace operation ids', () => {
    const permissions = resolveWorkspacePermissions('owner', [
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceContentWrite,
      OPERATION_IDS.workspaceLifecycleExecute,
      OPERATION_IDS.workspaceMetadataWrite,
      OPERATION_IDS.workspaceAccessManage,
      OPERATION_IDS.workspaceAttachmentWrite,
      OPERATION_IDS.workspaceFirewallRead,
      OPERATION_IDS.workspaceFirewallManage,
      OPERATION_IDS.workspaceSensitiveSettingsManage,
      OPERATION_IDS.workspaceDelete,
      OPERATION_IDS.workspaceTerminalUse,
      OPERATION_IDS.workspaceAgentChatUse,
      OPERATION_IDS.workspaceAutomationExecute,
      OPERATION_IDS.workspaceBrowserAutomationUse,
    ]);

    const navigationItems = getNavigationItems({
      agenticTools: ['claude-code'],
      hasWorkspaceOperation: permissions.hasOperation,
    });

    expect(navigationItems.map((item) => item.id)).toEqual([
      'ai-agent',
      'file-management',
      'version-control',
      'workspace-settings',
      'container-management',
      'workspace-automation',
      'canvas',
      'browser',
      'claude-code',
    ]);
    expect(
      navigationItems
        .find((item) => item.id === 'ai-agent')
        ?.subItems
        ?.map((item) => item.id),
    ).toEqual(['ai-chat-home', 'terminal']);
  });

  it('shows Firewall without exposing Runtime Settings to a firewall reader', () => {
    const permissions = resolveWorkspacePermissions('reader', [
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceFirewallRead,
    ]);

    const navigationItems = getNavigationItems({
      agenticTools: [],
      hasWorkspaceOperation: permissions.hasOperation,
    });
    const containerManagement = navigationItems.find(
      (item) => item.id === 'container-management',
    );

    expect(containerManagement?.subItems?.map((item) => item.id)).toEqual([
      'firewall',
    ]);
  });
});
