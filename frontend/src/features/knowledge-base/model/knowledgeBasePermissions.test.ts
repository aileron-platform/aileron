import { describe, expect, it } from 'vitest';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import { resolveKnowledgeBasePermissions } from './knowledgeBasePermissions';

describe('knowledgeBasePermissions', () => {
  it('uses backend allowed operations as the authority', () => {
    expect(resolveKnowledgeBasePermissions('owner', [
      OPERATION_IDS.knowledgeBaseDetailRead,
    ])).toMatchObject({
      canRead: true,
      canWrite: false,
      canManage: false,
      canDelete: false,
    });
  });

  it('distinguishes content, settings, sharing, visibility, and delete operations', () => {
    expect(resolveKnowledgeBasePermissions('owner', [
      OPERATION_IDS.knowledgeBaseDetailRead,
      OPERATION_IDS.knowledgeBaseContentWrite,
      OPERATION_IDS.knowledgeBaseSettingsManage,
      OPERATION_IDS.knowledgeBaseShareManage,
      OPERATION_IDS.knowledgeBaseVisibilityManage,
      OPERATION_IDS.knowledgeBaseDelete,
    ])).toMatchObject({
      canRead: true,
      canWrite: true,
      canManageSettings: true,
      canManageShares: true,
      canManageVisibility: true,
      canManage: true,
      canDelete: true,
    });
  });

  it.each([
    [undefined, [OPERATION_IDS.knowledgeBaseDetailRead]],
    ['admin', [OPERATION_IDS.knowledgeBaseDetailRead]],
    ['reader', undefined],
    ['reader', ['knowledge_base.unknown']],
  ])('fails closed for malformed authorization data', (role, operations) => {
    expect(resolveKnowledgeBasePermissions(role, operations).canRead).toBe(false);
  });
});
