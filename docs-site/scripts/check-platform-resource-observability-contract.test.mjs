import assert from 'node:assert/strict';
import test from 'node:test';
import {
  assertPlatformResourceContract,
  assertPlatformResourceDocumentation,
} from './platform-resource-observability-validator.mjs';

const validContract = () => ({
  schemaVersion: 1,
  resourceTypes: ['workspace', 'knowledge_base'],
  ranges: ['7d', '30d', '90d'],
  storageKinds: ['workspace_data', 'runtime_home', 'knowledge_base'],
  workspaceHealthGroups: ['running', 'transitioning', 'stopped', 'error'],
  knowledgeBaseVisibility: ['public', 'private'],
  knowledgeBaseIndexingGroups: ['success', 'processing', 'failure', 'never_indexed'],
  capacityRisks: ['normal', 'warning', 'critical', 'unknown', 'stale'],
  expansionPhases: ['pending', 'applying', 'completed', 'failed'],
  thresholds: { warningPercent: 80, criticalPercent: 95, staleAfterSeconds: 7200 },
  retention: { rawActivityDays: 90, dailyAggregates: 'permanent', capacitySnapshots: 'permanent' },
  endpoints: [
    '/platform-resources/workspaces/statistics/summary',
    '/workspaces/{workspaceId}/capacity',
  ],
});

test('accepts the fixed platform resource observability contract', () => {
  assert.doesNotThrow(() => assertPlatformResourceContract(validContract()));
});

test('rejects unsafe or ambiguous capacity semantics', () => {
  const contract = validContract();
  contract.capacityRisks = ['normal', 'unlimited'];
  assert.throws(() => assertPlatformResourceContract(contract), /capacityRisks/);
});

test('requires both localized chapters and the sidebar entry', () => {
  const contract = validContract();
  const identifiers = [
    ...contract.ranges,
    ...contract.storageKinds,
    ...contract.workspaceHealthGroups,
    ...contract.capacityRisks,
    ...contract.endpoints,
  ];
  const source = identifiers.map(value => `\`${value}\``).join('\n');

  assert.doesNotThrow(() => assertPlatformResourceDocumentation({
    contract,
    zhHantSource: source,
    englishSource: source,
    sidebarSource: "'features/platform/resource-statistics-and-capacity'",
  }));
  assert.throws(() => assertPlatformResourceDocumentation({
    contract,
    zhHantSource: source,
    englishSource: source,
    sidebarSource: '',
  }), /sidebar/);
});
