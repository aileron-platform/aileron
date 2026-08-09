const supportedScopes = new Set(['platform', 'workspace', 'knowledge_base']);
const runtimeActions = new Set([
  'runtime_read',
  'runtime_write',
  'workspace_settings',
  'terminal',
  'agent',
  'automation',
  'browser_automation',
]);
const expectedPlatformRoles = ['admin', 'member'];
const expectedResourceRoles = ['reader', 'manager', 'owner'];
const expectedAccessSources = [
  'owned',
  'direct_share',
  'group_share',
  'public',
  'platform_admin',
];

function assertUniqueStrings(values, fieldName) {
  if (
    !Array.isArray(values)
    || values.some((value) => typeof value !== 'string' || value.length === 0)
    || new Set(values).size !== values.length
  ) {
    throw new Error(`${fieldName} must contain unique non-empty strings.`);
  }
}

export function assertAuthorizationContracts({
  wireContract,
  operationContract,
  runtimeRouteContract,
}) {
  if (
    wireContract.schemaVersion !== 2
    || operationContract.schemaVersion !== 2
    || runtimeRouteContract.schemaVersion !== 1
  ) {
    throw new Error('Unsupported authorization contract schema.');
  }

  const wireContractFields = [
    'schemaVersion',
    'platformRoles',
    'resourceAccessRoles',
    'resourceAccessSources',
    'operationIds',
    'errorCodes',
  ];
  if (
    Object.keys(wireContract).length !== wireContractFields.length
    || wireContractFields.some((fieldName) => !(fieldName in wireContract))
  ) {
    throw new Error('Authorization wire contract must use the fixed schema.');
  }

  for (const fieldName of wireContractFields.slice(1)) {
    assertUniqueStrings(wireContract[fieldName], fieldName);
  }

  if (
    wireContract.platformRoles.join('\0') !== expectedPlatformRoles.join('\0')
  ) {
    throw new Error('platformRoles must be exactly admin and member.');
  }
  if (
    wireContract.resourceAccessRoles.join('\0')
      !== expectedResourceRoles.join('\0')
  ) {
    throw new Error(
      'resourceAccessRoles must be exactly reader, manager, and owner.',
    );
  }
  if (
    wireContract.resourceAccessSources.join('\0')
      !== expectedAccessSources.join('\0')
  ) {
    throw new Error(
      'resourceAccessSources must be exactly owned, direct_share, group_share, public, and platform_admin.',
    );
  }

  const operationIds = new Set(wireContract.operationIds);
  const resourceRoles = new Set(wireContract.resourceAccessRoles);
  const seenRequirements = new Set();

  for (const requirement of operationContract.requirements) {
    const requirementFields = [
      'operationId',
      'scope',
      'minimumResourceRole',
      'platformAdminOnly',
    ];
    if (
      Object.keys(requirement).length !== requirementFields.length
      || requirementFields.some((fieldName) => !(fieldName in requirement))
      || !operationIds.has(requirement.operationId)
      || !supportedScopes.has(requirement.scope)
      || typeof requirement.platformAdminOnly !== 'boolean'
      || seenRequirements.has(requirement.operationId)
    ) {
      throw new Error(
        `Operation requirement ${requirement.operationId ?? '<missing>'} must use the fixed schema without capability.`,
      );
    }
    if (
      requirement.scope === 'platform'
        ? requirement.minimumResourceRole !== null
        : !resourceRoles.has(requirement.minimumResourceRole)
    ) {
      throw new Error(
        `Invalid minimum resource role for ${requirement.operationId}.`,
      );
    }
    seenRequirements.add(requirement.operationId);
  }

  if (
    seenRequirements.size !== operationIds.size
    || [...operationIds].some((operationId) => !seenRequirements.has(operationId))
  ) {
    throw new Error('Operation requirements do not cover every OperationId.');
  }

  const routeKeys = new Set();
  for (const route of runtimeRouteContract.routes) {
    assertUniqueStrings(route.methods, `${route.routeTemplate}.methods`);
    if (
      typeof route.routeTemplate !== 'string'
      || route.routeTemplate.length === 0
      || !runtimeActions.has(route.action)
      || !Number.isInteger(route.matchPriority)
      || typeof route.sensitive !== 'boolean'
    ) {
      throw new Error(`Invalid Runtime route ${route.routeTemplate ?? '<missing>'}.`);
    }

    for (const method of route.methods) {
      const routeKey = `${method}:${route.routeTemplate}`;
      if (routeKeys.has(routeKey)) {
        throw new Error(`Duplicate Runtime route ${routeKey}.`);
      }
      routeKeys.add(routeKey);
    }
  }
}
