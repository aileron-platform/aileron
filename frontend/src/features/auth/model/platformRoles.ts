export const PLATFORM_ROLES = [
  'admin',
  'member',
] as const;

export type PlatformRole = typeof PLATFORM_ROLES[number];

export const normalizePlatformRole = (value: unknown): PlatformRole | null => (
  typeof value === 'string'
  && PLATFORM_ROLES.includes(value as PlatformRole)
    ? value as PlatformRole
    : null
);
