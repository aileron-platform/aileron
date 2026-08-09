import { describe, expect, it } from 'vitest';
import { normalizeResourceAccessRole } from './resourceAccessRole';

describe('resourceAccessRole', () => {
  it.each(['reader', 'manager', 'owner'] as const)(
    'normalizes the known %s role',
    (role) => {
      expect(normalizeResourceAccessRole(role)).toBe(role);
    },
  );

  it.each([undefined, null, '', 'editor', 'viewer', 'admin', 'OWNER', 1, {}])(
    'fails closed for an unknown role value',
    (value) => {
      expect(normalizeResourceAccessRole(value)).toBeNull();
    },
  );
});
