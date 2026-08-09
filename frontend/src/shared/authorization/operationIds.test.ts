import { describe, expect, it } from 'vitest';
import {
  OPERATION_IDS,
  normalizeAllowedOperations,
} from './operationIds';

describe('normalizeAllowedOperations', () => {
  it('keeps known operations in response order and removes duplicates', () => {
    expect(normalizeAllowedOperations([
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceContentWrite,
      OPERATION_IDS.workspaceDetailRead,
    ])).toEqual([
      OPERATION_IDS.workspaceDetailRead,
      OPERATION_IDS.workspaceContentWrite,
    ]);
  });

  it.each([
    undefined,
    null,
    {},
    'workspace.detail.read',
    ['workspace.unknown', 1, null],
  ])('fails closed for malformed or unknown values', (value) => {
    expect(normalizeAllowedOperations(value)).toEqual([]);
  });
});
