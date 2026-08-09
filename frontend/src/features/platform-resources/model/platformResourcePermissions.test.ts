import { describe, expect, it } from 'vitest';
import { resolvePlatformResourcePermissions } from './platformResourcePermissions';

describe('resolvePlatformResourcePermissions', () => {
  it('fails every Platform Resources operation closed by default', () => {
    expect(resolvePlatformResourcePermissions([])).toEqual({
      canRead: false,
      canReassignOwner: false,
      canManageKnowledgeBaseQuota: false,
      canExpandWorkspaceCapacity: false,
    });
  });

  it('does not infer mutation access from the read operation', () => {
    expect(resolvePlatformResourcePermissions([
      'platform_resources.read',
    ])).toEqual({
      canRead: true,
      canReassignOwner: false,
      canManageKnowledgeBaseQuota: false,
      canExpandWorkspaceCapacity: false,
    });
  });

  it('maps each mutation operation independently', () => {
    expect(resolvePlatformResourcePermissions([
      'platform_resources.owner.reassign',
      'platform_resources.knowledge_base.quota.update',
      'platform_resources.workspace.capacity.expand',
    ])).toEqual({
      canRead: false,
      canReassignOwner: true,
      canManageKnowledgeBaseQuota: true,
      canExpandWorkspaceCapacity: true,
    });
  });
});
