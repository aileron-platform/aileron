import assert from 'node:assert/strict';
import test from 'node:test';
import { assertAuthorizationContracts } from './authorization-contract-validator.mjs';

import {
  assertMarkerIdentifierParity,
  assertNoLegacyAuthorizationTerms,
  assertOnlyAllowedDocumentChanges,
  groupAuthorizationErrorCodes,
  renderTableWithDescriptions,
} from './check-authorization-contract.mjs';

const validContracts = () => ({
  wireContract: {
    schemaVersion: 2,
    platformRoles: ['admin', 'member'],
    resourceAccessRoles: ['reader', 'manager', 'owner'],
    resourceAccessSources: [
      'owned',
      'direct_share',
      'group_share',
      'public',
      'platform_admin',
    ],
    operationIds: [
      'workspace.collection.read',
      'workspace.detail.read',
    ],
    errorCodes: [
      'PLATFORM_AUTHORIZATION_DENIED',
      'WORKSPACE_ACCESS_DENIED',
    ],
  },
  operationContract: {
    schemaVersion: 2,
    requirements: [
      {
        operationId: 'workspace.collection.read',
        scope: 'platform',
        minimumResourceRole: null,
        platformAdminOnly: false,
      },
      {
        operationId: 'workspace.detail.read',
        scope: 'workspace',
        minimumResourceRole: 'reader',
        platformAdminOnly: false,
      },
    ],
  },
  runtimeRouteContract: {
    schemaVersion: 1,
    routes: [{
      routeTemplate: '/api/v1/files',
      methods: ['GET'],
      action: 'runtime_read',
      matchPriority: 10,
      sensitive: false,
    }],
  },
});

test('rejects fields outside the fixed wire contract schema', () => {
  const contracts = validContracts();
  contracts.wireContract.roleCapabilities = {
    admin: ['workspace.read'],
  };

  assert.throws(
    () => assertAuthorizationContracts(contracts),
    /fixed schema/,
  );
});

test('accepts the simplified authorization contract without capabilities', () => {
  assert.doesNotThrow(() => assertAuthorizationContracts(validContracts()));
});

test('rejects legacy platform and resource roles', () => {
  const contracts = validContracts();
  contracts.wireContract.platformRoles.push('developer');
  contracts.wireContract.resourceAccessRoles.push('editor');

  assert.throws(
    () => assertAuthorizationContracts(contracts),
    /platformRoles|resourceAccessRoles/,
  );
});

test('rejects capability fields from operation requirements', () => {
  const contracts = validContracts();
  contracts.operationContract.requirements[1].capability = 'workspace.read';

  assert.throws(
    () => assertAuthorizationContracts(contracts),
    /fixed schema|capability/,
  );
});

test('preserves an existing localized description by row key', () => {
  const existingTable = [
    '| OperationId | Capability | 說明 |',
    '| --- | --- | --- |',
    '| `workspace.detail.read` | `old.capability` | 保留這段說明 |',
  ].join('\n');

  const rendered = renderTableWithDescriptions({
    headers: ['OperationId', 'Capability'],
    rows: [['`workspace.detail.read`', '`workspace.read`']],
    descriptionHeader: '說明',
    existingTable,
    fallbackDescription: () => '不應覆寫',
  });

  assert.match(
    rendered,
    /\| `workspace\.detail\.read` \| `workspace\.read` \| 保留這段說明 \|/,
  );
});

test('generates a readable fallback for legacy rows and marks only new row keys', () => {
  const existingTable = [
    '| OperationId | Capability |',
    '| --- | --- |',
    '| `workspace.detail.read` | `workspace.read` |',
  ].join('\n');

  const rendered = renderTableWithDescriptions({
    headers: ['OperationId', 'Capability'],
    rows: [
      ['`workspace.detail.read`', '`workspace.read`'],
      ['`workspace.content.write`', '`workspace.write`'],
    ],
    descriptionHeader: '說明',
    existingTable,
    fallbackDescription: (row) => `既有操作 ${row[0]}`,
  });

  assert.match(
    rendered,
    /\| `workspace\.detail\.read` \| `workspace\.read` \| 既有操作 `workspace\.detail\.read` \|/,
  );
  assert.match(
    rendered,
    /\| `workspace\.content\.write` \| `workspace\.write` \| TODO_TRANSLATION \|/,
  );
});

test('replaces a legacy dash placeholder with a readable fallback', () => {
  const existingTable = [
    '| OperationId | Capability | 說明 |',
    '| --- | --- | --- |',
    '| `workspace.detail.read` | `workspace.read` | — |',
  ].join('\n');

  const rendered = renderTableWithDescriptions({
    headers: ['OperationId', 'Capability'],
    rows: [['`workspace.detail.read`', '`workspace.read`']],
    descriptionHeader: '說明',
    existingTable,
    fallbackDescription: () => '讀取 Workspace 詳情',
  });

  assert.match(rendered, /讀取 Workspace 詳情/);
  assert.doesNotMatch(rendered, /\| — \|/);
});

test('regenerates route descriptions for the same template with different methods', () => {
  const existingTable = [
    '| Route template | Methods | Action | Priority | Sensitive | Description |',
    '| --- | --- | --- | --- | --- | --- |',
    '| `/api/v1/example` | `GET` | `runtime_read` | `10` | No | stale write description |',
    '| `/api/v1/example` | `POST` | `runtime_write` | `20` | Yes | stale read description |',
  ].join('\n');

  const rendered = renderTableWithDescriptions({
    headers: ['Route template', 'Methods', 'Action', 'Priority', 'Sensitive'],
    rows: [
      ['`/api/v1/example`', '`GET`', '`runtime_read`', '`10`', 'No'],
      ['`/api/v1/example`', '`POST`', '`runtime_write`', '`20`', 'Yes'],
    ],
    descriptionHeader: 'Description',
    existingTable,
    fallbackDescription: (row) => `${row[1]} maps to ${row[2]}.`,
    preserveDescriptions: false,
    rowKey: (row) => JSON.stringify(row),
  });

  assert.match(
    rendered,
    /`GET` \| `runtime_read` \| `10` \| No \| `GET` maps to `runtime_read`\./,
  );
  assert.match(
    rendered,
    /`POST` \| `runtime_write` \| `20` \| Yes \| `POST` maps to `runtime_write`\./,
  );
  assert.doesNotMatch(rendered, /stale (?:write|read) description/);
});

test('preserves descriptions by the complete row key when route templates repeat', () => {
  const existingTable = [
    '| Route template | Methods | Action | Description |',
    '| --- | --- | --- | --- |',
    '| `/api/v1/example` | `GET` | `runtime_read` | 讀取說明 |',
    '| `/api/v1/example` | `POST` | `runtime_write` | 寫入說明 |',
  ].join('\n');

  const rendered = renderTableWithDescriptions({
    headers: ['Route template', 'Methods', 'Action'],
    rows: [
      ['`/api/v1/example`', '`GET`', '`runtime_read`'],
      ['`/api/v1/example`', '`POST`', '`runtime_write`'],
    ],
    descriptionHeader: 'Description',
    existingTable,
    fallbackDescription: () => '不應覆寫',
    rowKey: (row) => JSON.stringify(row),
  });

  assert.match(
    rendered,
    /`GET` \| `runtime_read` \| 讀取說明/,
  );
  assert.match(
    rendered,
    /`POST` \| `runtime_write` \| 寫入說明/,
  );
  assert.doesNotMatch(rendered, /不應覆寫/);
});

test('rejects changes outside the exact authorization document allow-list', () => {
  const before = new Map([
    ['/workspace/docs-site/docs/api/manager-api.md', 'before'],
    ['/workspace/docs-site/docs/api/other.md', 'before'],
  ]);
  const after = new Map([
    ['/workspace/docs-site/docs/api/manager-api.md', 'after'],
    ['/workspace/docs-site/docs/api/other.md', 'after'],
  ]);
  const allowedPaths = new Set([
    '/workspace/docs-site/docs/api/manager-api.md',
  ]);

  assert.throws(
    () => assertOnlyAllowedDocumentChanges(before, after, allowedPaths),
    /other\.md/,
  );
});

test('permits changes limited to the exact authorization document allow-list', () => {
  const before = new Map([
    ['/workspace/docs-site/docs/api/manager-api.md', 'before'],
    ['/workspace/docs-site/docs/api/other.md', 'same'],
  ]);
  const after = new Map([
    ['/workspace/docs-site/docs/api/manager-api.md', 'after'],
    ['/workspace/docs-site/docs/api/other.md', 'same'],
  ]);
  const allowedPaths = new Set([
    '/workspace/docs-site/docs/api/manager-api.md',
  ]);

  assert.doesNotThrow(
    () => assertOnlyAllowedDocumentChanges(before, after, allowedPaths),
  );
});

test('rejects different identifier order between localized marker blocks', () => {
  const zhHant = [
    '| OperationId | 說明 |',
    '| --- | --- |',
    '| `workspace.detail.read` | 讀取 |',
    '| `workspace.content.write` | 寫入 |',
  ].join('\n');
  const english = [
    '| OperationId | Description |',
    '| --- | --- |',
    '| `workspace.content.write` | Write |',
    '| `workspace.detail.read` | Read |',
  ].join('\n');

  assert.throws(
    () => assertMarkerIdentifierParity(zhHant, english, 'workspace'),
    /workspace.*identifier order/,
  );
});

test('rejects legacy authorization identifiers outside an explicit history block', () => {
  assert.throws(
    () => assertNoLegacyAuthorizationTerms(
      'Workspace `editor` still has `workspace.write`.',
      'features/example.md',
    ),
    /legacy authorization.*features\/example\.md/,
  );

  assert.doesNotThrow(() => assertNoLegacyAuthorizationTerms(
    [
      '<!-- authorization-legacy:start -->',
      'The removed `editor` role is rejected.',
      '<!-- authorization-legacy:end -->',
    ].join('\n'),
    'features/history.md',
  ));
});

test('routes Platform Resources errors to the Manager API marker', () => {
  const errorCodes = [
    'PLATFORM_AUTHORIZATION_DENIED',
    'MANAGER_SESSION_REQUIRED',
    'MANAGER_SESSION_ORIGIN_INVALID',
    'MANAGER_SESSION_CSRF_INVALID',
    'PLATFORM_RESOURCE_INVALID_REQUEST',
    'PLATFORM_RESOURCE_NOT_FOUND',
    'RESOURCE_DELETE_CONFIRMATION_MISMATCH',
  ];

  assert.deepEqual(groupAuthorizationErrorCodes(errorCodes), {
    platform: [
      'PLATFORM_AUTHORIZATION_DENIED',
      'MANAGER_SESSION_REQUIRED',
      'MANAGER_SESSION_ORIGIN_INVALID',
      'MANAGER_SESSION_CSRF_INVALID',
      'RESOURCE_DELETE_CONFIRMATION_MISMATCH',
    ],
    platformResources: [
      'PLATFORM_RESOURCE_INVALID_REQUEST',
      'PLATFORM_RESOURCE_NOT_FOUND',
    ],
    workspace: [],
    knowledgeBase: [],
    runtime: [],
  });
});
