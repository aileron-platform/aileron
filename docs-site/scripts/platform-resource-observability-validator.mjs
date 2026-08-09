const expectedArrays = {
  resourceTypes: ['workspace', 'knowledge_base'],
  ranges: ['7d', '30d', '90d'],
  storageKinds: ['workspace_data', 'runtime_home', 'knowledge_base'],
  workspaceHealthGroups: ['running', 'transitioning', 'stopped', 'error'],
  knowledgeBaseVisibility: ['public', 'private'],
  knowledgeBaseIndexingGroups: ['success', 'processing', 'failure', 'never_indexed'],
  capacityRisks: ['normal', 'warning', 'critical', 'unknown', 'stale'],
  expansionPhases: ['pending', 'applying', 'completed', 'failed'],
};

function assertEqual(actual, expected, field) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Invalid platform resource observability ${field}.`);
  }
}

export function assertPlatformResourceContract(contract) {
  assertEqual(contract.schemaVersion, 1, 'schemaVersion');
  for (const [field, expected] of Object.entries(expectedArrays)) {
    assertEqual(contract[field], expected, field);
  }
  assertEqual(contract.thresholds, {
    warningPercent: 80,
    criticalPercent: 95,
    staleAfterSeconds: 7200,
  }, 'thresholds');
  assertEqual(contract.retention, {
    rawActivityDays: 90,
    dailyAggregates: 'permanent',
    capacitySnapshots: 'permanent',
  }, 'retention');
  if (!Array.isArray(contract.endpoints) || contract.endpoints.length < 2) {
    throw new Error('Invalid platform resource observability endpoints.');
  }
}

export function assertPlatformResourceDocumentation({
  contract,
  zhHantSource,
  englishSource,
  sidebarSource,
}) {
  const requiredIdentifiers = [
    ...contract.ranges,
    ...contract.storageKinds,
    ...contract.workspaceHealthGroups,
    ...contract.capacityRisks,
    ...contract.endpoints,
  ];
  for (const [locale, source] of [['zh-Hant', zhHantSource], ['en', englishSource]]) {
    const missing = requiredIdentifiers.filter(identifier => !source.includes(`\`${identifier}\``));
    if (missing.length > 0) {
      throw new Error(`${locale} platform resource chapter is missing: ${missing.join(', ')}.`);
    }
    if (source.includes('TODO_TRANSLATION')) {
      throw new Error(`${locale} platform resource chapter contains TODO_TRANSLATION.`);
    }
  }
  if (!sidebarSource.includes("'features/platform/resource-statistics-and-capacity'")) {
    throw new Error('Platform resource chapter is missing from sidebar.');
  }
}
