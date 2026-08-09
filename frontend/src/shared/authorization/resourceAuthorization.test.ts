import { describe, expect, it } from 'vitest';
import { OPERATION_IDS } from './operationIds';
import { normalizeResourceAuthorization } from './resourceAuthorization';

describe('normalizeResourceAuthorization', () => {
  it('normalizes the authoritative role, primary source, all sources, and operations', () => {
    expect(normalizeResourceAuthorization({
      accessRole: 'manager',
      accessSource: 'direct_share',
      accessSources: ['group_share', 'direct_share', 'group_share'],
      allowedOperations: [
        OPERATION_IDS.workspaceDetailRead,
        OPERATION_IDS.workspaceContentWrite,
      ],
    })).toEqual({
      accessRole: 'manager',
      accessSource: 'direct_share',
      accessSources: ['group_share', 'direct_share'],
      allowedOperations: [
        OPERATION_IDS.workspaceDetailRead,
        OPERATION_IDS.workspaceContentWrite,
      ],
    });
  });

  it.each([
    { accessRole: 'invalid', accessSource: 'direct_share', accessSources: ['direct_share'] },
    { accessRole: 'reader', accessSource: 'shared', accessSources: ['shared'] },
    { accessRole: 'reader', accessSource: 'public', accessSources: [] },
    { accessRole: 'reader', accessSource: 'public', accessSources: ['unknown'] },
  ])('fails closed for malformed resource authorization', (authorization) => {
    expect(normalizeResourceAuthorization({
      ...authorization,
      allowedOperations: [OPERATION_IDS.knowledgeBaseDetailRead],
    })).toBeNull();
  });
});
