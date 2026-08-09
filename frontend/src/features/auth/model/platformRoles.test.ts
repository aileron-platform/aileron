import { describe, expect, it } from 'vitest';
import { normalizePlatformRole } from './platformRoles';

describe('normalizePlatformRole', () => {
  it.each(['admin', 'member'] as const)(
    'accepts the known %s platform role',
    (role) => {
      expect(normalizePlatformRole(role)).toBe(role);
    },
  );

  it.each([
    undefined,
    null,
    '',
    'developer',
    'assistant_user',
    'read_only_user',
    'viewer',
    'reader',
    'ADMIN',
    1,
    {},
  ])(
    'fails closed for a retired or malformed role',
    (value) => {
      expect(normalizePlatformRole(value)).toBeNull();
    },
  );
});
