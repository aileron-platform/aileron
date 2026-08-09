import { describe, expect, it } from 'vitest';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import { resolveWorkspacePermissions } from './workspacePermissions';

describe('workspacePermissions', () => {
  it('uses backend allowed operations without rebuilding a capability-role matrix', () => {
    const permissions = resolveWorkspacePermissions('manager', [
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceAgentChatUse,
    ]);

    expect(permissions.canRead).toBe(true);
    expect(permissions.canUseChat).toBe(true);
    expect(permissions.canWrite).toBe(false);
  });

  it('keeps a read-only snapshot read-only even with an owner resource role', () => {
    const permissions = resolveWorkspacePermissions('owner', [
      OPERATION_IDS.workspaceDetailRead,
    ]);

    expect(permissions.canRead).toBe(true);
    expect(permissions.canWrite).toBe(false);
    expect(permissions.canManageSettings).toBe(false);
  });

  it('keeps firewall read, firewall mutation, and sensitive settings independent', () => {
    const readerPermissions = resolveWorkspacePermissions('reader', [
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceFirewallRead,
    ]);
    expect(readerPermissions.canReadFirewall).toBe(true);
    expect(readerPermissions.canManageFirewall).toBe(false);
    expect(readerPermissions.canUseSensitiveSettings).toBe(false);

    const permissions = resolveWorkspacePermissions('manager', [
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceFirewallRead,
      OPERATION_IDS.workspaceFirewallManage,
      OPERATION_IDS.workspaceSensitiveSettingsManage,
    ]);
    expect(permissions.canUseSensitiveSettings).toBe(true);
    expect(permissions.canReadFirewall).toBe(true);
    expect(permissions.canManageFirewall).toBe(true);
  });

  it.each([
    [undefined, [OPERATION_IDS.workspaceDetailRead]],
    ['admin', [OPERATION_IDS.workspaceDetailRead]],
    ['reader', undefined],
    ['reader', ['workspace.unknown']],
  ])('fails closed for malformed authorization data', (role, operations) => {
    expect(resolveWorkspacePermissions(role, operations).canRead).toBe(false);
  });
});
