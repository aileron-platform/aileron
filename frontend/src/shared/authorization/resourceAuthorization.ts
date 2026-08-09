import {
  normalizeAllowedOperations,
  type OperationId,
} from './operationIds';
import {
  normalizeResourceAccessRole,
  type ResourceAccessRole,
} from './resourceAccessRole';

export const RESOURCE_ACCESS_SOURCES = [
  'owned',
  'direct_share',
  'group_share',
  'public',
  'platform_admin',
] as const;

export type ResourceAccessSource = typeof RESOURCE_ACCESS_SOURCES[number];

export interface ResourceAuthorization {
  accessRole: ResourceAccessRole;
  accessSource: ResourceAccessSource;
  accessSources: ResourceAccessSource[];
  allowedOperations: OperationId[];
}

export const normalizeResourceAccessSource = (
  value: unknown,
): ResourceAccessSource | null => (
  typeof value === 'string'
  && RESOURCE_ACCESS_SOURCES.includes(value as ResourceAccessSource)
    ? value as ResourceAccessSource
    : null
);

const normalizeResourceAccessSources = (
  value: unknown,
): ResourceAccessSource[] | null => {
  if (!Array.isArray(value)) {
    return null;
  }
  const normalized = value.map(normalizeResourceAccessSource);
  if (normalized.some(source => source === null)) {
    return null;
  }
  return [...new Set(normalized as ResourceAccessSource[])];
};

export const normalizeResourceAuthorization = (
  value: {
    accessRole?: unknown;
    accessSource?: unknown;
    accessSources?: unknown;
    allowedOperations?: unknown;
  },
): ResourceAuthorization | null => {
  const accessRole = normalizeResourceAccessRole(value.accessRole);
  const accessSource = normalizeResourceAccessSource(value.accessSource);
  const accessSources = normalizeResourceAccessSources(value.accessSources);
  const allowedOperations = normalizeAllowedOperations(value.allowedOperations);

  if (
    !accessRole
    || !accessSource
    || !accessSources
    || !accessSources.includes(accessSource)
    || allowedOperations.length === 0
  ) {
    return null;
  }

  return {
    accessRole,
    accessSource,
    accessSources,
    allowedOperations,
  };
};
