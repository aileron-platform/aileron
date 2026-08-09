export const RESOURCE_ACCESS_ROLES = [
  'reader',
  'manager',
  'owner',
] as const;

export type ResourceAccessRole = typeof RESOURCE_ACCESS_ROLES[number];

export const normalizeResourceAccessRole = (
  value: unknown,
): ResourceAccessRole | null => (
  typeof value === 'string'
  && RESOURCE_ACCESS_ROLES.includes(value as ResourceAccessRole)
    ? value as ResourceAccessRole
    : null
);
